import pytest
from shapely.geometry import Point
from kikit.substrate import *

def test_biteBoundary():
    l1 = LineString([ (0, 0), (1, 0), (1, 1), (0, 1)])
    l2 = LineString([ (0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
    l3 = LinearRing([ (0, 0), (1, 0), (1, 1), (0, 1)])

    t1 = biteBoundary(l1, Point(1, 0.5), Point(0.5, 1), 0.01)
    assert t1 == LineString([(1, 0.5), (1, 1), (0.5, 1)])

    t2 = biteBoundary(l1, Point(0, 0.5), Point(0.5, 0), 0.1)
    assert t2 is None

    t3 = biteBoundary(l2, Point(0, 0.5), Point(0.5, 0), 0.1)
    assert t3 == LineString([(0, 0.5), (0, 0), (0.5, 0)])

    t4 = biteBoundary(l3, Point(0, 0.5), Point(0.5, 0), 0.1)
    assert t4 == LineString([(0, 0.5), (0, 0), (0.5, 0)])

    t5 = biteBoundary(l1, Point(1, 0.25), Point(1, 0.75), 0.1)
    assert t5 == LineString([(1, 0.25), (1, 0.75)])
