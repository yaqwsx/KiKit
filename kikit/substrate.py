from shapely import geometry
from shapely.geometry import (Polygon, MultiPolygon, LineString,
    MultiLineString, LinearRing, Point)
from shapely.geometry.collection import GeometryCollection
from shapely.ops import orient, unary_union, split, nearest_points
import shapely
import json
import numpy as np
from kikit.intervals import Interval, BoxNeighbors, BoxPartitionLines
from pcbnewTransition import pcbnew
from enum import IntEnum
from itertools import product

from typing import Iterable, List, Tuple, Union

from kikit.common import *
from kikit.units import deg
from kikit.defs import STROKE_T, Layer

TABFAIL_VISUAL = False

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
    SEGMENTS_PER_FULL= 4 * 32 # To Be consistent with default shapely settings

    startAngle = EDA_ANGLE(0, pcbnew.DEGREES_T)
    endAngle = EDA_ANGLE(0, pcbnew.DEGREES_T)
    arc.CalcArcAngles(startAngle, endAngle)
    if arc.GetShape() == STROKE_T.S_CIRCLE:
        endAngle = startAngle + 360 * deg
        segments = SEGMENTS_PER_FULL
    else:
        segments = abs(int((endAngle.AsDegrees() - startAngle.AsDegrees()) * SEGMENTS_PER_FULL // 360))
    # Ensure a minimal number of segments for small angle section of arcs
    segments = max(segments, 12)
    theta = np.linspace(startAngle.AsRadians(), endAngle.AsRadians(), segments)
    x = arc.GetCenter()[0] + arc.GetRadius() * np.cos(theta)
    y = arc.GetCenter()[1] + arc.GetRadius() * np.sin(theta)
    outline = list(np.column_stack([x, y]))

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

    CURVE_POINTS = 4 * 32 - 2
    dt = 1.0 / CURVE_POINTS

    start = np.array(bezier.GetStart())
    if hasattr(bezier, "GetBezierC1"):
      bc1 = np.array(bezier.GetBezierC1())
      bc2 = np.array(bezier.GetBezierC2())
    else:
      bc1 = np.array(bezier.GetBezControl1())
      bc2 = np.array(bezier.GetBezControl2())
    end = np.array(bezier.GetEnd())

    degenerated = (start == bc1).all() and (bc2 == end).all()

    outline = [start]
    if not degenerated:
        for i in range(CURVE_POINTS):
            t = dt * i
            vertex = (1 - t) ** 3 * start + \
                     3 * t * (1 - t) ** 2 * bc1 + \
                     3 * t ** 2 * (1 - t) * bc2 + \
                     t ** 3 * end
            outline.append(vertex)
    else:
        outline += [start, end]
    outline.append(end)

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
            kHole = p.Hole(hIdx)
            assert kHole.isClosed()
            holes.append(shapeLinechainToList(kHole))
        polygons.append(Polygon(outline, holes=holes))
    if len(polygons) == 1:
        return polygons[0]
    return MultiPolygon(polygons=polygons)


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
            outline += geometryList[idxA].GetRectCorners()
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
            points = [np.array([x, y]) for x, y in zip(self._xs, self._ys)]
            toRevalidate = list(zip(points, points[1:]))
        else:
            toRevalidate = [(np.array([self._xs[-2], self._ys[-2]]), np.array([self._xs[-1], self._ys[-1]]))]

        if self._doLinesFitCircle(toRevalidate, newCenter, newRadius) and newRadius < self.radius_limit:
            self.foundCircle = newCenter, newRadius
            return True

        self._popLast()
        return False

    def _doLinesFitCircle(self, lines: Iterable[Tuple[np.array, np.array]],
                          c: np.array, r: float) -> bool:
        for start, end in lines:
            # We don't use list of candidates in this as it is in the hot path
            # and constructing the list of candidates adds a significant
            # overhead (both technically, and for early return)
            #
            # The extreme occurs either in one of the endpoints or in the
            # projection of center of the circle to the line (if it lies on the
            # segment).
            if np.abs(np.linalg.norm(start - c) - r) > self.tolerance:
                return False
            if np.abs(np.linalg.norm(end - c) - r) > self.tolerance:
                return False

            # Project center to the line; if it doesn't fit line, continue
            ap = c - start
            ab = end - start
            t = np.dot(ap, ab) / np.dot(ab, ab)
            if t < 0 or t > 1:
                continue
            projection = start + t * ab
            if np.abs(np.linalg.norm(projection - c) - r) > self.tolerance:
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
        Zi = Xi * Xi + Yi * Yi

        # compute moments
        Mxy = (Xi * Yi).sum() / n
        Mxx = (Xi * Xi).sum() / n
        Myy = (Yi * Yi).sum() / n
        Mxz = (Xi * Zi).sum() / n
        Myz = (Yi * Zi).sum() / n
        Mzz = (Zi * Zi).sum() / n

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
            xnew = X - Y / Dy
            if xnew == X or not np.isfinite(xnew):
                break
            ynew = A0 + xnew * (A1 + xnew * (A2 + 4. * xnew * xnew))
            if abs(ynew) >= abs(Y):
                break
            X, Y = xnew, ynew

        det = X ** 2 - X * Mz + Cov_xy
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
        self.substrates = self.substrates.simplify(SHP_EPSILON)
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
            self.substrates = unary_union([self.substrates] + other)
        elif isinstance(other, Substrate):
            self.substrates = unary_union([self.substrates, other.substrates])
        else:
            self.substrates = unary_union([self.substrates, other])
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
        if isinstance(self.substrates, MultiPolygon) or isinstance(self.substrates, GeometryCollection):
            geoms = self.substrates.geoms
        elif isinstance(self.substrates, Polygon):
            geoms = [self.substrates]
        else:
            raise RuntimeError("Uknown type '{}' of substrate geometry".format(type(self.substrates)))
        items = []
        for polygon in geoms:
            items += self._serializeRing(polygon.exterior, reconstructArcs)
            for interior in polygon.interiors:
                items += self._serializeRing(interior, reconstructArcs)
        return items

    def _serializeRing(self, ring, reconstructArcs):
        TOLERANCE = fromMm(0.01)
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

        segments = []
        i = 0
        while i < len(coords):
            j = i # in the case the following cycle never happens
            candidateCircle = CircleFitCandidates(tolerance=TOLERANCE)
            if reconstructArcs:
                for j in range(i, len(coords)):
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

                    segments.append(self._constructArc(toKiCADPoint(start), toKiCADPoint(arcMiddle), toKiCADPoint(end)))

                i += len(candidateCircle) - 1
            else:
                # Yield a line
                a = coords[i]
                b = coords[(i + 1) % len(coords)]
                if np.linalg.norm(np.array(a) - np.array(b)) > SHP_EPSILON:
                    segments.append(self._constructEdgeSegment(a, b))
                i += 1
        return segments

    def _constructEdgeSegment(self, a, b):
        segment = pcbnew.PCB_SHAPE()
        segment.SetShape(STROKE_T.S_SEGMENT)
        segment.SetLayer(Layer.Edge_Cuts)
        segment.SetStart(toKiCADPoint(a))
        segment.SetEnd(toKiCADPoint(b))
        return segment

    def _constructArc(self, a, b, c):
        """
        Construct arc based on three points
        """
        arc = pcbnew.PCB_SHAPE()
        arc.SetShape(STROKE_T.S_ARC)
        arc.SetLayer(Layer.Edge_Cuts)
        arc.SetArcGeometry(toKiCADPoint(a), toKiCADPoint(b), toKiCADPoint(c))
        return arc

    def _constructCircle(self, c, r):
        circle = pcbnew.PCB_SHAPE()
        circle.SetShape(STROKE_T.S_CIRCLE)
        circle.SetLayer(Layer.Edge_Cuts)
        circle.SetCenter(toKiCADPoint(c))
        if isV8():
            circle.SetRadius(int(r))
        else:
            circle.SetEnd(toKiCADPoint(c + np.array([r, 0])))
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
        direction = np.around(normalize(direction), 4)
        origin -= direction * float(SHP_EPSILON)
        for geom in listGeometries(self.substrates):
            try:
                sideOriginA = origin + makePerpendicular(direction) * width / 2
                sideOriginB = origin - makePerpendicular(direction) * width / 2
                boundary = geom.exterior
                splitPointA = closestIntersectionPoint(sideOriginA, direction,
                    boundary, maxHeight)
                splitPointB = closestIntersectionPoint(sideOriginB, direction,
                    boundary, maxHeight)
                tabFace = biteBoundary(boundary, splitPointB, splitPointA)
                if partitionLine is None:
                    # There is nothing else to do, return the tab
                    tab = Polygon(list(tabFace.coords) + [sideOriginA, sideOriginB])
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
                        offsetTabFace = [(p[0] - float(SHP_EPSILON) * direction[0], p[1] - float(SHP_EPSILON) * direction[1]) for p in tabFace.coords]
                        partitionFaceCoord = [(p[0] + float(SHP_EPSILON) * direction[0], p[1] + float(SHP_EPSILON) * direction[1]) for p in partitionFaceCoord]
                        tab = Polygon(offsetTabFace + partitionFaceCoord)
                        return self._makeTabFillet(tab, tabFace, fillet)
                return None, None
            except NoIntersectionError as e:
                continue
            except TabFilletError as e:
                raise TabError(origin, direction, ["This is a bug. Please open an issue and provide the board on which the fillet failed."])

        raise TabError(origin, direction, [
            "too wide tab so it does not hit the board",
            "annotation is placed inside the board",
            "ray length is not sufficient"
        ])

    def _makeTabFillet(self, tab: Polygon, tabFace: LineString, fillet: KiLength) \
            -> Tuple[Polygon, LineString]:
        if fillet == 0:
            return tab, tabFace
        joined = self.substrates.union(tab)
        RESOLUTION = 64
        rounded = joined.buffer(fillet, resolution=RESOLUTION).buffer(-fillet, resolution=RESOLUTION)
        remainder = rounded.difference(self.substrates,)

        if isinstance(remainder, MultiPolygon) or isinstance(remainder, GeometryCollection):
            geoms = remainder.geoms
        elif isinstance(remainder, Polygon):
            geoms = [remainder]
        else:
            raise RuntimeError("Uknown type '{}' of substrate geometry".format(type(remainder)))
        candidates = [x for x in geoms if x.intersects(tab)]
        if len(candidates) != 1:
            raise TabFilletError(f"Unexpected number of fillet candidates: {len(candidates)}")
        # Shapely is numerically unstable for this, bloat the polygon slighlty
        # to ensure there is an intersection
        candidate = candidates[0].buffer(SHP_EPSILON)

        newFace = candidate.intersection(self.substrates.exterior)
        if isinstance(newFace, GeometryCollection):
            newFace = MultiLineString([x for x in newFace.geoms if not isinstance(x, Polygon)])
        if isinstance(newFace, MultiLineString):
            newFace = shapely.ops.linemerge(newFace)
        if not isinstance(newFace, LineString):
            raise TabFilletError(f"Unexpected result of filleted tab face: {type(newFace)}, {json.dumps(shapely.geometry.mapping(newFace), indent=4)}")
        if Point(tabFace.coords[0]).distance(Point(newFace.coords[0])) > Point(tabFace.coords[0]).distance(Point(newFace.coords[-1])):
            newFace = LineString(reversed(newFace.coords))
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

