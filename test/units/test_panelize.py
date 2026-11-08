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
    debugPanel = SimpleNamespace(debugRawFrame=[], debugReverseTabs=[], boardSubstrate=Substrate([]))
    filletedFrame = addFrameFillets(frame, boards, fillet, debugPanel)
    panelGeometry = unary_union(
        [filletedFrame] + [substrate.substrates for substrate in boards]
    )

    assert len(debugPanel.debugReverseTabs) == 1
    assert all(not panelGeometry.contains(center) for center in holeCenters)


@pytest.mark.parametrize("split_outline", [False, True])
def test_circular_board_panel_precision(tmp_path, monkeypatch, split_outline):
    from collections import Counter
    from click.testing import CliRunner
    import numpy as np
    from kikit.ui import cli

    source = tmp_path / "circle.kicad_pcb"
    output = tmp_path / "panel.kicad_pcb"
    board = pcbnew.BOARD()
    if split_outline:
        angles = np.linspace(0, 2 * np.pi, 9)
        points = np.array([fromMm(50), fromMm(50)]) + fromMm(10) * np.column_stack(
            (np.cos(angles), np.sin(angles)))
        factory = Substrate([])
        edges = [factory._constructArc(*points[i:i+3]) for i in range(0, 8, 2)]
    else:
        circle = pcbnew.PCB_SHAPE()
        circle.SetShape(pcbnew.S_CIRCLE)
        circle.SetLayer(pcbnew.Edge_Cuts)
        circle.SetCenter(pcbnew.VECTOR2I(fromMm(50), fromMm(50)))
        circle.SetRadius(fromMm(10))
        edges = [circle]
    for edge in edges:
        edge.SetWidth(fromMm(0.05))
        board.Add(edge)
    board.Save(str(source))
    monkeypatch.setattr("kikit.common.fakeKiCADGui", lambda: None)
    result = CliRunner().invoke(cli, [
        "panelize", "--layout", "grid; rows: 2; cols: 3; space: 2mm",
        "--tabs", "fixed; width: 1.5mm; fillet: 1mm",
        "--framing", "frame; width: 5mm; space: 3mm",
        "--post", "reconstructarcs: true; edgewidth: 0.05mm", str(source), str(output)
    ])
    assert result.exit_code == 0, result.output
    panel = pcbnew.LoadBoard(str(output))
    edges = [e for e in panel.GetDrawings() if e.GetLayer() == pcbnew.Edge_Cuts]
    endpoints = Counter(tuple(p) for e in edges for p in [e.GetStart(), e.GetEnd()])
    assert set(endpoints.values()) == {2}
    arcs = [e for e in edges if e.GetShape() == pcbnew.S_ARC]
    board_arcs = [e for e in arcs if e.GetRadius() > fromMm(5)]
    fillets = [e for e in arcs if e.GetRadius() < fromMm(5)]
    assert len(board_arcs) == 24
    assert len(fillets) >= 48
    # Check the saved/reloaded geometry, including KiCad's arc rounding.
    assert max(abs(e.GetRadius() - fromMm(10)) for e in board_arcs) <= 100
    assert max(abs(e.GetRadius() - fromMm(1)) for e in fillets) <= 100


@pytest.mark.parametrize("angle", [0, 13, 90])
@pytest.mark.parametrize("curved", [False, True])
def test_cachedSourceOutlineMatchesReconstruction(tmp_path, angle, curved):
    import numpy as np
    import shapely
    source = tmp_path / "source.kicad_pcb"
    board = pcbnew.NewBoard(str(source))
    center = np.array([fromMm(20), fromMm(30)])
    if curved:
        shape = pcbnew.PCB_SHAPE(board)
        shape.SetShape(pcbnew.S_CIRCLE)
        shape.SetCenter(pcbnew.VECTOR2I(*map(int, center)))
        shape.SetRadius(fromMm(10))
        shape.SetLayer(pcbnew.Edge_Cuts)
        board.Add(shape)
    else:
        angles = np.linspace(0, 2 * np.pi, 513)
        radii = fromMm(10) + fromMm(2) * np.sin(5 * angles)
        points = np.rint(center + radii[:, None] * np.column_stack((np.cos(angles), np.sin(angles)))).astype(int)
        for a, b in zip(points, points[1:]):
            shape = pcbnew.PCB_SHAPE(board)
            shape.SetShape(pcbnew.S_SEGMENT)
            shape.SetStart(pcbnew.VECTOR2I(*map(int, a)))
            shape.SetEnd(pcbnew.VECTOR2I(*map(int, b)))
            shape.SetLayer(pcbnew.Edge_Cuts)
            board.Add(shape)
    board.Save(str(source))
    cached = Panel(str(tmp_path / "cached.kicad_pcb"))
    reference = Panel(str(tmp_path / "reference.kicad_pcb"))
    sourceArea = pcbnew.BOX2I(pcbnew.VECTOR2I(0, 0), pcbnew.VECTOR2I(fromMm(50), fromMm(50)))
    for x, y in [(50, 50), (100, 100), (150, 75)]:
        reference._sourceSubstrates.clear()
        for panel in [cached, reference]:
            panel.appendBoard(source, pcbnew.VECTOR2I(fromMm(x), fromMm(y)),
                              sourceArea=sourceArea, rotationAngle=EDA_ANGLE(angle, DEGREES_T))
        a, b = cached.substrates[-1], reference.substrates[-1]
        assert a.substrates.equals_exact(b.substrates, 0)
        assert shapely.get_precision(a.substrates) == shapely.get_precision(b.substrates)
        assert len(a.circles) == len(b.circles)
        for ca, cb in zip(a.circles, b.circles):
            for va, vb in zip(ca, cb):
                assert np.array_equal(va, vb)
        probe = (fromMm(x), fromMm(y))
        assert np.array_equal(a.backToSource(probe), b.backToSource(probe))

    if curved:
        import os
        oldStat = source.stat()
        shape.SetRadius(fromMm(8))
        board.Save(str(source))
        os.utime(source, ns=(oldStat.st_atime_ns, oldStat.st_mtime_ns))
        reference._sourceSubstrates.clear()
        for panel in [cached, reference]:
            panel.appendBoard(source, pcbnew.VECTOR2I(fromMm(200), fromMm(125)),
                              sourceArea=sourceArea, rotationAngle=EDA_ANGLE(angle, DEGREES_T))
        assert cached.substrates[-1].substrates.equals_exact(reference.substrates[-1].substrates, 0)



def test_saveWithoutRefillMatchesRefillPath(tmp_path):
    from collections import Counter
    source = Path(__file__).parents[1] / "resources/conn.kicad_pcb"
    snapshots = []
    for refill in [False, True]:
        panel = Panel(str(tmp_path / f"panel-{refill}.kicad_pcb"))
        for x in [50, 100]:
            panel.appendBoard(source, pcbnew.VECTOR2I(fromMm(x), fromMm(50)))
        panel.save(reconstructArcs=True, refillAllZones=refill)
        result = pcbnew.LoadBoard(panel.filename)
        edges = Counter((s.GetShape(), tuple(s.GetStart()), tuple(s.GetEnd()),
                         tuple(s.GetCenter()),
                         s.GetRadius() if s.GetShape() in [pcbnew.S_ARC, pcbnew.S_CIRCLE] else 0, s.GetWidth())
                        for s in result.GetDrawings() if s.GetLayer() == pcbnew.Edge_Cuts)
        footprints = sorted((f.GetReference(), tuple(f.GetPosition()), f.GetOrientation().AsDegrees())
                            for f in result.GetFootprints())
        nets = sorted(str(n) for n in result.GetNetInfo().NetsByName())
        project = json.loads(Path(panel.getProFilepath()).read_text())
        snapshots.append((edges, footprints, nets, project["net_settings"],
                          project["board"]["design_settings"]))
        assert not any(s.GetLayer() == pcbnew.Edge_Cuts for s in panel.board.GetDrawings())
    assert snapshots[0] == snapshots[1]
