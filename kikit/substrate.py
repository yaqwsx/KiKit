from shapely import geometry
from shapely.geometry import (Polygon, MultiPolygon, LineString,
    MultiLineString, LinearRing, Point)
from shapely.geometry.collection import GeometryCollection
from shapely.ops import orient, unary_union, split, nearest_points
import shapely
import numpy as np
from kikit.intervals import Interval, BoxNeighbors, BoxPartitionLines
from pcbnewTransition import pcbnew, isV6
from enum import IntEnum
from itertools import product

from typing import List, Tuple, Union

from kikit.common import *

from kikit.defs import STROKE_T, Layer

class PositionError(RuntimeError):
    def __init__(self, message, point):
        super().__init__(message.format(toMm(point[0]), toMm(point[1])))
        self.point = point
        self.origMessage = message

class NoIntersectionError(RuntimeError):
    def __init__(self, message, point):
        super().__init__(message)
        self.point = point

def roundPoint(point, precision=-4):
    return (round(point[0], precision), round(point[1], precision))
    return pcbnew.wxPoint(round(point[0], precision), round(point[1], precision))

def getStartPoint(geom):
    if isV6():
        if geom.GetShape() == STROKE_T.S_CIRCLE:
            # Circle start is circle center /o\
            point = geom.GetStart() + pcbnew.wxPoint(geom.GetRadius(), 0)
        elif geom.GetShape() == STROKE_T.S_RECT:
            point = geom.GetStart()
        else:
            point = geom.GetStart()
        return roundPoint(point)

    if geom.GetShape() in [STROKE_T.S_ARC, STROKE_T.S_CIRCLE]:
        return roundPoint(geom.GetArcStart())
    return roundPoint(geom.GetStart())

def getEndPoint(geom):
    if isV6():
        if geom.GetShape() == STROKE_T.S_CIRCLE:
            # Circle start is circle center /o\
            point = geom.GetStart() + pcbnew.wxPoint(geom.GetRadius(), 0)
        elif geom.GetShape() == STROKE_T.S_RECT:
            # Rectangle is closed, so it starts at the same point as it ends
            point = geom.GetStart()
        else:
            point = geom.GetEnd()
        return roundPoint(point)

    if geom.GetShape() == STROKE_T.S_ARC:
        return roundPoint(geom.GetArcEnd())
    if geom.GetShape() == STROKE_T.S_CIRCLE:
        return roundPoint(geom.GetArcStart())
    return roundPoint(geom.GetEnd())

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
    if getStartPoint(geometryList[startIdx]) == getEndPoint(geometryList[startIdx]):
        return ring
    currentPoint = getEndPoint(geometryList[startIdx])
    while True:
        nextIdx = coincidencePoints[currentPoint].getNeighbor(ring[-1])
        assert(unused[nextIdx] or nextIdx == startIdx)
        if currentPoint == getStartPoint(geometryList[nextIdx]):
            currentPoint = getEndPoint(geometryList[nextIdx])
        else:
            currentPoint = getStartPoint(geometryList[nextIdx])
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
    return g.GetShape() != pcbnew.S_SEGMENT or g.GetLength() > 0

def extractRings(geometryList):
    """
    Walks a list of PCB_SHAPE entities and produces a lists of continuous
    rings returned as list of list of indices from the geometryList.
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
    if aStart == bStart or aStart == bEnd:
        return aStart
    return aEnd

def approximateArc(arc, endWith):
    """
    Take DRAWINGITEM and approximate it using lines
    """
    SEGMENTS_PER_FULL= 4 * 32 # To Be consistent with default shapely settings
    startAngle = arc.GetArcAngleStart() / 10
    if arc.GetShape() == STROKE_T.S_CIRCLE:
        endAngle = startAngle + 360
        segments = SEGMENTS_PER_FULL
    else:
        endAngle = startAngle + arc.GetArcAngle() / 10
        segments = abs(int((endAngle - startAngle) * SEGMENTS_PER_FULL // 360))
    # Ensure a minimal number of segments for small angle section of arcs
    segments = max(segments, 12)
    theta = np.radians(np.linspace(startAngle, endAngle, segments))
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

    This is more-less inspired by the KiCAD code as KiCAD does not export the
    relevant functions
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
    outline.append(end)

    endWith = np.array(endWith)
    first = np.array([outline[0][0], outline[0][1]])
    last = np.array([outline[-1][0], outline[-1][1]])
    if (np.linalg.norm(endWith - first) < np.linalg.norm(endWith - last)):
        outline.reverse()

    return outline

def createRectangle(rect):
    """
    Take PCB_SHAPE and convert it into outline
    """
    tl = rect.GetStart()
    br = rect.GetEnd()
    return [tl, (br[0], tl[1]), br, (tl[0], br[1]), tl]

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
    Take a list indices representing a ring from PCB_SHAPE entities and
    convert them into a shapely polygon. The segments are expected to be
    continuous. Arcs & other are broken down into lines.
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
            outline += createRectangle(geometryList[idxA])
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

def commonCircleKiCAD(a, b, c):
    """
    Get a common circle using KiCAD APIs (a little abusive)
    """
    arc = pcbnew.PCB_SHAPE()
    arc.SetShape(STROKE_T.S_ARC)
    arc.SetArcGeometry(wxPoint(*a), wxPoint(*b), wxPoint(*c))
    center = [int(x) for x in arc.GetCenter()]
    mid = [(a[i] + b[i]) // 2 for i in range(2)]
    if center == mid:
        return None
    return roundPoint(center, -8)

def commonCirclePython(a, b, c):
    """
    Get a common circle using pure Python implementation
    """
    o_l = [(a[i] + b[i]) / 2 for i in range(2)]
    o_r = [(b[i] + c[i]) / 2 for i in range(2)]
    d_l = [(b[i] - a[i]) for i in range(2)]
    d_r = [(c[i] - b[i]) for i in range(2)]
    n_l = (d_l[1], -d_l[0])
    n_r = (d_r[1], -d_r[0])

    t_denom = n_l[0] * n_r[1] - n_l[1] * n_r[0]
    if t_denom == 0:
        return None # The normal vectors are parallel
    t = (n_r[0] * (o_l[1] - o_r[1]) + n_r[1] * (o_r[1] - o_l[1])) / t_denom
    intersection = [o_l[i] + n_l[i] * t for i in range(2)]
    return roundPoint(intersection)


def commonCircle(a, b, c):
    """
    Given three 2D points return (x, y, r) of the circle they lie on or None if
    they lie in a line
    """
    # We use the KiCAD's API implementation as it seems faster, but v5 doesn't
    # offer it
    if isV6():
        return commonCircleKiCAD(a, b, c)
    return commonCirclePython(a, b, c)


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
    testLine = LineString([origin, origin + direction * maxDistance])
    inter = testLine.intersection(outline)
    if inter.is_empty:
        raise NoIntersectionError(f"No intersection found within given distance", origin)
    origin = Point(origin[0], origin[1])
    if isinstance(inter, Point):
        geoms = [inter]
    else:
        geoms = inter.geoms
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
        self.substrates = self.substrates.buffer(bufferDistance)
        if not self.substrates.is_empty:
            self.substrates = shapely.ops.orient(self.substrates)
        self.partitionLine = shapely.geometry.GeometryCollection()
        self.annotations = []
        self.oriented = True
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
        self.substrates = shapely.ops.orient(self.substrates)
        self.oriented = True

    def bounds(self):
        """
        Return shapely bounds of substrates
        """
        return self.substrates.bounds

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
        coords = ring.coords
        segments = []
        if coords[0] != coords[-1]:
            raise RuntimeError("Ring is incomplete")
        i = 0
        while i < len(coords):
            j = i # in the case the following cycle never happens
            if reconstructArcs:
                for j in range(i, len(coords) - 3): # Just walk until there is an arc
                    cc1 = commonCircle(coords[j], coords[j + 1], coords[j + 2])
                    cc2 = commonCircle(coords[j + 1], coords[j + 2], coords[j + 3])
                    if cc1 is None or cc2 is None or cc1 != cc2:
                        break
            if j - i > 10:
                j += 2
                # Yield a circle
                a = coords[i]
                b = coords[(i + j) // 2]
                c = coords[j]
                segments.append(self._constructArc(a, b, c))
                i = j
            else:
                # Yield a line
                a = coords[i]
                b = coords[(i + 1) % len(coords)]
                segments.append(self._constructEdgeSegment(a, b))
                i += 1
        return segments

    def _constructEdgeSegment(self, a, b):
        segment = pcbnew.PCB_SHAPE()
        segment.SetShape(STROKE_T.S_SEGMENT)
        segment.SetLayer(Layer.Edge_Cuts)
        segment.SetStart(wxPoint(*a))
        segment.SetEnd(wxPoint(*b))
        return segment

    def _constructArc(self, a, b, c):
        """
        Construct arc based on three points
        """
        arc = pcbnew.PCB_SHAPE()
        arc.SetShape(STROKE_T.S_ARC)
        arc.SetLayer(Layer.Edge_Cuts)
        arc.SetArcGeometry(wxPoint(*a), wxPoint(*b), wxPoint(*c))
        return arc

    def boundingBox(self):
        """
        Return bounding box as wxRect
        """
        minx, miny, maxx, maxy = self.substrates.bounds
        return pcbnew.wxRect(int(minx), int(miny), int(maxx - minx), int(maxy - miny))

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

    def boundary(self):
        """
        Return shapely geometry representing the outer ring
        """
        return self.substrates.boundary

    def tab(self, origin, direction, width, partitionLine=None,
               maxHeight=pcbnew.FromMM(50)):
        """
        Create a tab for the substrate. The tab starts at the specified origin
        (2D point) and tries to penetrate existing substrate in direction (a 2D
        vector). The tab is constructed with given width. If the substrate is
        not penetrated within maxHeight, exception is raised.

        When partitionLine is specified, tha tab is extended to the opposite
        side - limited by the partition line. Note that if tab cannot span
        towards the partition line, then the the tab is not created - it returns
        a tuple (None, None).

        Returns a pair tab and cut outline. Add the tab it via union - batch
        adding of geometry is more efficient.
        """
        self.orient()

        origin = np.array(origin)
        try:
            direction = normalize(direction)
            sideOriginA = origin + makePerpendicular(direction) * width / 2
            sideOriginB = origin - makePerpendicular(direction) * width / 2
            boundary = self.substrates.exterior
            splitPointA = closestIntersectionPoint(sideOriginA, direction,
                boundary, maxHeight)
            splitPointB = closestIntersectionPoint(sideOriginB, direction,
                boundary, maxHeight)
            tabFace = biteBoundary(boundary, splitPointB, splitPointA)
            if partitionLine is None:
                # There is nothing else to do, return the tab
                tab = Polygon(list(tabFace.coords) + [sideOriginA, sideOriginB])
                return tab, tabFace
            # Span the tab towwards the partition line
            # There might be multiple geometries in the partition line, so try them
            # individually.
            direction = -direction
            for p in listGeometries(partitionLine):
                try:
                    partitionSplitPointA = closestIntersectionPoint(splitPointA.coords[0],
                            direction, p, maxHeight)
                    partitionSplitPointB = closestIntersectionPoint(splitPointB.coords[0],
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
                    tab = Polygon(list(tabFace.coords) + partitionFaceCoord)
                    return tab, tabFace
            return None, None
        except NoIntersectionError as e:
            message = "Cannot create tab:\n"
            message += f"  Annotation position {self._strPosition(origin)}\n"
            message += f"  Tab ray origin that failed: {self._strPosition(origin)}\n"
            message += "Possible causes:\n"
            message += "- too wide tab so it does not hit the board,\n"
            message += "- annotation is placed inside the board,\n"
            message += "- ray length is not sufficient,\n"
            raise RuntimeError(message)

    def _strPosition(self, point):
        msg = f"[{toMm(point[0])}, {toMm(point[1])}]"
        if self.revertTransformation:
            rp = self.revertTransformation(point)
            msg += f"([{toMm(rp[0])}, {toMm(rp[1])}] in source board)"
        return msg

    def millFillets(self, millRadius):
        """
        Add fillets to inner conernes which will be produced a by mill with
        given radius.
        """
        EPS = fromMm(0.01)
        RES = 32
        if millRadius < EPS:
            return
        self.orient()
        self.substrates = self.substrates.buffer(millRadius - EPS, resolution=RES) \
                              .buffer(-millRadius, resolution=RES) \
                              .buffer(EPS, resolution=RES)


    def removeIslands(self):
        """
        Removes all islads - pieces of substrate fully contained within outline
        of another board
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
            boxes,
            seedFilter,
            safeHorizontalMargin, safeVerticalMargin)

    @property
    def query(self):
        return self._partition.query

    def partitionSubstrate(self, substrate):
        return self._partition.partitionLines(id(substrate))

