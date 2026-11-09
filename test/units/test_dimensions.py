from pathlib import Path
import pcbnew
import pytest
from kikit.common import fromMm, toMm
from kikit.panelize_ui import doPanelization
from kikit.panelize_ui_impl import obtainPreset
from kikit.panelize_ui_sections import PresetError, SDimensionGroups

SOURCE = str(Path(__file__).parents[1] / "resources/conn.kicad_pcb")


def panelize(tmp_path, dimensions=None, post=None, **sections):
    sections.setdefault("layout", {"type": "grid", "rows": "2", "cols": "2", "space": "2mm"})
    sections.setdefault("tabs", {"type": "fixed", "width": "3mm"})
    sections.setdefault("cuts", {"type": "mousebites"})
    sections.setdefault("framing", {"type": "frame", "width": "5mm", "space": "3mm"})
    sections.setdefault("tooling", {"type": "4hole", "hoffset": "2.5mm",
                                    "voffset": "2.5mm", "size": "1.5mm"})
    sections.setdefault("fiducials", {"type": "3fid", "hoffset": "2.5mm",
                                      "voffset": "10mm", "coppersize": "1mm",
                                      "opening": "2mm"})
    preset = obtainPreset([], dimensions=dimensions, post=post, **sections)
    output = str(tmp_path / "panel.kicad_pcb")
    doPanelization(SOURCE, output, preset)
    board = pcbnew.LoadBoard(output)
    dims = [d.Cast() for d in board.GetDrawings()
            if isinstance(d.Cast(), pcbnew.PCB_DIMENSION_BASE)]
    return board, dims


def orthogonal(dims):
    return [d for d in dims if isinstance(d, pcbnew.PCB_DIM_ORTHOGONAL)]


def measured(dims):
    return sorted(round(toMm(abs(d.GetMeasuredValue())), 3) for d in orthogonal(dims))


def leaders(dims):
    return [d.GetShownText(False) for d in dims if isinstance(d, pcbnew.PCB_DIM_LEADER)]


def panelSize(board):
    # The bounding box includes the edge line width (0.1 mm by default)
    bbox = board.GetBoardEdgesBoundingBox()
    return round(toMm(bbox.GetWidth()) - 0.1, 3), round(toMm(bbox.GetHeight()) - 0.1, 3)


def test_dimensionGroupsValidation():
    groups = SDimensionGroups(None, "")
    assert groups.validate("all") == ["overall", "frame", "boards", "tooling", "fiducials"]
    assert groups.validate("overall, tooling") == ["overall", "tooling"]
    with pytest.raises(PresetError):
        groups.validate("overall, holes")


def test_noDimensionsByDefault(tmp_path):
    _, dims = panelize(tmp_path)
    assert dims == []


def test_legacyOverallDimensions(tmp_path):
    board, dims = panelize(tmp_path, post={"dimensions": True})
    assert len(orthogonal(dims)) == 2
    assert sorted(panelSize(board)) == measured(dims)


def test_legacyOptionDoesNotDuplicateOverall(tmp_path):
    _, dims = panelize(tmp_path, post={"dimensions": True},
                       dimensions={"type": "auto", "include": "overall"})
    assert len(orthogonal(dims)) == 2


def test_representativeDimensions(tmp_path):
    board, dims = panelize(tmp_path, dimensions={"type": "auto"})
    values = measured(dims)
    width, height = panelSize(board)
    # Overall size
    assert width in values and height in values
    # Frame width, frame spacing and board spacing are present in both chains
    assert values.count(5) >= 2
    assert values.count(3) >= 2
    assert values.count(2) >= 2
    # Tooling hole offsets and fiducial offsets
    assert values.count(2.5) >= 3
    assert 10 in values
    assert sorted(leaders(dims)) == ["3× FID Ø1, MASK Ø2", "4× Ø1.5 NPTH"]
    assert all(d.GetLayer() == pcbnew.Dwgs_User for d in dims)


def test_allCoverageDimensionsEveryInstance(tmp_path):
    _, representative = panelize(tmp_path, dimensions={"type": "auto"})
    _, everything = panelize(tmp_path, dimensions={"type": "auto", "coverage": "all"})
    assert len(everything) > len(representative)
    # Every tooling hole and fiducial gets two position dimensions
    assert measured(everything).count(2.5) >= 4 * 2 + 3
    assert len(leaders(everything)) == 2


def test_dimensionGroupsSelection(tmp_path):
    _, dims = panelize(tmp_path, dimensions={"type": "auto", "include": "tooling"})
    assert len(orthogonal(dims)) == 2
    assert leaders(dims) == ["4× Ø1.5 NPTH"]


def test_dimensionsStyle(tmp_path):
    _, dims = panelize(tmp_path, dimensions={
        "type": "auto", "include": "overall", "layer": "Cmts.User",
        "units": "inch", "textsize": "2mm"})
    assert len(dims) == 2
    for d in dims:
        assert d.GetLayer() == pcbnew.Cmts_User
        assert d.GetTextSize().x == fromMm(2)
        assert d.GetShownText(False).endswith("in")


@pytest.mark.parametrize("framing", [
    {"type": "railstb", "width": "5mm", "space": "3mm"},
    {"type": "railslr", "width": "5mm", "space": "3mm"},
    {"type": "tightframe", "width": "5mm", "space": "3mm", "slotwidth": "2mm"},
    {"type": "none"}
])
def test_dimensionsWithOtherFramings(tmp_path, framing):
    tooling = {"type": "none"} if framing["type"] == "none" else None
    sections = {"framing": framing}
    if tooling:
        sections["tooling"] = tooling
        sections["fiducials"] = {"type": "none"}
    board, dims = panelize(tmp_path, dimensions={"type": "auto"}, **sections)
    width, height = panelSize(board)
    values = measured(dims)
    assert width in values and height in values
    if framing["type"] in ["railstb", "railslr"]:
        assert 5 in values and 3 in values
