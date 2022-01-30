import pytest
from kikit.intervals import *

def identity(x):
    return x

def test_intersection():
    a = Interval(0, 2)
    b = Interval(1, 2)
    c = Interval(1, 3)
    d = Interval(2, 3)
    e = Interval(3, 4)

    assert a.intersect(b) == Interval(1, 2)
    assert a.intersect(c) == Interval(1, 2)
    assert a.intersect(d) == Interval(2, 2)
    assert a.intersect(e) is None

def test_IntervalLists():
    I = Interval
    IL = IntervalList
    a = IL([ I(0, 1), I(2, 3), I(5, 10) ])
    b = IL([ I(0, 2), I(4, 8) ])


    assert a.union(b) == IL([I(0, 3), I(4, 10)])
    assert a.difference(b) == IL([I(2, 3), I(8, 10)])
    assert a.intersect(b) == IL([I(0, 1), I(5, 8)])

def test_boxNeighbors():
    """
    The test case is as follows:

    +---+ +---+ +---+
    | 1 | | 2 | | 3 |
    +---+ +---+ +---+
    +---+ +---+ +---+
    | 4 | | 5 | | 6 |
    +---+ +---+ +---+
    +---------+ +---+
    |    7    | | 8 |
    +---------+ +---+

    """

    # minx, miny, maxx, maxy
    b1 = (1, 1, 2, 2)
    b2 = (3, 1, 4, 2)
    b3 = (5, 1, 6, 2)
    b4 = (1, 3, 2, 4)
    b5 = (3, 3, 4, 4)
    b6 = (5, 3, 6, 4)
    b7 = (1, 5, 4, 6)
    b8 = (5, 5, 6, 6)
    boxes = { i: b for i, b in enumerate([b1, b2, b3, b4, b5, b6, b7, b8], 1) }

    n = BoxNeighbors(boxes)

    assert n.left(1) == []
    assert n.right(1) == [2]
    assert n.top(1) == []
    assert n.bottom(1) == [4]

    assert set(n.top(7)) == set([4, 5])

def test_boxNeighborsOverlap():
    """
    The test case is as follows:

    +---+---+---+
    | 1 | 2 | 3 |
    +---+---+---+
    | 4 | 5 | 6 |
    +---+---+---+
    """
    # minx, miny, maxx, maxy
    b1 = (1, 1, 2, 2)
    b2 = (2, 1, 3, 2)
    b3 = (3, 1, 4, 2)
    b4 = (1, 2, 2, 3)
    b5 = (2, 2, 3, 3)
    b6 = (3, 2, 4, 3)

    boxes = { i: b for i, b in enumerate([b1, b2, b3, b4, b5, b6], 1) }

    n = BoxNeighbors(boxes)

    assert n.right(1) == [2]
    assert n.left(2) == [1]
    assert n.bottom(2) == [5]

def test_boxNeighborsNotSameLevel():
    """
    The test case is as follows:

    +---+ +---+
    | 1 | | 2 |
    +---+ +---+
    +---+
    | 3 |
    +---+
    +---------+
    |    4    |
    +---------+
    """
    # minx, miny, maxx, maxy
    # minx, miny, maxx, maxy
    b1 = (1, 1, 2, 2)
    b2 = (3, 1, 4, 2)
    b3 = (1, 3, 2, 4)
    b4 = (1, 5, 4, 6)

    boxes = { i: b for i, b in enumerate([b1, b2, b3, b4], 1) }

    n = BoxNeighbors(boxes)

    assert set(n.top(4)) == set([2, 3])
    assert n.bottom(3) == [4]
    assert n.bottom(2) == [4]
    assert n.bottom(1) == [3]

def test_bounds():
    a = [1, 2, 3, 4, 5, 6, 7, 8]
    b = [2, 4, 6, 8, 10, 12, 14]
    c = [1, 2, 2, 2, 2, 3, 4]

    assert a[upperBound(a, 5, identity)] == 6
    assert b[upperBound(b, 5, identity)] == 6
    assert b[upperBound(b, 1, identity)] == 2
    assert upperBound(b, 14, identity) == 7
    assert upperBound(b, 15, identity) == 7
    assert upperBound(c, 2, identity) == 5
    assert upperBound(c, 1, identity) == 1

    assert lowerBound(a, 1, identity) == -1
    assert a[lowerBound(a, 3, identity)] == 2
    assert a[lowerBound(a, 5, identity)] == 4
    assert b[lowerBound(b, 5, identity)] == 4
    assert a[lowerBound(a, 14, identity)] == 8
    assert b[lowerBound(b, 15, identity)] == 14
    assert lowerBound(c, 2, identity) == 0
    assert lowerBound(c, 1, identity) == -1


def test_buildShadows():
    AL = AxialLine
    lines = [AL(1, 2, 3, "L1"), AL(2, 1, 2, "L2")]
    bounds = [
        AL(0, 0, 3),
        AL(1, 1, 2),
        AL(3, 2, 3),
        AL(4, 0, 2),
        AL(5, 0, 3)
    ]

    shadows = buildShadows(lines, bounds)
    assert shadows == [ShadowLine(lines[0], Interval(1, 4)),
                       ShadowLine(lines[1], Interval(1, 3))]

def test_trimShadows():
    AL = AxialLine
    SL = ShadowLine
    I = Interval

    lines = [SL(AL(1, 2, 3, "L1"), I(1, 5)), SL(AL(2, 1, 2, "L2"), I(1, 3))]
    bounds = [
        AL(0, 0, 3),
        AL(1, 1, 2),
        AL(3, 2, 3),
        AL(4, 0, 2),
        AL(5, 0, 3)
    ]
    shadows = trimShadows(lines, bounds)
    assert shadows == [
        SL(lines[0].line, I(1, 4)), SL(lines[1].line, I(1, 3))
    ]

def test_BoxPartitionLines():
    pass
    boxes = {
        1: (0, 5, 1, 6),
        2: (2, 5, 3, 6),
        3: (4, 5, 5, 6),
        4: (0, 3, 1, 4),
        5: (2, 3, 3, 4),
        6: (4, 3, 5, 4),
        7: (0, 1, 1, 2),
        8: (2, 1, 3, 2),
        9: (4, 1, 5, 2),
        10: (0, -1, 5, 0),
        11: (0, 7, 5, 8)
    }

    filter = lambda idA, idB, v, l: idA < 10 or idB < 10
    lines = BoxPartitionLines(boxes, filter)

    hlines, vlines = lines.partitionLines(5)