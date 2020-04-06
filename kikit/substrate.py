from shapely.geometry import Polygon, MultiPolygon, LineString, MultiLineString, Point
from shapely.ops import unary_union, split
import shapely
import numpy as np
import pcbnew
from enum import IntEnum
from itertools import product

from kikit.defs import STROKE_T, Layer

def toTuple(item):
    if isinstance(item, pcbnew.wxPoint):
        return item[0], item[1]
    raise NotImplementedError("toTuple for {} not implemented".format(type(item)))

def getStartPoint(geom):
    if geom.GetShape() in [STROKE_T.S_ARC, STROKE_T.S_CIRCLE]:
        return geom.GetArcStart()
    return geom.GetStart()

def getEndPoint(geom):
    if geom.GetShape() == STROKE_T.S_ARC:
        return geom.GetArcEnd()
    if geom.GetShape() == STROKE_T.S_CIRCLE:
        return geom.GetArcStart()
    return geom.GetEnd()

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
    if geometryList[startIdx].GetStart() == geometryList[startIdx].GetEnd():
        return ring
    currentPoint = geometryList[startIdx].GetEnd()
    while True:
        nextIdx = coincidencePoints[toTuple(currentPoint)].getNeighbor(ring[-1])
        assert(unused[nextIdx] or nextIdx == startIdx)
        if currentPoint == getStartPoint(geometryList[nextIdx]):
            currentPoint = getEndPoint(geometryList[nextIdx])
        else:
            currentPoint = getStartPoint(geometryList[nextIdx])
        unused[nextIdx] = False
        if nextIdx == startIdx:
            return ring
        ring.append(nextIdx)

def extractRings(geometryList):
    """
    Walks a list of DRAWSEGMENT entities and produces a lists of continuous
    rings returned as list of list of indices from the geometryList.
    """
    coincidencePoints = {}
    for i, geom in enumerate(geometryList):
        start = toTuple(getStartPoint(geom))
        coincidencePoints.setdefault(start, CoincidenceList()).append(i)
        end = toTuple(getEndPoint(geom))
        coincidencePoints.setdefault(end, CoincidenceList()).append(i)
    for point, items in coincidencePoints.items():
        if len(items) != 2:
            raise RuntimeError("Wrong number of entities ({}) at [{}, {}]".format(
                len(items), pcbnew.ToMM(point[0]), pcbnew.ToMM(point[1])
            ))

    rings = []
    unused = [True] * len(geometryList)
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
    SEGMENTS_PER_FULL= 4 * 16 # To Be consistent with default shapely settings
    startAngle = arc.GetArcAngleStart() / 10
    if arc.GetShape() == STROKE_T.S_CIRCLE:
        endAngle = startAngle + 360
        segments = SEGMENTS_PER_FULL
    else:
        endAngle = startAngle + arc.GetAngle() / 10
        segments = abs(int((endAngle - startAngle) * SEGMENTS_PER_FULL // 360))
    theta = np.radians(np.linspace(startAngle, endAngle, segments))
    x = arc.GetCenter()[0] + arc.GetRadius() * np.cos(theta)
    y = arc.GetCenter()[1] + arc.GetRadius() * np.sin(theta)
    outline = list(np.column_stack([x, y]))
    last = outline[-1][0], outline[-1][1]
    if (not np.isclose(last[0], endWith[0], atol=pcbnew.FromMM(0.001)) or
        not np.isclose(last[1], endWith[1], atol=pcbnew.FromMM(0.001))):
        outline.reverse()
    return outline

def toShapely(ring, geometryList):
    """
    Take a list indices representing a ring from DRAWSEGMENT entities and
    convert them into a shapely polygon. The segments are expected to be
    continuous. Arcs & other are broken down into lines.
    """
    outline = []
    for idxA, idxB in zip(ring, ring[1:] + ring[:1]):
        if geometryList[idxA].GetShape() in [STROKE_T.S_ARC, STROKE_T.S_CIRCLE]:
            outline += approximateArc(geometryList[idxA],
                commonEndPoint(geometryList[idxA], geometryList[idxB]))[1:]
        else:
            outline.append(commonEndPoint(geometryList[idxA], geometryList[idxB]))
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

def commonCircle(a, b, c):
    """
    Given three 2D points return (x, y, r) of the circle they lie on or None if
    they lie in a line
    """
    # Based on http://web.archive.org/web/20161011113446/http://www.abecedarical.com/zenosamples/zs_circle3pts.html
    m11 = np.matrix([[a[0], a[1], 1],
                     [b[0], b[1], 1],
                     [c[0], c[1], 1]])
    m11d = np.linalg.det(m11)
    if m11d == 0:
        return None
    m12 = np.matrix([[a[0]*a[0] + a[1]*a[1], a[1], 1],
                     [b[0]*b[0] + b[1]*b[1], b[1], 1],
                     [c[0]*c[0] + c[1]*c[1], c[1], 1]])
    m13 = np.matrix([[a[0]*a[0] + a[1]*a[1], a[0], 1],
                     [b[0]*b[0] + b[1]*b[1], b[0], 1],
                     [c[0]*c[0] + c[1]*c[1], c[0], 1]])
    m14 = np.matrix([[a[0]*a[0] + a[1]*a[1], a[0], a[1]],
                     [b[0]*b[0] + b[1]*b[1], b[0], b[1]],
                     [c[0]*c[0] + c[1]*c[1], c[0], c[1]]])
    x = 0.5 * np.linalg.det(m12) / m11d
    y = -0.5 * np.linalg.det(m13) / m11d
    r = np.sqrt(x*x + y*y + np.linalg.det(m14) / m11d)
    return (x, y, r)

def cutOutline(point, linestring):
    """
    Given a point finds an entity in (multi)linestring which goes through the
    point. Then returns the string starting and ending in that point
    """
    LEN_LIMIT = 40 # Should be roughly equal to half the circular segments,
                    # may prevent from finding a solution
    if isinstance(linestring, LineString):
        geom = [linestring]
    elif isinstance(linestring, MultiLineString):
        geom = linestring.geoms
    else:
        raise RuntimeError("Unknown geometry '{}' passed".format(type(linestring)))
    for string in geom:
        if not string.intersects(point):
            continue
        splitted = split(string, point)
        if len(splitted) > 1:
            string = LineString(list(splitted[1].coords) + splitted[0].coords[1:])
        else:
            string = splitted[0]
        limit1 = max(1, len(string.coords) - LEN_LIMIT)
        limit2 = min(LEN_LIMIT, len(string.coords) - 1)
        return LineString(string.coords[limit1:]), LineString(string.coords[:limit2])
    return None, None

def extractPoint(collection):
    """
    Given a geometry collection, return first point if it. None if no point in
    the collection
    """
    if isinstance(collection, LineString):
        return None
    if isinstance(collection, Point):
        return collection
    for x in collection:
        if isinstance(x, Point):
            return x
    return None

class Substrate:
    """
    Represents (possibly multiple) PCB substrates reconstructed from a list of
    geometry
    """
    def __init__(self, geometryList):
        polygons = [toShapely(ring, geometryList) for ring in extractRings(geometryList)]
        self.substrates = unary_union(substratesFrom(polygons))

    def union(self, other):
        """
        Appends a substrate or a polygon. If there is a common intersection,
        with existing substrate, it will be merged into a single substrate.
        """
        if isinstance(other, Substrate):
            self.substrates = unary_union([self.substrates, other.substrates])
        else:
            self.substrates = unary_union([self.substrates, other])
        self.substrates = shapely.ops.orient(self.substrates)

    def serialize(self):
        """
        Produces a list of DRAWSEGMENT on the Edge.Cuts layer
        """
        if isinstance(self.substrates, MultiPolygon):
            geoms = self.substrates.geoms
        elif isinstance(self.substrates, Polygon):
            geoms = [self.substrates]
        else:
            raise RuntimeError("Uknown type '{}' of substrate geometry".format(type(self.substrates)))
        items = []
        for polygon in geoms:
            items += self._serializeRing(polygon.exterior)
            for interior in polygon.interiors:
                items += self._serializeRing(interior)
        return items

    def _serializeRing(self, ring):
        coords = list(ring.coords)
        segments = []
        # ToDo: Reconstruct arcs
        for a, b in zip(coords, coords[1:]):
            segment = pcbnew.DRAWSEGMENT()
            segment.SetShape(STROKE_T.S_SEGMENT)
            segment.SetLayer(Layer.Edge_Cuts)
            segment.SetStart(pcbnew.wxPoint(a[0], a[1]))
            segment.SetEnd(pcbnew.wxPoint(b[0], b[1]))
            segments.append(segment)
        return segments

    def boundingBox(self):
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
        return self.substrates.boundary

    def fillet(self, point, radius):
        """
        Add a fillet to the substrate at given point. If the point does not lie
        on an inner corner or the surrounding geometry does not allow for fillet,
        does nothing. Return true if the fillet was created, else otherwise
        """
        if radius == 0:
            return
        cut1, cut2 = cutOutline(point, self.substrates.boundary)
        if not cut1 or not cut2:
            # The point does not intersect any outline
            return False
        offset1 = cut1.parallel_offset(radius, 'right', join_style=2)
        offset2 = cut2.parallel_offset(radius, 'right', join_style=2)
        filletCenter = extractPoint(offset1.intersection(offset2))
        if not filletCenter:
            return False
        a, _ = shapely.ops.nearest_points(cut1, filletCenter)
        b, _ = shapely.ops.nearest_points(cut2, filletCenter)
        if not a or not b:
            return False
        patch = Polygon([a, b, point]).difference(filletCenter.buffer(radius))
        self.union(patch)
        return True



def showPolygon(polygon):
    import matplotlib.pyplot as plt

    x,y = polygon.exterior.xy
    plt.fill(x,y)
    for inter in polygon.interiors:
        x, y = inter.xy
        plt.fill(x, y, color='w')
    plt.show()

def showPolygons(polygons):
    import matplotlib.pyplot as plt

    for polygon in polygons:
        x,y = polygon.exterior.xy
        plt.fill(x,y, zorder=1)
        for inter in polygon.interiors:
            x2, y2 = inter.xy
            plt.fill(x2, y2, color="w")
    plt.show()
