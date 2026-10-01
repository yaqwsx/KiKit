import pytest
from pcbnew import EDA_ANGLE, DEGREES_T
from kikit.annotations import TabAnnotation
from kikit.common import KiAngle, fromMm
from kikit.panelize import (
    Panel, GridPlacerBase, BasicGridPosition, OddEvenRowsPosition, addFrameFillets,
    OddEvenColumnPosition, OddEvenRowsColumnsPosition, prolongCut,
    netClassesDefaultFirst
)
from kikit.substrate import Substrate
from shapely.geometry import LineString, Point, box
from shapely.ops import unary_union
from math import sqrt
from types import SimpleNamespace


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


def test_odd_even_columns_position_rotation():
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


def test_odd_even_rows_columns_position_rotation():
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


def test_makeVCutsIgnoresEmptyGeometry(tmp_path):
    panel = Panel(str(tmp_path / "panel.kicad_pcb"))

    panel.makeVCuts([LineString([(0, 0), (0, 0)])])

    assert panel.hVCuts == set()
    assert panel.vVCuts == set()


def buildTwoBoardPanelWithNotch(tmp_path, notchSize):
    """
    Two 10x10 mm boards placed side by side. The left one has a square notch
    milled into the corner that faces the right board.
    """
    size = fromMm(10)
    notch = box(size - notchSize, size - notchSize, size, size)

    left = Substrate([])
    left.union(box(0, 0, size, size).difference(notch))
    left.partitionLine = LineString([(size, 0), (size, size)])

    right = Substrate([])
    right.union(box(size, 0, 2 * size, size))
    right.partitionLine = LineString([(size, 0), (size, size)])

    panel = Panel(str(tmp_path / "panel.kicad_pcb"))
    panel.substrates = [left, right]
    panel.appendSubstrate(left.substrates)
    panel.appendSubstrate(right.substrates)
    return panel, notch


def test_buildFullTabsKeepsNotchesInBoardOutline(tmp_path):
    notchSize = fromMm(6)
    panel, notch = buildTwoBoardPanelWithNotch(tmp_path, notchSize)

    panel.buildFullTabs(fromMm(1), patchCorners=False, fillRadius=fromMm(2))

    assert not panel.boardSubstrate.substrates.contains(notch.centroid)


def test_buildFullTabsFillsNarrowGaps(tmp_path):
    # A gap narrower than the fill radius is a manufacturing artifact (e.g.,
    # the space between rounded corners), not an intentional board feature
    notchSize = fromMm(1)
    panel, notch = buildTwoBoardPanelWithNotch(tmp_path, notchSize)

    panel.buildFullTabs(fromMm(1), patchCorners=False, fillRadius=fromMm(2))

    assert panel.boardSubstrate.substrates.contains(notch.centroid)


def test_buildFullTabsZeroFillRadiusFillsNothing(tmp_path):
    notchSize = fromMm(1)
    panel, notch = buildTwoBoardPanelWithNotch(tmp_path, notchSize)

    panel.buildFullTabs(fromMm(1), patchCorners=False, fillRadius=0)

    assert not panel.boardSubstrate.substrates.contains(notch.centroid)


def test_netClassesDefaultFirst():
    netClasses = [
        {"name": "Default"},
        {"name": "HV"},
        {"name": "Board_0-Default"},
        {"name": "Board_0-HV"},
        {"name": "Board_1-Default"},
        {"name": "Board_1-HV"},
    ]

    assert [x["name"] for x in netClassesDefaultFirst(netClasses)] == [
        "Default",
        "Board_0-Default",
        "Board_1-Default",
        "HV",
        "Board_0-HV",
        "Board_1-HV",
    ]


def test_addFrameFilletsDoesNotCrossOtherBoards():
    boardWidth = fromMm(10)
    boardHeight = fromMm(10)
    boardSpacing = fromMm(2)
    holeWidth = fromMm(3.5)
    holeHeight = fromMm(3)
    tabWidth = fromMm(3)
    fillet = fromMm(1)

    boards = []
    holeCenters = []
    for row in range(3):
        miny = row * (boardHeight + boardSpacing)
        maxy = miny + boardHeight
        hole = box(
            (boardWidth - holeWidth) / 2,
            miny + fromMm(3),
            (boardWidth + holeWidth) / 2,
            miny + fromMm(3) + holeHeight
        )
        substrate = Substrate([])
        substrate.union(box(0, miny, boardWidth, maxy).difference(hole))
        substrate.annotations.append(
            TabAnnotation(None, (boardWidth / 2, miny), (0, 1), tabWidth)
        )
        boards.append(substrate)
        holeCenters.append(Point(boardWidth / 2, miny + fromMm(4.5)))

    frame = box(0, -fromMm(4), boardWidth, -fromMm(2))
    debugPanel = SimpleNamespace(debugRawFrame=[], debugReverseTabs=[])
    filletedFrame = addFrameFillets(frame, boards, fillet, debugPanel)
    panelGeometry = unary_union(
        [filletedFrame] + [substrate.substrates for substrate in boards]
    )

    assert len(debugPanel.debugReverseTabs) == 1
    assert all(not panelGeometry.contains(center) for center in holeCenters)
