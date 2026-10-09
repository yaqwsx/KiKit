import json
from pathlib import Path
import pcbnew
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


@pytest.mark.skipif(not hasattr(pcbnew.BOARD, "AddVariant"), reason="requires KiCad 10")
@pytest.mark.parametrize("inherit_drc", [True, False])
def test_panel_preserves_variants(tmp_path, inherit_drc):
    source = tmp_path / "source.kicad_pcb"
    board = pcbnew.LoadBoard(str(Path(__file__).parents[1] / "resources/conn.kicad_pcb"))
    board.AddVariant("Assembly A")
    board.SetVariantDescription("Assembly A", "Without J3")
    footprint = next(x for x in board.GetFootprints() if x.GetReference() == "J3")
    variant = footprint.AddVariant("Assembly A")
    variant.SetDNP(True)
    variant.SetFieldValue("Value", "Variant value")
    board.Save(str(source))
    with open(source.with_suffix(".kicad_pro"), encoding="utf-8") as f:
        source_project = json.load(f)
    source_project["schematic"]["variants"] = [
        {"name": "Assembly A", "description": "Without J3"}]
    with open(source.with_suffix(".kicad_pro"), "w", encoding="utf-8") as f:
        json.dump(source_project, f)

    panel = Panel(str(tmp_path / "panel.kicad_pcb"))
    panel.appendBoard(source, pcbnew.VECTOR2I(fromMm(50), fromMm(50)),
                      inheritDrc=inherit_drc)
    panel.appendBoard(source, pcbnew.VECTOR2I(fromMm(150), fromMm(50)),
                      inheritDrc=inherit_drc)
    panel.save()

    output = pcbnew.LoadBoard(panel.filename)
    assert output.HasVariant("Assembly A")
    assert output.GetVariantDescription("Assembly A") == "Without J3"
    copied = [x for x in output.GetFootprints() if x.GetReference() == "J3"]
    assert len(copied) == 2
    assert all(x.GetDNPForVariant("Assembly A") for x in copied)
    assert all(x.GetFieldValueForVariant("Assembly A", "Value") == "Variant value"
               for x in copied)
    with open(panel.getProFilepath(), encoding="utf-8") as f:
        assert json.load(f)["schematic"]["variants"] == [
            {"name": "Assembly A", "description": "Without J3"}]


@pytest.mark.skipif(not hasattr(pcbnew.BOARD, "AddVariant"), reason="requires KiCad 10")
def test_panel_rejects_conflicting_variants(tmp_path):
    panel = Panel(str(tmp_path / "panel.kicad_pcb"))
    for description in ("First", "Second"):
        source = tmp_path / f"{description}.kicad_pcb"
        board = pcbnew.LoadBoard(str(Path(__file__).parents[1] / "resources/conn.kicad_pcb"))
        board.AddVariant("Assembly A")
        board.SetVariantDescription("Assembly A", description)
        board.Save(str(source))
    panel.appendBoard(tmp_path / "First.kicad_pcb",
                      pcbnew.VECTOR2I(fromMm(50), fromMm(50)), inheritDrc=False)
    with pytest.raises(RuntimeError, match="Conflicting definitions"):
        panel.appendBoard(tmp_path / "Second.kicad_pcb",
                          pcbnew.VECTOR2I(fromMm(150), fromMm(50)), inheritDrc=False)


@pytest.mark.skipif(not hasattr(pcbnew.BOARD, "AddVariant"), reason="requires KiCad 10")
def test_panel_rejects_project_variant_mismatch(tmp_path):
    source = tmp_path / "source.kicad_pcb"
    board = pcbnew.LoadBoard(str(Path(__file__).parents[1] / "resources/conn.kicad_pcb"))
    board.AddVariant("Assembly A")
    board.Save(str(source))
    project_path = source.with_suffix(".kicad_pro")
    with open(project_path, encoding="utf-8") as f:
        project = json.load(f)
    project["schematic"]["variants"] = [{"name": "Other", "description": ""}]
    with open(project_path, "w", encoding="utf-8") as f:
        json.dump(project, f)

    panel = Panel(str(tmp_path / "panel.kicad_pcb"))
    with pytest.raises(RuntimeError, match="differ"):
        panel.appendBoard(source, pcbnew.VECTOR2I(fromMm(50), fromMm(50)))


@pytest.mark.skipif(not hasattr(pcbnew.BOARD, "AddVariant"), reason="requires KiCad 10")
def test_failed_append_does_not_add_variant(tmp_path):
    source = tmp_path / "source.kicad_pcb"
    incompatible = tmp_path / "incompatible.kicad_pcb"
    board = pcbnew.LoadBoard(str(Path(__file__).parents[1] / "resources/conn.kicad_pcb"))
    board.Save(str(source))
    board.AddVariant("Unused")
    board.GetDesignSettings().SetBoardThickness(fromMm(3))
    board.Save(str(incompatible))

    panel = Panel(str(tmp_path / "panel.kicad_pcb"))
    panel.appendBoard(source, pcbnew.VECTOR2I(fromMm(50), fromMm(50)), inheritDrc=False)
    with pytest.raises(RuntimeError, match="thickness"):
        panel.appendBoard(incompatible, pcbnew.VECTOR2I(fromMm(150), fromMm(50)),
                          inheritDrc=False)
    assert not panel.board.HasVariant("Unused")


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
