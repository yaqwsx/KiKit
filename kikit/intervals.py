from itertools import islice, chain
from math import isclose
from copy import copy

class Interval:
    """
    Basic interval representation
    """
    def __init__(self, a, b):
        self.min = min(a, b)
        self.max = max(a, b)

    def __contains__(self, item):
        return self.min <= item and item <= self.max

    def intersect(self, other):
        """
        Return a new interval representing the overlap, otherwise None
        """
        if self.min > other.max or other.min > self.max:
            return None
        return Interval(max(self.min, other.min), min(self.max, other.max))

    def nontrivialIntersect(self, other):
        """
        Return a new interval representing the overlap larger than a single
        point, otherwise None
        """
        i = self.intersect(other)
        if i is None or i.trivial():
            return None
        return i

    def trivial(self):
        return self.min == self.max

    @property
    def length(self):
        return self.max - self.min

    def __eq__(self, other):
        return isclose(self.min, other.min) and isclose(self.max, other.max)

    def __repr__(self):
        return f"I({self.min}, {self.max})"

    def __str__(self):
        return f"<{self.min}, {self.max}>"

class IntervalList:
    def __init__(self, intervals):
        self.intervals = self._normalize(self._toList(intervals))

    def __eq__(self, other):
        return self.intervals == self._toList(other)

    def __repr__(self):
        return f"IL[ {', '.join([x.__repr__() for x in self.intervals])} ]"

    def __str__(self):
        return f"IL[ {', '.join([x.__str__() for x in self.intervals])} ]"

    def trivial(self):
        return len(self.intervals) == 0

    @staticmethod
    def _toList(object):
        """
        Convert the object into a list of intervals
        """
        if isinstance(object, Interval):
            return [object]
        if isinstance(object, list):
            return object
        if isinstance(object, IntervalList):
            return object.intervals
        raise RuntimeError("Uknown object")

    @staticmethod
    def _normalize(intervals):
        intervals.sort(key=lambda x: x.min)
        newIntervals = []
        for b in intervals:
            if b.trivial():
                continue
            if len(newIntervals) == 0:
                newIntervals.append(copy(b))
                continue
            a = newIntervals[-1]
            if b.min <= a.max:
                a.max = max(a.max, b.max)
            else:
                newIntervals.append(copy(b))
        return newIntervals

    @staticmethod
    def _eventList(intervals0, intervals1):
        """
        Build event list; event is a tuple (1/0, x, event). Event +1 means open
        interval, -1 means close interval. The events are sorted by x
        """
        base1 = [[(0, x.min, 1), (0, x.max, -1)] for x in intervals0]
        base2 = [[(1, x.min, 1), (1, x.max, -1)] for x in intervals1]
        l = list(chain(*base1, *base2))
        l.sort(key=lambda x: x[1])
        return l

    def union(self, other):
        """
        Union this interval with other and return new instance
        """
        return IntervalList(self.intervals + self._toList(other))

    def intersect(self, other):
        """
        Perform self / other and return new instance
        """
        intervals = []
        visibleIntervals = 0
        for _, p, e in self._eventList(self.intervals, self._toList(other)):
            if visibleIntervals == 1 and e == 1:
                start = p
            if visibleIntervals == 2 and e == -1:
                intervals.append(Interval(start, p))
            visibleIntervals += e
            assert visibleIntervals >= 0 and visibleIntervals <= 2
        return IntervalList(intervals)

    def difference(self, other):
        """
        Perform self / other and return new instance
        """
        intervals = []
        aOpen = 0
        bOpen = 0
        for ident, p, e in self._eventList(self.intervals, self._toList(other)):
            if (ident == 0 and e == 1) and bOpen == 0: # Rising A, no B
                start = p
            if (ident == 1 and e == -1) and aOpen == 1: # Falling B, A is on
                start = p
            if (ident == 0 and e == -1) and bOpen == 0: # Falling A, no B
                intervals.append(Interval(start, p))
            if (ident == 1 and e == 1) and aOpen == 1: # Raising B, A is on
                intervals.append(Interval(start, p))
            if ident == 0:
                aOpen += e
            else:
                bOpen += e
            assert aOpen >= 0 and aOpen <= 1
            assert bOpen >= 0 and bOpen <= 1
        return IntervalList(intervals)


class BoxNeighbors:
    """
    Given a set of axially arranged non-overlapping boxes answers the query for
    the closest top, bottom, left and right neighbor.

    Neighbor is defined as the closest box in a given direction that has
    non-empty intersection of their projections in the given direction.
    """
    def __init__(self, boxes):
        """
        Given a dictionary id -> box initializes the structure.

        Boxes are represented by a tuple (minx, miny, maxx, maxy)
        """
        xProj = lambda b: Interval(b[0], b[2])
        yProj = lambda b: Interval(b[1], b[3])

        leftList = self._prepareProjection(yProj, lambda b: -b[2], boxes)
        self._leftQ = self._computeQuery(leftList)
        rightList = self._prepareProjection(yProj, lambda b: b[0], boxes)
        self._rightQ = self._computeQuery(rightList)
        topList = self._prepareProjection(xProj, lambda b: -b[3], boxes)
        self._topQ = self._computeQuery(topList)
        bottomList = self._prepareProjection(xProj, lambda b: b[1], boxes)
        self._bottomQ = self._computeQuery(bottomList)

    @staticmethod
    def _prepareProjection(getInterval, getDistance, boxes):
        x = [(ident, getInterval(b), getDistance(b)) for ident, b in boxes.items()]
        x.sort(key=lambda t: t[2])
        return x

    @staticmethod
    def _computeQuery(list):
        neighbors = {}
        for i, (ident, interval, pos) in enumerate(list):
            n = []
            rest = IntervalList(interval)
            for j in range(i + 1, len(list)):
                nIdent, nInterval, nPos = list[j]
                shadow = rest.intersect(nInterval)
                if shadow.trivial():
                    continue
                n.append((nIdent, shadow))
                rest = rest.difference(nInterval)
                if rest.trivial():
                    break
            neighbors[ident] = n
        return neighbors

    @staticmethod
    def _simplify(result):
        return [ident for ident, _ in result]

    def left(self, ident):
        return self._simplify(self._leftQ[ident])

    def leftC(self, ident):
        return self._leftQ[ident]

    def right(self, ident):
        return self._simplify(self._rightQ[ident])

    def rightC(self, ident):
        return self._rightQ[ident]

    def top(self, ident):
        return self._simplify(self._topQ[ident])

    def topC(self, ident):
        return self._topQ[ident]

    def bottom(self, ident):
        return self._simplify(self._bottomQ[ident])

    def bottomC(self, ident):
        return self._bottomQ[ident]


class AxialLine(Interval):
    """
    Representation of a horizontal or vertical line
    """
    def __init__(self, x, y1, y2, tag=None):
        super().__init__(y1, y2)
        self.x = x
        self.tag = tag

    def cut(self, y):
        """
        Cut the line at y. Return a list of newly created AxialLines
        """
        if y not in self or y == self.min or y == self.max:
            return [self]
        return [
            AxialLine(self.x, self.min, y, self.tag),
            AxialLine(self.x, y, self.max, self.tag)
        ]

    def __eq__(self, other):
        return isclose(self.x, other.x) and super().__eq__(other)

    def __repr__(self):
        return f"Line[{self.tag}]({self.x}, {self.min}, {self.max})"

    def __hash__(self):
        return hash((self.x, self.min, self.max, self.tag))

class ShadowLine:
    """
    Represents a horizontal or vertical line with a shadow (possible
    prolongation)
    """
    def __init__(self, line, shadow):
        assert isinstance(line, AxialLine)
        assert isinstance(shadow, Interval)
        self.line = line
        self.shadow = shadow

    @property
    def shadowLine(self):
        return AxialLine(self.line.x, self.shadow.min, self.shadow.max,
            self.line.tag)

    def __eq__(self, other):
        return self.line == other.line and self.shadow == other.shadow

    def __repr__(self):
        return f"Shadow({self.line.__repr__()}, {self.shadow.__repr__()})"

def collectBoxEdges(box):
    """
    Given a box, return a tuple (horiz edges, vert edges) as lists of AxialLine
    """
    return (
        [AxialLine(box[1], box[0], box[2]), AxialLine(box[3], box[0], box[2])],
        [AxialLine(box[0], box[1], box[3]), AxialLine(box[2], box[1], box[3])]
    )

def collectHardStops(boxes):
    """
    Given an iterable of boxes, return all partition lines hard stops - i.e.,
    union of all edges as a tuple (horiz edges, vert edges) as lists of
    AxialLine
    """
    from kikit.common import shpBBoxMerge

    hedges, vedges = set(), set()
    commonBox = None
    for b in boxes:
        if commonBox is None:
            commonBox = b
        else:
            commonBox = shpBBoxMerge(commonBox, b)
        h, v = collectBoxEdges(b)
        hedges.update(h)
        vedges.update(v)
    h, v = collectBoxEdges(commonBox)
    hedges.update(h)
    vedges.update(v)
    return list(hedges), list(vedges)

def defaultSeedFilter(boxIdA, boxIdB, vertical, seedline):
    return True

def collectSeedLines(boxes, seedFilter):
    """
    Given a dictionary ident -> box return a list of all midlines between
    neighboring boxes.

    The function seedFilter of type(boxAId, boxBId, vertical, seedLine) -> bool,
    serves as a predicate that can filter unwanted seed lines - e.g., too far
    apart or comming from ghost boxes.

    Returns (horlines, verlines), where the lines are tagged with ident
    """
    neighbors = BoxNeighbors(boxes)
    horlines, verlines = [], []
    for identA, boxA in boxes.items():
        for identB, shadow in neighbors.leftC(identA):
            mid = (boxA[0] + boxes[identB][2]) / 2
            candidates = [AxialLine(mid, e.min, e.max, identA)
                for e in shadow.intervals]
            verlines.extend([x for x in candidates
                if seedFilter(identA, identB, True, x)])
        for identB, shadow in neighbors.rightC(identA):
            mid = (boxA[2] + boxes[identB][0]) / 2
            candidates = [AxialLine(mid, e.min, e.max, identA)
                for e in shadow.intervals]
            verlines.extend([x for x in candidates
                if seedFilter(identA, identB, True, x)])
        for identB, shadow in neighbors.topC(identA):
            mid = (boxA[1] + boxes[identB][3]) / 2
            candidates = [AxialLine(mid, e.min, e.max, identA)
                for e in shadow.intervals]
            horlines.extend([x for x in candidates
                if seedFilter(identA, identB, False, x)])
        for identB, shadow in neighbors.bottomC(identA):
            mid = (boxA[3] + boxes[identB][1]) / 2
            candidates = [AxialLine(mid, e.min, e.max, identA)
                for e in shadow.intervals]
            horlines.extend([x for x in candidates
                if seedFilter(identA, identB, False, x)])
    return horlines, verlines

def upperBound(sortedCollection, item, key=lambda x: x):
    """
    Given a sorted collection, perform binary search to find element x for which
    the following holds: item < key(x) and the value key(x) is the smallest.
    Returns index of such an element.
    """
    lo = 0
    hi = len(sortedCollection)
    while lo < hi:
        mid = (lo + hi) // 2
        if item < key(sortedCollection[mid]):
            hi = mid
        else:
            lo = mid + 1
    return lo

def lowerBound(sortedCollection, item, key=lambda x: x):
    """
    Given a sorted collection, perform binary search to find element x for which
    the following holds: item > key(x) and the value key(x) is the largest.
    Returns index of such an element.
    """
    lo = 0
    hi = len(sortedCollection)
    while lo < hi:
        mid = (lo + hi) // 2
        if item > key(sortedCollection[mid]):
            lo = mid + 1
        else:
            hi = mid
    return lo - 1

def buildShadows(lines, boundaries):
    """
    Given an iterable of AxialLines, build their prolonged shadows. Shadows
    stop at the boundaries. Lines and boundaries are expected to be
    perpendicular to each other. This function assumes there is a boundary for
    every line.
    """
    boundaries = list(boundaries)
    boundaries.sort(key=lambda line: line.x)

    shadowLines = []
    for l in lines:
        # Extend to right
        righStart = lowerBound(boundaries, l.max, key=lambda line: line.x)
        for i in range(righStart, len(boundaries)):
            b = boundaries[i]
            if l.x in b and b.x > l.min:
                rightExtend = b.x
                break
        # Extend to left
        leftStart = upperBound(boundaries, l.min, key=lambda line: line.x)
        for i in range(leftStart, 0, -1):
            b  = boundaries[i]
            if l.x in b and b.x < l.max:
                leftExtend = b.x
                break
        assert rightExtend is not None
        assert leftExtend is not None
        shadowLines.append(ShadowLine(l, Interval(leftExtend, rightExtend)))
    return shadowLines

def trimShadows(shadows, boundaries):
    """
    Given an iterable of ShadowLines and Axial lines as boudaries, trim the
    shadows so they do not cross any boundary. Return new shadows.
    """
    boundaries = list(boundaries)
    boundaries.sort(key=lambda line: line.x)
    newShadows = []
    for l in shadows:
        # Trim right
        rightStart = upperBound(boundaries, l.line.min, key=lambda line: line.x)
        rightTrim = l.shadow.max
        for i in range(rightStart, len(boundaries)):
            b = boundaries[i]
            if l.line.x in b and l.shadow.min < b.x <= l.shadow.max:
                rightTrim = b.x
                break
        # Trim left
        leftStart = upperBound(boundaries, l.line.max, key=lambda line: line.x) - 1
        leftTrim = l.shadow.min
        for i in range(leftStart, 0, -1):
            b = boundaries[i]
            if l.line.x in b and l.shadow.min <= b.x < l.shadow.max:
                leftTrim = b.x
                break
        newShadows.append(ShadowLine(l.line, Interval(leftTrim, rightTrim)))
    return newShadows

class BoxPartitionLines:
    """
    Given a set of axially arranged non-overlapping boxes answers the query for
    the partition lines of each box.

    Partition line is a horizontal or a vertical line. The union of all
    partition lines splits the free space between the boxes such that the gaps
    between two neighboring boxes are split evenly. See the following
    illustration:

    +---+ | +----+ | +--------+
    |   | | |    | | |        |
    +---+ | |    | | |        |
    ------| |    | | +--------+
    +---+ | |    | |-----------
    |   | | |    |   |   +----+
    +---+ | +----+   |   +----+
    """

    def __init__(self, boxes, seedFilter=defaultSeedFilter,
                 safeHorizontalMargin=0, safeVerticalMargin=0):
        """
        Given a dictionary id -> box initializes the structure.

        Boxes are represented by a tuple (minx, miny, maxx, maxy)

        The margin guarantees there will be no partition line too close to edge
        (necessary to handle some pathological cases)
        """
        from kikit.common import shpBBoxExpand

        hstops, vstops = collectHardStops(boxes.values())
        hSafeStops, vSafeStops = collectHardStops([
            shpBBoxExpand(x, safeVerticalMargin, safeHorizontalMargin) for x in boxes.values()])
        hseeds, vseeds = collectSeedLines(boxes, seedFilter)
        hshadows = buildShadows(hseeds, chain(vstops, vSafeStops))
        vshadows = buildShadows(vseeds, chain(hstops, hSafeStops))

        hPartition = trimShadows(hshadows, chain(
            [x.shadowLine for x in vshadows], vSafeStops))
        vPartition = trimShadows(vshadows, chain(
            [x.shadowLine for x in hshadows], hSafeStops))

        self.query = { ident: ([], []) for ident in boxes.keys() }
        for l in hPartition:
            self.query[l.line.tag][0].append(
                AxialLine(l.line.x, l.shadow.min, l.shadow.max))
        for l in vPartition:
            self.query[l.line.tag][1].append(
                AxialLine(l.line.x, l.shadow.min, l.shadow.max))

    def partitionLines(self, ident):
        """
        Return a tuple (horiz. lines, vert. lines) represented as AxialLine
        """
        return self.query[ident]

    def _visualize(self, vars):
        """
        When debugging, you can invoke self._visualize(locals()) in __init__ to
        see what is happening.
        """
        import matplotlib.pyplot as plt

        for h in vars["hstops"]:
            plt.hlines(h.x, h.min, h.max, ["g"])
        for v in vars["vstops"]:
            plt.vlines(v.x, v.min, v.max, ["g"])

        plt.axis('equal')
        for h in vars["hshadows"]:
            plt.hlines(h.line.x, h.shadow.min, h.shadow.max, ["r"])
        for v in vars["vshadows"]:
            plt.vlines(v.line.x, v.shadow.min, v.shadow.max, ["r"])

        for h in vars["hseeds"]:
            plt.hlines(h.x, h.min, h.max)
        for v in vars["vseeds"]:
            plt.vlines(v.x, v.min, v.max)
        plt.show()
