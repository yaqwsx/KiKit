import pytest
from kikit.intervals import *


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