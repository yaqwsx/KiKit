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

import math

class DummyRect:
    def __init__(self, corners, radius=None):
        self._corners = corners
        self._radius = radius

    def GetRectCorners(self):
        return self._corners

    def GetCornerRadius(self):
        if self._radius is None:
            raise AttributeError("no corner radius in old KiCad")
        return self._radius

def test_approximateRect_pre_kicad10():
    # Pre-KiCad 10 has no corner radius attribute
    rect = DummyRect([(0,0), (10,0), (10,5), (0,5)], radius=None)
    points = approximateRect(rect)
    assert points == [(0,0), (10,0), (10,5), (0,5)]

def test_approximateRect_kicad10_radius_zero():
    # KiCad 10 with corner radius explicitly 0
    rect = DummyRect([(0,0), (10,0), (10,5), (0,5)], radius=0)
    points = approximateRect(rect)
    assert points == [(0,0), (10,0), (10,5), (0,5)]

def test_approximateRect_kicad10_rounded():
    # KiCad 10 Native rounded rectangle with radius 1
    rect = DummyRect([(0,0), (10,0), (10,5), (0,5)], radius=1)
    points = approximateRect(rect)
    
    assert len(points) > 4
    
    # Verify shape bounds
    poly = Polygon(points)
    assert poly.is_valid
    
    minx, miny, maxx, maxy = poly.bounds
    assert pytest.approx(minx, rel=1e-3) == 0
    assert pytest.approx(miny, rel=1e-3) == 0
    assert pytest.approx(maxx, rel=1e-3) == 10
    assert pytest.approx(maxy, rel=1e-3) == 5
    
    expected_area = 50 - (4 - math.pi * 1 * 1)
    assert pytest.approx(poly.area, rel=1e-2) == expected_area

