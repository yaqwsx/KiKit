import pytest
from kikit.panelize import prolongCut
from shapely.geometry import LineString
from math import sqrt


def test_prolongCut():
    line = LineString([(0, 0), (1, 1)])
    prolonged = prolongCut(line, 0.5)

    assert prolonged.coords[0] == pytest.approx((sqrt(2)/2 * -0.5, sqrt(2)/2 * -0.5))
    assert prolonged.coords[1] == pytest.approx((1 + sqrt(2)/2 * 0.5, 1 + sqrt(2)/2 * 0.5))
