from itertools import islice
from math import isclose

class Interval:
    """
    Basic interval representation
    """
    def __init__(self, a, b):
        self.min = min(a, b)
        self.max = max(a, b)

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
        return f"Interval({self.min}, {self.max})"

    def __str__(self):
        return f"<{self.min}, {self.max}>"

class BoxNeighbors:
    """
    Given a set of axially arranged non-overlapping boxes answers the query for
    the closest top, bottom, left and right neighbor.

    Neighbor is defined as the closest box in a given direction that has
    non-empty intersection of their projections in the given direction.
    """
    def __init__(self, boxes):
        """
        Given a dictionary id -> box initializes the structure. The construction
        runs in O(n log(n)).

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

    def _prepareProjection(self, getInterval, getDistance, boxes):
        x = [(ident, getInterval(b), getDistance(b)) for ident, b in boxes.items()]
        x.sort(key=lambda t: t[2])
        return x

    def _computeQuery(self, list):
        neighbors = {}
        for i, (ident, interval, pos) in enumerate(list):
            n = []
            for j in range(i + 1, len(list)):
                nIdent, nInterval, nPos = list[j]
                if interval.nontrivialIntersect(nInterval) is None:
                    continue
                if len(n) == 0 or n[0][2] == nPos:
                    n.append((nIdent, nInterval, nPos))
                else:
                    break
            neighbors[ident] = [i for i, _, _ in n]
        return neighbors

    def left(self, ident):
        return self._leftQ[ident]

    def right(self, ident):
        return self._rightQ[ident]

    def top(self, ident):
        return self._topQ[ident]

    def bottom(self, ident):
        return self._bottomQ[ident]

