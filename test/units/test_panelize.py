import pytest
from pcbnewTransition.pcbnew import EDA_ANGLE, DEGREES_T
from kikit.common import KiAngle
from kikit.panelize import (
    GridPlacerBase, BasicGridPosition, OddEvenRowsPosition,
    OddEvenColumnPosition, OddEvenRowsColumnsPosition, prolongCut
)
from shapely.geometry import LineString
from math import sqrt


def test_grid_place_base_rotation():
    placer = GridPlacerBase()
    for (i, j) in ((0, 0), (0, 1), (1, 0), (1, 1), (2, 0), (2, 1)):
        rotation = placer.rotation(i, j)
        assert isinstance(rotation, KiAngle)
        assert rotation.AsDegrees() == EDA_ANGLE(0, DEGREES_T).AsDegrees()


def test_basic_grid_position_rotation():
    placer = BasicGridPosition(0, 0)
    for (i, j) in ((0, 0), (0, 1), (1, 0), (1, 1), (2, 0), (2, 1)):
        rotation = placer.rotation(i, j)
        assert isinstance(rotation, KiAngle)
        assert rotation.AsDegrees() == EDA_ANGLE(0, DEGREES_T).AsDegrees()


def test_odd_even_rows_position_rotation():
    placer = OddEvenRowsPosition(0, 0)
    for (i, j, expected_rot) in ((0, 0, EDA_ANGLE(0, DEGREES_T)),
                                 (0, 1, EDA_ANGLE(0, DEGREES_T)),
                                 (1, 0, EDA_ANGLE(180, DEGREES_T)),
                                 (1, 1, EDA_ANGLE(180, DEGREES_T)),
                                 (2, 0, EDA_ANGLE(0, DEGREES_T)),
                                 (2, 1, EDA_ANGLE(0, DEGREES_T))):
        rotation = placer.rotation(i, j)
        assert isinstance(rotation, KiAngle)
        assert rotation.AsDegrees() == expected_rot.AsDegrees()


def test_odd_even_column_position_rotation():
    placer = OddEvenColumnPosition(0, 0)
    for (i, j, expected_rot) in ((0, 0, EDA_ANGLE(0, DEGREES_T)),
                                 (0, 1, EDA_ANGLE(180, DEGREES_T)),
                                 (1, 0, EDA_ANGLE(0, DEGREES_T)),
                                 (1, 1, EDA_ANGLE(180, DEGREES_T)),
                                 (2, 0, EDA_ANGLE(0, DEGREES_T)),
                                 (2, 1, EDA_ANGLE(180, DEGREES_T))):
        rotation = placer.rotation(i, j)
        assert isinstance(rotation, KiAngle)
        assert rotation.AsDegrees() == expected_rot.AsDegrees()


def test_odd_even_column_position_rotation():
    placer = OddEvenRowsColumnsPosition(0, 0)
    for (i, j, expected_rot) in ((0, 0, EDA_ANGLE(0, DEGREES_T)),
                                 (0, 1, EDA_ANGLE(180, DEGREES_T)),
                                 (1, 0, EDA_ANGLE(180, DEGREES_T)),
                                 (1, 1, EDA_ANGLE(0, DEGREES_T)),
                                 (2, 0, EDA_ANGLE(0, DEGREES_T)),
                                 (2, 1, EDA_ANGLE(180, DEGREES_T))):
        rotation = placer.rotation(i, j)
        assert isinstance(rotation, KiAngle)
        assert rotation.AsDegrees() == expected_rot.AsDegrees()


def test_prolongCut():
    line = LineString([(0, 0), (1, 1)])
    prolonged = prolongCut(line, 0.5)

    assert prolonged.coords[0] == pytest.approx((sqrt(2)/2 * -0.5, sqrt(2)/2 * -0.5))
    assert prolonged.coords[1] == pytest.approx((1 + sqrt(2)/2 * 0.5, 1 + sqrt(2)/2 * 0.5))
