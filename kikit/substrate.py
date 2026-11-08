from shapely import geometry
from shapely.geometry import (Polygon, MultiPolygon, LineString,
    MultiLineString, LinearRing, Point)
from shapely.geometry.collection import GeometryCollection
from shapely.ops import orient, unary_union, split, nearest_points, substring
import shapely
import json
import math
import numpy as np
from kikit.intervals import Interval, BoxNeighbors, BoxPartitionLines
import pcbnew
from enum import IntEnum
from itertools import product

from typing import Iterable, List, Tuple, Union

from kikit.common import *
from kikit.units import deg
from kikit.defs import STROKE_T, Layer

TABFAIL_VISUAL = False
GEOMETRY_EPSILON = fromMm(0.00001)
ARC_CHORD_ERROR = fromMm(0.0001)  # Bound chord sagitta during polygon operations to 0.1 um.

class PositionError(RuntimeError):
    def __init__(self, message, point):
        super().__init__(message.format(toMm(point[0]), toMm(point[1])))
        self.point = point
        self.origMessage = message

class NoIntersectionError(RuntimeError):
    def __init__(self, message, point):
        super().__init__(message)
        self.point = point

class TabError(RuntimeError):
    def __init__(self, origin, direction, hints):
        self.origin = origin
        self.direction = direction
        message = "Cannot create tab; possible causes:\n"
        for hint in hints:
            message += f"- {hint}\n"
        super().__init__(message)

class TabFilletError(RuntimeError):
    pass

def roundPoint(point, precision=-2):
    return (round(point[0], precision), round(point[1], precision))

def getStartPoint(geom):
    if geom.GetShape() == STROKE_T.S_CIRCLE:
        # Circle start is circle center /o\
        point = geom.GetStart() + pcbnew.VECTOR2I(geom.GetRadius(), 0)
    elif geom.GetShape() == STROKE_T.S_RECT:
        point = geom.GetStart()
    elif geom.GetShape() == STROKE_T.S_POLYGON:
        # Polygons don't use the properties for start point, look into the
        # geometry
        point = geom.GetPolyShape().Outline(0).CPoints()[0]
    else:
        point = geom.GetStart()
    return point

def getEndPoint(geom):
    if geom.GetShape() == STROKE_T.S_CIRCLE:
        # Circle start is circle center /o\
        point = geom.GetStart() + pcbnew.VECTOR2I(geom.GetRadius(), 0)
    elif geom.GetShape() == STROKE_T.S_RECT:
        # Rectangle is closed, so it starts at the same point as it ends
        point = geom.GetStart()
    elif geom.GetShape() == STROKE_T.S_POLYGON:
        # Polygons don't use the properties for start point, look into the
        # geometry
        outline = geom.GetPolyShape().Outline(0)
        if outline.IsClosed():
            point = outline.CPoints()[0]
        else:
            point = outline.CPoints()[-1]
    else:
        point = geom.GetStart() if geom.IsClosed() else geom.GetEnd()
    return point

class CoincidenceList(list):
    def getNeighbor(self, myIdx):
        if self[0] == myIdx:
            return self[1]
        return self[0]

def getUnused(usageList):
    return usageList.index(True)

def findRing(startIdx, geometryList, coincidencePoints, unused):
    """
    Find a geometry ring starting at given element, returns it as a list of indices
    """
    unused[startIdx] = False
    ring = [startIdx]
    if roundPoint(getStartPoint(geometryList[startIdx])) == roundPoint(getEndPoint(geometryList[startIdx])):
        return ring
    currentPoint = roundPoint(getEndPoint(geometryList[startIdx]))
    while True:
        nextIdx = coincidencePoints[currentPoint].getNeighbor(ring[-1])
        assert(unused[nextIdx] or nextIdx == startIdx)
        if currentPoint == roundPoint(getStartPoint(geometryList[nextIdx])):
            currentPoint = roundPoint(getEndPoint(geometryList[nextIdx]))
        else:
            currentPoint = roundPoint(getStartPoint(geometryList[nextIdx]))
        unused[nextIdx] = False
        if nextIdx == startIdx:
            return ring
        ring.append(nextIdx)

def isValidPcbShape(g):
    """
    Currently, we are aware of a single case of an invalid pcb_shape -- line
    with zero length. Unfortunately, KiCAD does not discard such lines when
    saving. Therefore, we have to check it.
    """
    return g.GetShape() != pcbnew.S_SEGMENT or g.GetLength() >= fromMm(0.001)

def extractRings(geometryList):
    """
    Walks a list of PCB_SHAPE entities and produces a list of continuous rings
    returned as list of list of indices from the geometryList.
    """
    coincidencePoints = {}
    invalidGeometry = []
    for i, geom in enumerate(geometryList):
        if not isValidPcbShape(geom):
            invalidGeometry.append(i)
            continue
        start = roundPoint(getStartPoint(geom))
        coincidencePoints.setdefault(start, CoincidenceList()).append(i)
        end = roundPoint(getEndPoint(geom))
        coincidencePoints.setdefault(end, CoincidenceList()).append(i)
    for point, items in coincidencePoints.items():
        l = len(items)
        if l == 1:
            raise PositionError("Discontinuous outline at [{}, {}]. This may have several causes:\n" +
                                "    - The outline in really discontinuous. Check the coordinates in your source board.\n" +
                                "    - You haven't included all the outlines or in the case of multi-design,\n" +
                                "      you have included a part of outline from a neighboring board.",
                                point)
        if l == 2:
            continue
        raise PositionError("Multiple outlines ({}) at [{{}}, {{}}]".format(l), point)

    rings = []
    unused = [True] * len(geometryList)
    for invalidIdx in invalidGeometry:
        unused[invalidIdx] = False
    while any(unused):
        start = getUnused(unused)
        rings.append(findRing(start, geometryList, coincidencePoints, unused))
    return rings

def commonEndPoint(a, b):
    """
    Return common end/start point of two entities
    """
    aStart, aEnd = getStartPoint(a), getEndPoint(a)
    bStart, bEnd = getStartPoint(b), getEndPoint(b)
    if roundPoint(aStart) == roundPoint(bStart) or roundPoint(aStart) == roundPoint(bEnd):
        return aStart
    return aEnd

def approximateArc(arc, endWith):
    """
    Take DRAWINGITEM and approximate it using lines
    """
    startAngle = EDA_ANGLE(0, pcbnew.DEGREES_T)
    endAngle = EDA_ANGLE(0, pcbnew.DEGREES_T)
    arc.CalcArcAngles(startAngle, endAngle)
    if arc.GetShape() == STROKE_T.S_CIRCLE:
        endAngle = startAngle + 360 * deg
    step = 2 * np.arccos(max(-1, 1 - ARC_CHORD_ERROR / max(arc.GetRadius(), 1)))
    segments = max(12, int(np.ceil(abs(endAngle.AsRadians() - startAngle.AsRadians()) / step)) + 1)
    if arc.GetShape() == STROKE_T.S_CIRCLE:
        # Include the four extrema so circular-board bounds and placement stay exact.
        segments = 4 * int(np.ceil((segments - 1) / 4)) + 1
    theta = np.linspace(startAngle.AsRadians(), endAngle.AsRadians(), segments)
    x = arc.GetCenter()[0] + arc.GetRadius() * np.cos(theta)
    y = arc.GetCenter()[1] + arc.GetRadius() * np.sin(theta)
    outline = list(np.column_stack([x, y]))
    if arc.GetShape() == STROKE_T.S_ARC:
        endpoints = [np.array(arc.GetStart()), np.array(arc.GetEnd())]
        if np.linalg.norm(outline[0] - endpoints[0]) > np.linalg.norm(outline[0] - endpoints[1]):
            endpoints.reverse()
        outline[0], outline[-1] = endpoints

    end = np.array(endWith)
    first = np.array([outline[0][0], outline[0][1]])
    last = np.array([outline[-1][0], outline[-1][1]])
    if (np.linalg.norm(end - first) < np.linalg.norm(end - last)):
        outline.reverse()
    return outline

def approximateBezier(bezier, endWith):
    """
    Take DRAWINGITEM bezier and approximate it using lines.

    This is more or less inspired by the KiCAD code as KiCAD does not export
    the relevant functions
    """
    assert bezier.GetShape() == STROKE_T.S_CURVE

    start = np.array(bezier.GetStart())
    if hasattr(bezier, "GetBezierC1"):
      bc1 = np.array(bezier.GetBezierC1())
      bc2 = np.array(bezier.GetBezierC2())
    else:
      bc1 = np.array(bezier.GetBezControl1())
      bc2 = np.array(bezier.GetBezControl2())
    end = np.array(bezier.GetEnd())

    outline = [start]
    pending = [np.array([start, bc1, bc2, end], dtype=float)]
    while pending:
        curve = pending.pop()
        chord = curve[3] - curve[0]
        lengthSquared = np.dot(chord, chord)
        if lengthSquared:
            projections = np.clip((curve[1:3] - curve[0]) @ chord / lengthSquared, 0, 1)
            errors = curve[1:3] - (curve[0] + projections[:, None] * chord)
        else:
            errors = curve[1:3] - curve[0]
        if np.max(np.linalg.norm(errors, axis=1)) <= ARC_CHORD_ERROR:
            outline.append(curve[3])
            continue
        a, b, c = (curve[:-1] + curve[1:]) / 2
        d, e = (a + b) / 2, (b + c) / 2
        middle = (d + e) / 2
        pending.extend([np.array([middle, e, c, curve[3]]),
                        np.array([curve[0], a, d, middle])])

    endWith = np.array(endWith)
    first = np.array([outline[0][0], outline[0][1]])
    last = np.array([outline[-1][0], outline[-1][1]])
    if (np.linalg.norm(endWith - first) < np.linalg.norm(endWith - last)):
        outline.reverse()

    return outline

def shapeLinechainToList(l: pcbnew.SHAPE_LINE_CHAIN) -> List[Tuple[int, int]]:
    return [(p.x, p.y) for p in l.CPoints()]

def shapePolyToShapely(p: pcbnew.SHAPE_POLY_SET) \
        -> Union[shapely.geometry.Polygon, shapely.geometry.MultiPolygon]:
    """
    Take SHAPE_POLY_SET and create a shapely polygon out of it.
    """
    polygons = []
    for pIdx in range(p.OutlineCount()):
        kOutline = p.Outline(pIdx)
        assert kOutline.IsClosed()
        outline = shapeLinechainToList(kOutline)
        holes = []
        for hIdx in range(p.HoleCount(pIdx)):
            kHole = p.Hole(pIdx, hIdx)
            holes.append(shapeLinechainToList(kHole))
        polygons.append(Polygon(outline, holes=holes))
    if len(polygons) == 1:
        return polygons[0]
    return MultiPolygon(polygons=polygons)


def rectToShapely(rect):
    corners = [tuple(c) for c in rect.GetRectCorners()]
    try:
        radius = rect.GetCornerRadius()
    except AttributeError:
        # KiCad 9 has no corner radius on rects
        radius = 0
    poly = Polygon(corners)
    if radius == 0:
        return poly
    # Shrink-then-grow rounds the corners; unlike manual arc math this
    # works correctly even when the rect is rotated.
    return poly.buffer(-radius, join_style='round').buffer(radius, join_style='round')

def toShapely(ring, geometryList):
    """
    Take a list of indices representing a ring from PCB_SHAPE entities and
    convert them into a shapely polygon. The segments are expected to be
    continuous. Arcs & others are broken down into lines.
    """
    outline = []
    for idxA, idxB in zip(ring, ring[1:] + ring[:1]):
        shape = geometryList[idxA].GetShape()
        if shape in [STROKE_T.S_ARC, STROKE_T.S_CIRCLE]:
            outline += approximateArc(geometryList[idxA],
                commonEndPoint(geometryList[idxA], geometryList[idxB]))
        elif shape in [STROKE_T.S_CURVE]:
            outline += approximateBezier(geometryList[idxA],
                commonEndPoint(geometryList[idxA], geometryList[idxB]))
        elif shape in [STROKE_T.S_RECT]:
            assert idxA == idxB
            return rectToShapely(geometryList[idxA])
        elif shape in [STROKE_T.S_POLYGON]:
            # Polygons are always closed, so they should appear as stand-alone
            assert len(ring) in [1, 2]
            return shapePolyToShapely(geometryList[idxA].GetPolyShape())
        elif shape in [STROKE_T.S_SEGMENT]:
            outline.append(commonEndPoint(geometryList[idxA], geometryList[idxB]))
        else:
            raise RuntimeError(f"Unsupported shape {shape} in outline")
    return Polygon(outline)

def buildContainmentGraph(polygons):
    """
    Given a list of polygons returns a dictionary a -> [b] representing a
    relation "a contains b". a and b are indices to the original list.
    """
    # We use the naive algorithm - test all pairs - as the number of polygons is
    # rather small in a typical scenario
    polygonCount = len(polygons)
    relation = {key: [] for key in range(polygonCount)}
    for a, b in product(range(polygonCount), range(polygonCount)):
        if a == b:
            continue
        if polygons[a].contains(polygons[b]):
            relation[a].append(b)
    return relation

class DFS(IntEnum):
    WHITE = 0
    GRAY = 2
    BLACK = 3

def topologicalSort(graph):
    """
    Given a acyclic graph as a dictionary a -> [b] computes topological order
    as a list
    """
    vertexState = dict.fromkeys(graph.keys(), DFS.WHITE)
    topologicalSort = []
    def dfs(vertex):
        vertexState[vertex] = DFS.GRAY
        for neighbor in graph[vertex]:
            if vertexState[neighbor] == DFS.WHITE:
                dfs(neighbor)
        vertexState[vertex] = DFS.BLACK
        topologicalSort.append(vertex)
    for vertex in graph.keys():
        if vertexState[vertex] == DFS.WHITE:
            dfs(vertex)
    return topologicalSort

def graphLevels(graph):
    """
    Assigns levels to graph based on the longest path from a root in DAG.
    The levels are returned as a dictionary vertex -> level
    """
    vertexLevel = dict.fromkeys(graph.keys(), 0)
    # Relax the edges in a topological order
    sort = topologicalSort(graph)
    sort.reverse()
    for vertex in sort:
        level = vertexLevel[vertex]
        for neighbor in graph[vertex]:
            vertexLevel[neighbor] = max(vertexLevel[neighbor], level + 1)
    return vertexLevel

def even(number):
    return number % 2 == 0

def substratesFrom(polygons):
    """
    Given a list of polygons, decides which polygons are inner and which are
    outer and returns a list of polygons with holes (substrates)
    """
    containmentGraph = buildContainmentGraph(polygons)
    polygonLevels = graphLevels(containmentGraph) # Even polygons are outlines, odd are holes
    substrates = []
    for idx, polygon in enumerate(polygons):
        level = polygonLevels[idx]
        if not even(level):
            continue
        holes = [polygons[x].exterior for x in containmentGraph[idx] if polygonLevels[x] == level + 1]
        substrates.append(Polygon(polygon.exterior, holes))
    return substrates

class CircleFitCandidates:
    def __init__(self, tolerance: int = fromMm(0.005), radius_limit: int = fromMm(1000)):
        self.tolerance = tolerance
        self.radius_limit = radius_limit

        self._xs = []
        self._xSum: float = 0
        self._ys = []
        self._ySum: float = 0

        self.foundCircle: Optional[Tuple[np.array, float]] = None

    def __len__(self) -> int:
        return len(self._xs)

    def addPoint(self, point: VECTOR2I) -> bool:
        """
        Try adding a candidate point. Returns true, if the point could lie on
        already found a circle. If the point doesn't lie on an already found
        circle, it is not added to the collection.
        """
        self._xs.append(point[0])
        self._xSum += point[0]

        self._ys.append(point[1])
        self._ySum += point[1]

        if len(self) < 5:
            return True

        newCenter, newRadius = self._fitCircle()

        needsRevalidation = False
        if self.foundCircle is None:
            needsRevalidation = True
        else:
            c, r = self.foundCircle
            needsRevalidation = np.linalg.norm(newCenter - c) > self.tolerance or np.abs(newRadius - r) > self.tolerance

        if needsRevalidation:
            toRevalidate = zip(zip(self._xs, self._ys),
                               zip(self._xs[1:], self._ys[1:]))
        else:
            toRevalidate = [((self._xs[-2], self._ys[-2]),
                             (self._xs[-1], self._ys[-1]))]

        if self._doLinesFitCircle(toRevalidate, newCenter, newRadius) and newRadius < self.radius_limit:
            self.foundCircle = newCenter, newRadius
            return True

        self._popLast()
        return False

    def _doLinesFitCircle(self, lines: Iterable[Tuple[np.array, np.array]],
                          c: np.array, r: float) -> bool:
        # Scalar arithmetic avoids NumPy dispatch for these two-dimensional vectors.
        cx, cy = map(float, c)
        for start, end in lines:
            sx, sy = map(float, start)
            ex, ey = map(float, end)
            # Distance extrema are at the endpoints or the center's projection.
            if abs(math.hypot(sx - cx, sy - cy) - r) > self.tolerance:
                return False
            if abs(math.hypot(ex - cx, ey - cy) - r) > self.tolerance:
                return False

            dx, dy = ex - sx, ey - sy
            lengthSquared = dx * dx + dy * dy
            if lengthSquared == 0:
                continue
            t = ((cx - sx) * dx + (cy - sy) * dy) / lengthSquared
            if 0 <= t <= 1:
                if abs(math.hypot(sx + t * dx - cx, sy + t * dy - cy) - r) > self.tolerance:
                    return False
        return True

    @property
    def start(self) -> np.array:
        return np.array((self._xs[0], self._ys[0]))

    @property
    def end(self) -> np.array:
        return np.array((self._xs[-1], self._ys[-1]))

    @property
    def mid(self) -> np.array:
        idx = len(self) // 2
        return np.array((self._xs[idx], self._ys[idx]))

    def _popLast(self):
        self._xSum -= self._xs[-1]
        self._xs.pop()
        self._ySum -= self._ys[-1]
        self._ys.pop()

    def _fitCircle(self, maxIter = 10) -> Tuple[np.array, float]:
        """
        Implements Kenichi Kanatani, Prasanna Rangarajan, "Hyper least squares fitting of circles and ellipses"
        Computational Statistics & Data Analysis, Vol. 55, pages 2197-2208, (2011)

        Implementation is based on https://github.com/AlliedToasters/circle-fit/blob/master/src/circle_fit/circle_fit.py

        Returns center and radius of the circle fit.
        """
        n = len(self._xs)

        xMean = self._xSum / n
        yMean = self._ySum / n

        Xi = np.array(self._xs) - xMean
        Yi = np.array(self._ys) - yMean
        XiSquared = Xi * Xi
        YiSquared = Yi * Yi
        Zi = XiSquared + YiSquared

        # compute moments
        Mxy = (Xi * Yi).sum() / n
        Mxx = XiSquared.sum() / n
        Myy = YiSquared.sum() / n
        Mxz = (Xi * Zi).sum() / n
        Myz = (Yi * Zi).sum() / n
        Mzz = (Zi * Zi).sum() / n

        # Preserve the centered reductions; use scalar arithmetic in the root solver.
        Mxy, Mxx, Myy, Mxz, Myz, Mzz = map(float, (Mxy, Mxx, Myy, Mxz, Myz, Mzz))

        # computing the coefficients of characteristic polynomial
        Mz = Mxx + Myy
        Cov_xy = Mxx * Myy - Mxy * Mxy
        Var_z = Mzz - Mz * Mz

        A2 = 4 * Cov_xy - 3 * Mz * Mz - Mzz
        A1 = Var_z * Mz + 4. * Cov_xy * Mz - Mxz * Mxz - Myz * Myz
        A0 = Mxz * (Mxz * Myy - Myz * Mxy) + Myz * (Myz * Mxx - Mxz * Mxy) - Var_z * Cov_xy
        A22 = A2 + A2

        # finding the root of the characteristic polynomial
        Y = A0
        X = 0.0
        for i in range(maxIter):
            Dy = A1 + X * (A22 + 16. * (X ** 2))
            if Dy == 0:
                break
            xnew = X - Y / Dy
            if xnew == X or not np.isfinite(xnew):
                break
            ynew = A0 + xnew * (A1 + xnew * (A2 + 4. * xnew * xnew))
            if abs(ynew) >= abs(Y):
                break
            X, Y = xnew, ynew

        det = X ** 2 - X * Mz + Cov_xy
        if det == 0:
            return np.array([np.nan, np.nan]), np.nan
        Xcenter = (Mxz * (Myy - X) - Myz * Mxy) / det / 2.
        Ycenter = (Myz * (Mxx - X) - Mxz * Mxy) / det / 2.

        xc: float = Xcenter + xMean
        yc: float = Ycenter + yMean
        r = np.sqrt(abs(Xcenter ** 2 + Ycenter ** 2 + Mz))
        return np.array((xc, yc)), r



def liesOnSegment(start, end, point, tolerance=fromMm(0.01)):
    """
    Decide if a point lies on a given segment within tolerance
    """
    segment = LineString([start, end])
    point = Point(point)
    candidatePoint, _ = nearest_points(segment, point)
    return candidatePoint.distance(point) < tolerance

def biteBoundary(boundary, pointA, pointB, tolerance=fromMm(0.01)):
    """
    Given an oriented and possibly cyclic boundary in a form of shapely
    linestring, return a part of the boundary between pointA and pointB. The
    orientation matters - the segment is oriented from A to B.

    If no intersection is found, None is returned.
    """
    if isLinestringCyclic(boundary):
        c = boundary.coords
        if c[0] == c[-1]:
            boundaryCoords = chain(c, islice(c, 1, None))
        else:
            boundaryCoords = chain(c, c)
    else:
        boundaryCoords = boundary.coords
    boundaryCoords = list(boundaryCoords)
    faceCoords = []
    targetPoint = (pointA.x, pointA.y)
    inCut = False
    for a, b in zip(boundaryCoords, islice(boundaryCoords, 1, None)):
        # The following lines limit the number of points we have to test
        # for relatively expensive liesOnSegment
        segmentLength = np.linalg.norm((a[0] - b[0], a[1] - b[1]))
        targetDistance = np.linalg.norm((a[0] - targetPoint[0], a[1] - targetPoint[1]))
        isCandidate = segmentLength >= targetDistance
        if isCandidate and liesOnSegment(a, b, targetPoint, tolerance):
            faceCoords.append(targetPoint)
            if inCut:
                return LineString(faceCoords)
            inCut = True
            targetPoint = (pointB.x, pointB.y)
            # The pointB might lie on the same segment
            if liesOnSegment(a, b, targetPoint, tolerance):
                return LineString([pointA, pointB])
        if inCut:
            faceCoords.append(b)
    return None


def closestIntersectionPoint(origin, direction, outline, maxDistance):
    """Find the closest intersection between an outline from a point within a maximum distance under a given direction"""
    testLine = LineString([origin, origin + direction * maxDistance])
    inter = testLine.intersection(outline)
    if inter.is_empty:
        if TABFAIL_VISUAL:
            import matplotlib.pyplot as plt

            plt.axis('equal')
            x, y = outline.coords.xy
            plt.plot(list(map(toMm, x)), list(map(toMm, y)))
            x, y = testLine.coords.xy
            plt.plot(list(map(toMm, x)), list(map(toMm, y)))
            plt.show()
        raise NoIntersectionError(f"No intersection found within given distance", origin)
    origin = Point(origin[0], origin[1])
    geoms = list()
    for geom in listGeometries(inter):
        if isinstance(geom, Point):
            geoms.append(geom)
        elif isinstance(geom, LineString):
            # When a linestring is an intersection, we know that the starting or
            # ending points are the nearest one
            geoms.extend([Point(geom.coords[0]), Point(geom.coords[-1])])
        else:
            raise TypeError(f"intersection() returned an unsupported datatype: {geom.__class__.__name__}")
    return min([(g, origin.distance(g)) for g in geoms], key=lambda t: t[1])[0]

def closestRing(geom, origin, direction, maxDistance):
    """
    Given a polygon geometry, find the ring (exterior or one of the
    interiors) that has the closest intersection point from origin in the
    given direction. This allows tab() to work with polygons that have
    holes (e.g., frame geometry with milled slots).
    """
    bestRing = None
    bestDist = float('inf')
    originPoint = Point(origin[0], origin[1])
    for ring in [geom.exterior] + list(geom.interiors):
        try:
            p = closestIntersectionPoint(origin, direction, ring, maxDistance)
            d = originPoint.distance(p)
            if d < bestDist:
                bestDist = d
                bestRing = ring
        except NoIntersectionError:
            continue
    if bestRing is None:
        raise NoIntersectionError("No intersection found within given distance", origin)
    return bestRing

def linestringToKicad(linestring):
    """
    Convert Shapely linestring to KiCAD's linechain
    """
    lineChain = pcbnew.SHAPE_LINE_CHAIN()
    lineChain.SetClosed(True)
    for c in linestring.coords:
        lineChain.Append(int(c[0]), int(c[1]))
    return lineChain

class Substrate:
    """
    Represents (possibly multiple) PCB substrates reconstructed from a list of
    geometry
    """
    def __init__(self, geometryList, bufferDistance=0, revertTransformation=None):
        # Retain exact circles and arc endpoints through polygon unions and translations.
        self.circles = [(np.array(e.GetCenter(), dtype=float), float(e.GetRadius()),
                         np.array(getStartPoint(e), dtype=float), np.array(getEndPoint(e), dtype=float), None)
                        for e in geometryList if e.GetShape() in [STROKE_T.S_ARC, STROKE_T.S_CIRCLE]]
        polygons = [toShapely(ring, geometryList) for ring in extractRings(geometryList)]
        self.substrates = unary_union(substratesFrom(polygons))
        self.oriented = False
        if not self.substrates.is_empty:
            self.orient()
        self.partitionLine = shapely.geometry.GeometryCollection()
        self.annotations = []
        self.revertTransformation = revertTransformation

    def backToSource(self, point):
        """
        Return a point in the source form (if a reverse transformation was set)
        """
        if self.revertTransformation is not None:
            return self.revertTransformation(point)
        return point

    def orient(self):
        """
        Ensures that the substrate is oriented in a correct way.
        """
        if self.oriented:
            return
        self.substrates = shapely.set_precision(self.substrates, 1).simplify(GEOMETRY_EPSILON)
        self.substrates = shapely.ops.orient(self.substrates)
        self.oriented = True

    def bounds(self):
        """
        Return shapely bounds of substrates
        """
        return self.substrates.bounds

    def interiors(self):
        """
        Return shapely interiors of the substrate
        """
        return self.substrates.interiors

    def midpoint(self) -> Tuple[int, int]:
        """
        Return a mid point of the bounding box
        """
        minx, miny, maxx, maxy = self.substrates.bounds
        return ((minx + maxx) // 2, (miny + maxy) // 2)

    def union(self, other):
        """
        Appends a substrate, polygon or list of polygons. If there is a common
        intersection, with existing substrate, it will be merged into a single
        substrate.
        """
        if isinstance(other, list):
            self.substrates = shapely.union_all([self.substrates] + other, grid_size=1)
        elif isinstance(other, Substrate):
            self.substrates = shapely.union(self.substrates, other.substrates, grid_size=1)
            self.circles.extend(other.circles)
        else:
            self.substrates = shapely.union(self.substrates, other, grid_size=1)
        if isinstance(self.substrates, GeometryCollection):
            # Edges collapsed by nanometre quantization have no substrate area.
            self.substrates = shapely.union_all(
                [g for g in self.substrates.geoms if isinstance(g, (Polygon, MultiPolygon))], grid_size=1)
        self.oriented = False

    def cut(self, piece):
        """
        Remove a piece of substrate given a shapely polygon.
        """
        self.substrates = self.substrates.difference(piece)

    def serialize(self, reconstructArcs=False):
        """
        Produces a list of PCB_SHAPE on the Edge.Cuts layer
        """
        if self.substrates.is_empty:
            return []
        if isinstance(self.substrates, MultiPolygon) or isinstance(self.substrates, GeometryCollection):
            geoms = self.substrates.geoms
        elif isinstance(self.substrates, Polygon):
            geoms = [self.substrates]
        else:
            raise RuntimeError("Uknown type '{}' of substrate geometry".format(type(self.substrates)))
        circleIndex = None
        if reconstructArcs and self.circles:
            circleIndex = shapely.STRtree([
                geometry.box(center[0] - radius, center[1] - radius,
                             center[0] + radius, center[1] + radius)
                for center, radius, _, _, _ in self.circles])
        items = []
        for polygon in geoms:
            simplified_polygon = shapely.simplify(polygon, GEOMETRY_EPSILON)
            items += self._serializeRing(simplified_polygon.exterior, reconstructArcs, circleIndex)
            for interior in simplified_polygon.interiors:
                items += self._serializeRing(interior, reconstructArcs, circleIndex)
        return items

    def _serializeRing(self, ring, reconstructArcs, circleIndex=None):
        TOLERANCE = ARC_CHORD_ERROR + GEOMETRY_EPSILON
        coords = ring.coords
        if coords[0] != coords[-1]:
            raise RuntimeError("Ring is incomplete")

        # Always start with the longes semgent (so we do not start in the middle
        # of an arc if possible)
        coords = np.array(coords[:-1])  # Exclude the last point since it's a duplicate of the first
        distances = np.sqrt(np.sum(np.diff(coords, axis=0, append=coords[:1,:])**2, axis=1))
        max_dist_index = np.argmax(distances)
        rearranged = np.roll(coords, -max_dist_index, axis=0)
        coords = np.vstack((rearranged, rearranged[0]))

        candidates = []
        if circleIndex is None and reconstructArcs:
            candidates = list(enumerate(self.circles))
        if circleIndex is not None:
            minx, miny, maxx, maxy = ring.bounds
            margin = ARC_CHORD_ERROR + GEOMETRY_EPSILON
            nearby = circleIndex.query(geometry.box(minx - margin, miny - margin,
                                                    maxx + margin, maxy + margin))
            candidates = [(i, self.circles[i]) for i in sorted(nearby)]

        if reconstructArcs:
            # Boolean operations on chords can trim a tangent endpoint by a fraction of a micron.
            for _, (_, _, start, end, _) in candidates:
                for endpoint in [start, end]:
                    coords[np.linalg.norm(coords - endpoint, axis=1) <= ARC_CHORD_ERROR] = endpoint
            keep = np.r_[True, np.linalg.norm(np.diff(coords, axis=0), axis=1) > 1]
            coords = coords[keep]

        circleEdges = np.full(len(coords) - 1, -1, dtype=int)
        circleErrors = np.full(len(coords) - 1, np.inf)
        if reconstructArcs:
            midpoints = (coords[:-1] + coords[1:]) / 2
            for index, (center, radius, start, end, sweep) in candidates:
                errors = np.abs(np.linalg.norm(coords - center, axis=1) - radius)
                chordErrors = np.abs(np.linalg.norm(midpoints - center, axis=1) - radius)
                edgeErrors = np.maximum(errors[:-1], errors[1:])
                matches = ((edgeErrors <= ARC_CHORD_ERROR + GEOMETRY_EPSILON) &
                           (chordErrors <= 4 * ARC_CHORD_ERROR + GEOMETRY_EPSILON) &
                           (edgeErrors < circleErrors))
                if sweep is not None:
                    # Nearby non-circular edges can lie close to the circle past its tangency.
                    angles = np.arctan2(coords[:, 1] - center[1], coords[:, 0] - center[0])
                    firstAngle = np.arctan2(start[1] - center[1], start[0] - center[0])
                    progress = ((angles - firstAngle) * np.sign(sweep)) % (2 * np.pi)
                    tolerance = GEOMETRY_EPSILON / radius
                    inside = ((progress <= abs(sweep) + tolerance) |
                              (progress >= 2 * np.pi - tolerance))
                    matches &= inside[:-1] & inside[1:]
                circleEdges[matches] = index
                circleErrors[matches] = edgeErrors[matches]

        segments = []
        i = 0
        while i < len(coords) - 1:
            if circleEdges[i] >= 0:
                j = i + 1
                while j < len(circleEdges) and circleEdges[j] == circleEdges[i]:
                    j += 1
                center, radius, _, _, _ = self.circles[circleEdges[i]]
                angles = np.unwrap(np.arctan2(coords[i:j+1, 1] - center[1],
                                             coords[i:j+1, 0] - center[0]))
                if (abs(angles[-1] - angles[0]) > np.pi and
                        np.linalg.norm(coords[i] - coords[j]) <= GEOMETRY_EPSILON):
                    segments.append(self._constructCircle(center, radius))
                else:
                    angle = (angles[0] + angles[-1]) / 2
                    middle = center + radius * np.array([np.cos(angle), np.sin(angle)])
                    segments.append(self._constructArc(coords[i], middle, coords[j]))
                i = j
                continue
            j = i # in the case the following cycle never happens
            candidateCircle = CircleFitCandidates(tolerance=TOLERANCE)
            if reconstructArcs:
                for j in range(i, len(coords)):
                    if j > i and circleEdges[j - 1] >= 0:
                        break
                    # Just walk edge segments until there is an arc
                    if not candidateCircle.addPoint(coords[j]):
                        break

            if candidateCircle.foundCircle is not None and candidateCircle.foundCircle[1] > fromMm(0.25):
                center, radius = candidateCircle.foundCircle
                start, end, mid = candidateCircle.start, candidateCircle.end, candidateCircle.mid

                # We prefer to preserve arc start and end points, adjust center
                # so it is true:
                dir = end - start
                chordLength = np.linalg.norm(dir)
                if chordLength == 0:
                    segments.append(self._constructCircle(center, radius))
                else:
                    dir /= chordLength
                    normal = np.array([dir[1], -dir[0]])
                    chordMidpoint = (start + end) / 2

                    # Due to numerical errors, the height might be invalid, if
                    # so, assume it is zero
                    heightSquared = radius ** 2 - chordLength ** 2 / 4
                    if heightSquared < 0:
                        height = 0
                    else:
                        height = np.sqrt(heightSquared)

                    centerCandidates = [chordMidpoint + normal * height, chordMidpoint - normal * height]
                    center = min(centerCandidates, key=lambda c: np.linalg.norm(c - center))

                    centerToMidpoint = chordMidpoint - center
                    centerToMidpointLength = np.linalg.norm(centerToMidpoint)
                    if centerToMidpointLength == 0:
                        centerToMidpoint = normal
                    else:
                        centerToMidpoint /= np.linalg.norm(centerToMidpoint)
                    middleCandidates = [center + centerToMidpoint * radius, center - centerToMidpoint * radius]
                    arcMiddle = min(middleCandidates, key=lambda c: np.linalg.norm(c - mid))

                    segments.append(self._constructArc(start, arcMiddle, end))

                i += len(candidateCircle) - 1
            else:
                # Yield a line
                a = coords[i]
                b = coords[(i + 1) % len(coords)]
                if np.linalg.norm(np.array(a) - np.array(b)) > 1:
                    segments.append(self._constructEdgeSegment(a, b))
                i += 1
        return segments

    def _constructEdgeSegment(self, a, b):
        segment = pcbnew.PCB_SHAPE()
        segment.SetShape(STROKE_T.S_SEGMENT)
        segment.SetLayer(Layer.Edge_Cuts)
        segment.SetStart(toKiCADPoint(np.rint(a)))
        segment.SetEnd(toKiCADPoint(np.rint(b)))
        return segment

    def _constructArc(self, a, b, c):
        """
        Construct arc based on three points
        """
        arc = pcbnew.PCB_SHAPE()
        arc.SetShape(STROKE_T.S_ARC)
        arc.SetLayer(Layer.Edge_Cuts)
        arc.SetArcGeometry(toKiCADPoint(np.rint(a)), toKiCADPoint(np.rint(b)), toKiCADPoint(np.rint(c)))
        return arc

    def _constructCircle(self, c, r):
        circle = pcbnew.PCB_SHAPE()
        circle.SetShape(STROKE_T.S_CIRCLE)
        circle.SetLayer(Layer.Edge_Cuts)
        circle.SetCenter(toKiCADPoint(c))
        circle.SetRadius(int(r))
        return circle

    def boundingBox(self):
        """
        Return bounding box as BOX2I
        """
        minx, miny, maxx, maxy = self.substrates.bounds
        return pcbnew.BOX2I(
            pcbnew.VECTOR2I(int(minx), int(miny)),
            pcbnew.VECTOR2I(int(maxx - minx), int(maxy - miny)))

    def exterior(self):
        """
        Return a geometry representing the substrate with no holes
        """
        if isinstance(self.substrates, MultiPolygon):
            geoms = self.substrates.geoms
        elif isinstance(self.substrates, Polygon):
            geoms = [self.substrates]
        else:
            raise RuntimeError("Uknown type '{}' of substrate geometry".format(type(self.substrates)))
        polygons = [Polygon(p.exterior) for p in geoms]
        return unary_union(polygons)

    def exteriorRing(self):
        return self.substrates.exterior

    def boundary(self):
        """
        Return shapely geometry representing the outer ring
        """
        return self.substrates.boundary

    def tab(self, origin, direction, width, partitionLine=None,
               maxHeight=pcbnew.FromMM(50), fillet=0):
        """
        Create a tab for the substrate. The tab starts at the specified origin
        (2D point) and tries to penetrate existing substrate in direction (a 2D
        vector). The tab is constructed with given width. If the substrate is
        not penetrated within maxHeight, exception is raised.

        When partitionLine is specified, the tab is extended to the opposite
        side - limited by the partition line. Note that if tab cannot span
        towards the partition line, then the tab is not created - it returns a
        tuple (None, None).

        If a fillet is specified, it allows you to add fillet to the tab of
        specified radius.

        Returns a pair tab and cut outline. Add the tab it via union - batch
        adding of geometry is more efficient.
        """
        self.orient()

        if self.substrates.contains(Point(origin)) and not self.substrates.boundary.contains(Point(origin)):
            raise TabError(origin, direction, ["Tab annotation is placed inside the board. It has to be on edge or outside the board."])

        origin = np.array(origin, dtype=np.float64)
        direction = normalize(direction)
        origin -= direction * float(SHP_EPSILON)
        for geom in listGeometries(self.substrates):
            try:
                sideOriginA = origin + makePerpendicular(direction) * width / 2
                sideOriginB = origin - makePerpendicular(direction) * width / 2
                boundary = closestRing(geom, sideOriginA, direction, maxHeight)
                splitPointA = closestIntersectionPoint(sideOriginA, direction,
                    boundary, maxHeight)
                splitPointB = closestIntersectionPoint(sideOriginB, direction,
                    boundary, maxHeight)
                tabFace = biteBoundary(boundary, splitPointB, splitPointA)
                if partitionLine is None:
                    # There is nothing else to do, return the tab
                    contact = [np.array(p) + direction if fillet else p for p in tabFace.coords]
                    tab = Polygon(contact + [sideOriginA, sideOriginB])
                    return self._makeTabFillet(tab, tabFace, fillet)
                # Span the tab towards the partition line
                # There might be multiple geometries in the partition line, so try them
                # individually.
                direction = -direction
                for p in listGeometries(partitionLine):
                    try:
                        partitionSplitPointA = closestIntersectionPoint(splitPointA.coords[0] - direction * float(SHP_EPSILON),
                                direction, p, maxHeight)
                        partitionSplitPointB = closestIntersectionPoint(splitPointB.coords[0] - direction * float(SHP_EPSILON),
                                direction, p, maxHeight)
                    except NoIntersectionError: # We cannot span towards the partition line
                        continue
                    if isLinestringCyclic(p):
                        candidates = [(partitionSplitPointA, partitionSplitPointB)]
                    else:
                        candidates = [(partitionSplitPointA, partitionSplitPointB),
                            (partitionSplitPointB, partitionSplitPointA)]
                    for i, (spa, spb) in enumerate(candidates):
                        partitionFace = biteBoundary(p, spa, spb)
                        if partitionFace is None:
                            continue
                        partitionFaceCoord = list(partitionFace.coords)
                        if i == 1:
                            partitionFaceCoord = partitionFaceCoord[::-1]
                        # We offset the tab face a little so we can be sure that we
                        # penetrate the board substrate. Otherwise, there is a
                        # numerical instability on small slopes that yields
                        # artifacts on substrate union
                        overlap = 1 if fillet else SHP_EPSILON
                        offsetTabFace = [(p[0] - float(overlap) * direction[0], p[1] - float(overlap) * direction[1]) for p in tabFace.coords]
                        partitionFaceCoord = [(p[0] + float(overlap) * direction[0], p[1] + float(overlap) * direction[1]) for p in partitionFaceCoord]
                        tab = Polygon(offsetTabFace + partitionFaceCoord)
                        return self._makeTabFillet(tab, tabFace, fillet)
                return None, None
            except NoIntersectionError as e:
                continue
            except TabFilletError as e:
                raise TabError(origin, direction, [str(e)]) from e

        raise TabError(origin, direction, [
            "too wide tab so it does not hit the board",
            "annotation is placed inside the board",
            "ray length is not sufficient"
        ])

    def _circleForEdge(self, start, end):
        tolerance = ARC_CHORD_ERROR + GEOMETRY_EPSILON
        for center, radius, _, _, _ in self.circles:
            points = np.array([start, end, (start + end) / 2])
            if np.max(np.abs(np.linalg.norm(points - center, axis=1) - radius)) <= tolerance:
                return center, radius
        return None

    def _filletOnBoundary(self, vertex, u, v, lengths, radius):
        rings = [ring for polygon in listGeometries(self.substrates)
                 for ring in [polygon.exterior, *polygon.interiors]]
        ring = min(rings, key=lambda r: r.distance(Point(vertex)))
        incomingBoard = ring.distance(Point(vertex - u * min(lengths[0] / 2, radius))) <= GEOMETRY_EPSILON
        direction = v if incomingBoard else u
        normal = np.array([direction[1], -direction[0]])
        base = vertex + radius * normal
        available = lengths[1] if incomingBoard else lengths[0]
        coords = np.array(ring.coords)
        segments = np.diff(coords, axis=0)
        segmentLengths = np.linalg.norm(segments, axis=1)
        tangents = segments / segmentLengths[:, None]
        normals = np.column_stack((tangents[:, 1], -tangents[:, 0]))
        offsets = coords[:-1] + radius * normals - base
        cross = direction[0] * tangents[:, 1] - direction[1] * tangents[:, 0]
        distances = np.full(len(segments), np.inf)
        np.divide(offsets[:, 0] * tangents[:, 1] - offsets[:, 1] * tangents[:, 0],
                  cross, out=distances, where=np.abs(cross) > 1e-12)
        valid = np.isfinite(distances)
        centers = base + distances[valid, None] * direction
        contacts = centers - radius * normals[valid]
        along = np.sum((contacts - coords[:-1][valid]) * tangents[valid], axis=1)
        onSegment = (along >= 0) & (along <= segmentLengths[valid])
        candidateCenters = [centers[onSegment]]
        candidateContacts = [contacts[onSegment]]

        # Convex vertices also belong to the offset boundary of a polygon.
        projections = (coords[:-1] - base) @ direction
        perpendicular = coords[:-1] - base - projections[:, None] * direction
        discriminants = radius ** 2 - np.sum(perpendicular ** 2, axis=1)
        valid = discriminants >= 0
        for sign in [-1, 1]:
            distances = projections[valid] + sign * np.sqrt(discriminants[valid])
            candidateCenters.append(base + distances[:, None] * direction)
            candidateContacts.append(coords[:-1][valid])

        centers = np.concatenate(candidateCenters)
        contacts = np.concatenate(candidateContacts)
        along = np.sum((centers - radius * normal - vertex) * direction, axis=1)
        along *= 1 if incomingBoard else -1
        # Pad the prefilter for rounding; the exact contact check below is unchanged.
        nearby = (along >= -2 * GEOMETRY_EPSILON) & (along <= available + 2 * GEOMETRY_EPSILON)
        candidates = list(zip(centers[nearby], contacts[nearby]))
        candidates.sort(key=lambda c: np.linalg.norm(c[0] - vertex))
        boundary = self.substrates.boundary
        line = LineString(ring.coords)
        firstDistance = line.project(Point(vertex))
        for center, contact in candidates:
            linePoint = center - radius * normal
            along = np.dot(linePoint - vertex, direction) * (1 if incomingBoard else -1)
            if not -GEOMETRY_EPSILON <= along <= available + GEOMETRY_EPSILON:
                continue
            if self.substrates.contains(Point(center)):
                continue
            if abs(boundary.distance(Point(center)) - radius) > GEOMETRY_EPSILON:
                continue
            start, end = (contact, linePoint) if incomingBoard else (linePoint, contact)
            a, b = start - center, end - center
            turn = np.arctan2(a[0] * b[1] - a[1] * b[0], np.dot(a, b))
            if turn >= -1e-10:
                continue
            lastDistance = line.project(Point(contact))
            walk = ((firstDistance - lastDistance) if incomingBoard else
                    (lastDistance - firstDistance)) % line.length
            if walk > line.length / 2:
                continue
            if incomingBoard and lastDistance > firstDistance:
                path = list(substring(line, firstDistance, 0).coords) + list(substring(line, line.length, lastDistance).coords)
            elif not incomingBoard and lastDistance < firstDistance:
                path = list(substring(line, firstDistance, line.length).coords) + list(substring(line, 0, lastDistance).coords)
            else:
                path = list(substring(line, firstDistance, lastDistance).coords)
            return start, end, center, turn, path[1:-1], incomingBoard
        raise TabFilletError("Requested fillet does not fit the local board boundary")

    def _filletOnCircle(self, vertex, u, v, lengths, circle, incomingCurve, radius):
        circleCenter, circleRadius = circle
        curveDirection = u if incomingCurve else v
        lineDirection = v if incomingCurve else u
        normal = np.array([lineDirection[1], -lineDirection[0]])
        curveNormal = np.array([curveDirection[1], -curveDirection[0]])
        outside = np.dot(curveNormal, vertex - circleCenter) > 0
        offsetRadius = circleRadius + radius if outside else circleRadius - radius
        if offsetRadius <= 0:
            raise TabFilletError("Fillet radius is too large for the circular contact")
        base = vertex + normal * radius
        projection = np.dot(circleCenter - base, lineDirection)
        perpendicular = base + projection * lineDirection - circleCenter
        discriminant = offsetRadius ** 2 - np.dot(perpendicular, perpendicular)
        if discriminant < 0:
            raise TabFilletError("No tangent fillet fits the circular contact")

        candidates = []
        for sign in [-1, 1]:
            center = base + (projection + sign * np.sqrt(discriminant)) * lineDirection
            linePoint = center - normal * radius
            distance = np.dot(linePoint - vertex, lineDirection)
            available = lengths[1] if incomingCurve else lengths[0]
            alongEdge = distance if incomingCurve else -distance
            if not -GEOMETRY_EPSILON <= alongEdge <= available + GEOMETRY_EPSILON:
                continue
            curvePoint = circleCenter + (center - circleCenter) * circleRadius / offsetRadius
            if self.substrates.boundary.distance(Point(curvePoint)) > ARC_CHORD_ERROR + GEOMETRY_EPSILON:
                continue
            candidates.append((center, linePoint, curvePoint))
        if not candidates:
            raise TabFilletError("Requested fillet does not fit the circular contact")
        center, linePoint, curvePoint = min(candidates, key=lambda c: np.linalg.norm(c[0] - vertex))
        start, end = (curvePoint, linePoint) if incomingCurve else (linePoint, curvePoint)
        a, b = start - center, end - center
        turn = np.arctan2(a[0] * b[1] - a[1] * b[0], np.dot(a, b))
        if turn >= 0:
            raise TabFilletError("Circular fillet would turn outside the tab contact")

        # Follow the existing polygon chords so the wedge shares the board boundary.
        points = np.array([p for polygon in listGeometries(self.substrates)
                           for ring in [polygon.exterior, *polygon.interiors] for p in ring.coords[:-1]])
        onCircle = np.abs(np.linalg.norm(points - circleCenter, axis=1) - circleRadius) <= ARC_CHORD_ERROR + GEOMETRY_EPSILON
        points = points[onCircle]
        angle = np.arctan2(vertex[1] - circleCenter[1], vertex[0] - circleCenter[0])
        lastAngle = np.arctan2(curvePoint[1] - circleCenter[1], curvePoint[0] - circleCenter[0])
        sweep = (lastAngle - angle + np.pi) % (2 * np.pi) - np.pi
        angles = np.arctan2(points[:, 1] - circleCenter[1], points[:, 0] - circleCenter[0])
        progress = ((angles - angle) * np.sign(sweep)) % (2 * np.pi)
        indices = np.argsort(progress)
        path = points[indices[progress[indices] < abs(sweep)]]
        patch = None
        if outside:
            relative = (angles - lastAngle + np.pi) % (2 * np.pi) - np.pi
            before = points[np.argmax(np.where(relative <= 0, relative, -np.inf))]
            after = points[np.argmin(np.where(relative >= 0, relative, np.inf))]
            # Split the original chord at the exact circle/fillet tangency.
            patch = Polygon([before, curvePoint, after])
        return start, end, center, turn, path, patch

    def _makeTabFillet(self, tab: Polygon, tabFace: LineString, fillet: KiLength) \
            -> Tuple[Polygon, LineString]:
        """Add circular fillets tangent to the local board boundary and tab sides."""
        if fillet == 0:
            return tab, tabFace
        if fillet < 0:
            raise TabFilletError("Fillet radius must be positive")
        joined = shapely.ops.orient(self.substrates.union(tab).simplify(GEOMETRY_EPSILON))
        corners = []
        for polygon in listGeometries(joined):
            for ring in [polygon.exterior, *polygon.interiors]:
                coords = np.array(ring.coords[:-1])
                incoming = coords - np.roll(coords, 1, axis=0)
                outgoing = np.roll(coords, -1, axis=0) - coords
                incomingLengths = np.linalg.norm(incoming, axis=1)
                outgoingLengths = np.linalg.norm(outgoing, axis=1)
                valid = np.minimum(incomingLengths, outgoingLengths) > GEOMETRY_EPSILON
                indices = np.flatnonzero(valid)
                us = incoming[valid] / incomingLengths[valid, None]
                vs = outgoing[valid] / outgoingLengths[valid, None]
                crosses = us[:, 0] * vs[:, 1] - us[:, 1] * vs[:, 0]
                for j in np.flatnonzero(crosses < -1e-10):
                    i = indices[j]
                    corners.append((coords[i], us[j], vs[j],
                                    (incomingLengths[i], outgoingLengths[i]), crosses[j],
                                    coords[i - 1], coords[(i + 1) % len(coords)]))

        wedges, circles = [], []
        for endpoint in [tabFace.coords[0], tabFace.coords[-1]]:
            if not corners:
                raise TabFilletError("No concave corner at the tab contact")
            corner = min(corners, key=lambda c: np.linalg.norm(c[0] - endpoint))
            vertex, u, v, lengths, cross, previous, following = corner
            if np.linalg.norm(vertex - endpoint) > 4 * SHP_EPSILON:
                raise TabFilletError("Cannot locate the tab contact corner")
            incomingCircle = self._circleForEdge(previous, vertex)
            outgoingCircle = self._circleForEdge(vertex, following)
            prefix, suffix = [], []
            if incomingCircle is not None or outgoingCircle is not None:
                incomingCurve = incomingCircle is not None
                start, end, center, turn, path, patch = self._filletOnCircle(
                    vertex, u, v, lengths, incomingCircle if incomingCurve else outgoingCircle,
                    incomingCurve, fillet)
                if patch is not None:
                    wedges.append(patch)
                if incomingCurve:
                    prefix = list(path)
                else:
                    suffix = list(reversed(path))
            else:
                turn = np.arctan2(cross, np.dot(u, v))
                setback = fillet * np.tan(-turn / 2)
                if setback > min(lengths) + GEOMETRY_EPSILON:
                    start, end, center, turn, path, incomingBoard = self._filletOnBoundary(
                        vertex, u, v, lengths, fillet)
                    if incomingBoard:
                        prefix = path
                    else:
                        suffix = list(reversed(path))
                else:
                    start, end = vertex - u * setback, vertex + v * setback
                    center = start + fillet * np.array([u[1], -u[0]])
            angle = np.arctan2(start[1] - center[1], start[0] - center[0])
            step = 2 * np.arccos(max(-1, 1 - ARC_CHORD_ERROR / fillet))
            count = max(2, int(np.ceil(-turn / step)) + 1)
            angles = np.linspace(angle, angle + turn, count)
            arc = center + fillet * np.column_stack((np.cos(angles), np.sin(angles)))
            arc[0], arc[-1] = start, end
            # One nanometre of overlap keeps rotated shared edges connected after quantization.
            wedges.append(Polygon([vertex, *prefix, *arc, *suffix]).buffer(1, join_style="mitre"))
            circles.append((center, float(fillet), start, end, turn))

        candidate = shapely.union_all([tab, *wedges], grid_size=1)
        if isinstance(candidate, MultiPolygon) and len(candidate.geoms) == 1:
            candidate = candidate.geoms[0]
        if not isinstance(candidate, Polygon) or not candidate.is_valid:
            raise TabFilletError("Fillets do not form a valid tab")
        # The overlap is for locating the cut on the boundary, not for enlarging the tab.
        newFace = candidate.buffer(1).intersection(self.substrates.boundary)
        if isinstance(newFace, GeometryCollection):
            newFace = MultiLineString([x for x in newFace.geoms if isinstance(x, LineString)])
        if isinstance(newFace, MultiLineString):
            newFace = shapely.ops.linemerge(newFace)
        if not isinstance(newFace, LineString) or newFace.is_empty:
            raise TabFilletError("Fillets do not form a continuous tab contact")
        if Point(tabFace.coords[0]).distance(Point(newFace.coords[0])) > Point(tabFace.coords[0]).distance(Point(newFace.coords[-1])):
            newFace = LineString(reversed(newFace.coords))
        self.circles.extend(circles)
        return candidate, newFace

    def _strPosition(self, point):
        msg = f"[{toMm(point[0])}, {toMm(point[1])}]"
        if self.revertTransformation:
            rp = self.revertTransformation(point)
            msg += f"([{toMm(rp[0])}, {toMm(rp[1])}] in source board)"
        return msg

    def millFillets(self, millRadius):
        """
        Add fillets to inner corners which will be produced by a mill with
        given radius.
        """
        EPS = 1000 # This number is intentionally near KiCAD's resolution of 1nm to not enclose narrow slots, but to preserve radius
        RES = 32
        if millRadius < EPS:
            return
        self.orient()
        self.substrates = self.substrates.buffer(millRadius - EPS, resolution=RES) \
                              .buffer(-millRadius, resolution=RES) \
                              .buffer(EPS, resolution=RES)


    def removeIslands(self):
        """
        Removes all islands - pieces of substrate fully contained within the
        outline of another board
        """
        if isinstance(self.substrates, Polygon):
            return
        mainland = []
        for i, substrate in enumerate(self.substrates.geoms):
            ismainland = True
            for j, otherSubstrate in enumerate(self.substrates.geoms):
                if j == i:
                    continue
                if Polygon(otherSubstrate.exterior.coords).contains(substrate):
                    ismainland = False
                    break
            if ismainland:
                mainland.append(substrate)
        self.substrates = shapely.geometry.collection.GeometryCollection(mainland)
        self.oriented = False

    def isSinglePiece(self):
        """
        Decide whether the substrate consists of a single piece
        """
        return isinstance(self.substrates, Polygon)

    def translate(self, vec):
        """
        Translate substrate by vec
        """
        self.substrates = shapely.affinity.translate(self.substrates, vec[0], vec[1])
        self.partitionLine = shapely.affinity.translate(self.partitionLine, vec[0], vec[1])
        offset = np.array(vec)
        self.circles = [(center + offset, radius, start + offset, end + offset, sweep)
                        for center, radius, start, end, sweep in self.circles]
        for annotation in self.annotations:
            o = annotation.origin
            annotation.origin = (o[0] + vec[0], o[1] + vec[1])

        def newRevertTransformation(point, orig=self.revertTransformation, vec=vec):
            prevPoint = (point[0] - vec[0], point[1] - vec[1])
            if orig is not None:
                return orig(prevPoint)
            return prevPoint
        self.revertTransformation = newRevertTransformation

def showPolygon(polygon):
    import matplotlib.pyplot as plt

    plt.axis('equal')
    x,y = polygon.exterior.xy
    plt.fill(x,y)
    for inter in polygon.interiors:
        x, y = inter.xy
        plt.fill(x, y, color='w')
    plt.show()

def showPolygons(polygons):
    import matplotlib.pyplot as plt

    plt.axis('equal')
    for polygon in polygons:
        x,y = polygon.exterior.xy
        plt.fill(x,y, zorder=1)
        for inter in polygon.interiors:
            x2, y2 = inter.xy
            plt.fill(x2, y2, color="w")
    plt.show()

class SubstrateNeighbors:
    """
    Thin wrapper around BoxNeighbors for finding substrate pieces' neighbors.
    """
    def __init__(self, substrates):
        self._revMap = { id(s): s for s in substrates }
        self._neighbors = BoxNeighbors( { id(s): s.bounds() for s in substrates })

    def _reverse(self, queryRes):
        return [self._revMap[ x ] for x in queryRes]

    def _reverseC(self, queryRes):
        return [(self._revMap[ x ], shadow) for x, shadow in queryRes]

    def left(self, s):
        return self._reverse(self._neighbors.left(id(s)))

    def leftC(self, s):
        return self._reverseC(self._neighbors.leftC(id(s)))

    def right(self, s):
        return self._reverse(self._neighbors.right(id(s)))

    def rightC(self, s):
        return self._reverseC(self._neighbors.rightC(id(s)))

    def bottom(self, s):
        return self._reverse(self._neighbors.bottom(id(s)))

    def bottomC(self, s):
        return self._reverseC(self._neighbors.bottomC(id(s)))

    def top(self, s):
        return self._reverse(self._neighbors.top(id(s)))

    def topC(self, s):
        return self._reverseC(self._neighbors.topC(id(s)))

class SubstratePartitionLines:
    """
    Thin wrapper around BoxPartitionLines for finding substrate pieces'
    partition lines. It allows you to specify ghost substrates. No partition
    line is formed between two ghost substrates.
    """
    def __init__(self, substrates, ghostSubstrates=[],
                 safeHorizontalMargin=0, safeVerticalMargin=0):
        boxes = {id(s): s.bounds() for s in chain(substrates, ghostSubstrates)}
        ghosts = set([id(s) for s in ghostSubstrates])
        SEED_LIMIT_SIZE = pcbnew.FromMM(0.01)
        def seedFilter(idA, idB, v, l):
            if l.length < SEED_LIMIT_SIZE:
                return False
            return idA not in ghosts or idB not in ghosts
        self._partition = BoxPartitionLines(
            self._preprocessBoxes(boxes),
            seedFilter,
            safeHorizontalMargin, safeVerticalMargin)

    def _preprocessBoxes(self, boxes):
        """
        BoxPartitionLines assumes non-overlapping boxes. However, when we
        specify zero spacing, the boxes share an edge which violates the initial
        condition. It is safe to shrink the boxes if they are not the outer-most
        edges.
        """
        minx = min(map(lambda x: x[0], boxes.values()))
        miny = min(map(lambda x: x[1], boxes.values()))
        maxx = max(map(lambda x: x[2], boxes.values()))
        maxy = min(map(lambda x: x[3], boxes.values()))

        newBoxes = {}
        for i, b in boxes.items():
            newBoxes[i] = (
                b[0] + SHP_EPSILON if b[0] != minx else minx,
                b[1] + SHP_EPSILON if b[1] != miny else miny,
                b[2] - SHP_EPSILON if b[2] != maxx else maxx,
                b[3] - SHP_EPSILON if b[3] != maxy else maxy
            )
        return newBoxes

    @property
    def query(self):
        return self._partition.query

    def partitionSubstrate(self, substrate):
        return self._partition.partitionLines(id(substrate))

