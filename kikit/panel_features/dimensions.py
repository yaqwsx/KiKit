from dataclasses import dataclass, field
from math import hypot
from typing import List, Optional, Tuple
import pcbnew
from pcbnew import VECTOR2I
from ..common import KiLength, fromMm, toMm
from ..defs import Layer
from ..pcbnew_utils import DIM_UNITS_MODE_MM, DIM_UNITS_MODE_INCH, DIM_UNITS_MODE_MILS
from ..panelize import Panel
from .baseFeature import PanelFeature

DIMENSION_GROUPS = ["overall", "frame", "boards", "tooling", "fiducials"]

UNITS_MODES = {
    "mm": DIM_UNITS_MODE_MM,
    "inch": DIM_UNITS_MODE_INCH,
    "mils": DIM_UNITS_MODE_MILS
}

PRECISIONS = [
    pcbnew.DIM_PRECISION_X,
    pcbnew.DIM_PRECISION_X_X,
    pcbnew.DIM_PRECISION_X_XX,
    pcbnew.DIM_PRECISION_X_XXX,
    pcbnew.DIM_PRECISION_X_XXXX,
    pcbnew.DIM_PRECISION_X_XXXXX
]

# Tolerance for deciding that two boards share a row/column
ALIGN_TOLERANCE = fromMm(0.01)

Point = Tuple[KiLength, KiLength]

def _overlap(aMin: KiLength, aMax: KiLength, bMin: KiLength, bMax: KiLength) -> bool:
    return min(aMax, bMax) - max(aMin, bMin) > ALIGN_TOLERANCE

@dataclass
class PanelDimensions(PanelFeature):
    """
    Annotate the panel with dimensions of its features.

    The groups to dimension are:

    - overall: total width and height of the panel
    - frame: width of the frame/rails and spacing between the frame and boards
    - boards: board size and the spacing between the boards
    - tooling: position of tooling holes from the panel edges and their diameter
    - fiducials: position of fiducials from the panel edges and their size

    Frame and board dimensions are drawn as a chain along the top and the left
    edge of the panel. The overall size is drawn as the outermost dimension.
    Tooling holes and fiducials are dimensioned from the nearest panel edges.

    With coverage "representative" only a single instance of repeated features
    is dimensioned (e.g., the first board and the first gap). With coverage
    "all", every instance is dimensioned.
    """
    include: List[str] = field(default_factory=lambda: list(DIMENSION_GROUPS))
    coverage: str = "representative"
    layer: Layer = Layer.Dwgs_User
    units: str = "mm"
    precision: int = 2
    offset: KiLength = fromMm(5)
    textSize: KiLength = fromMm(1.5)

    def apply(self, panel: Panel) -> None:
        unknown = set(self.include).difference(DIMENSION_GROUPS)
        if unknown:
            raise RuntimeError(f"Unknown dimension groups: {', '.join(unknown)}. " +
                               f"Use any of {', '.join(DIMENSION_GROUPS)}.")
        if self.coverage not in ["representative", "all"]:
            raise RuntimeError(f"Unknown dimension coverage '{self.coverage}'")
        if self.units not in UNITS_MODES:
            raise RuntimeError(f"Unknown dimension units '{self.units}'")

        self.panel = panel
        panel._ensureLayerEnabled(self.layer)
        self.minx, self.miny, self.maxx, self.maxy = [
            int(round(x)) for x in panel.panelBBox()]

        tier = 1
        if self._buildChains(tier):
            tier += 1
        if "overall" in self.include:
            self._buildOverall(tier)
        if "tooling" in self.include:
            self._buildTooling()
        if "fiducials" in self.include:
            self._buildFiducials()

    # Styling and primitive construction

    def _style(self, dim: pcbnew.PCB_DIMENSION_BASE, suffix: bool = False) -> None:
        """
        Apply common style. Only the overall dimensions carry the units suffix
        to keep the short dimensions readable.
        """
        dim.SetLayer(self.layer)
        dim.SetUnitsMode(UNITS_MODES[self.units])
        dim.SetUnitsFormat(pcbnew.DIM_UNITS_FORMAT_BARE_SUFFIX if suffix
                           else pcbnew.DIM_UNITS_FORMAT_NO_SUFFIX)
        dim.SetPrecision(PRECISIONS[min(self.precision, len(PRECISIONS) - 1)])
        dim.SetSuppressZeroes(True)
        dim.SetTextSize(VECTOR2I(self.textSize, self.textSize))
        dim.SetTextThickness(max(1, self.textSize // 8))
        dim.SetLineThickness(max(1, self.textSize // 10))
        dim.SetArrowLength(self.textSize)

    def _orthogonal(self, start: Point, end: Point, horizontal: bool,
                    crossbar: KiLength) -> Optional[pcbnew.PCB_DIM_ORTHOGONAL]:
        """
        Add an orthogonal dimension between start and end. The crossbar is the
        coordinate of the dimension line (y for horizontal, x for vertical).
        """
        axis = 0 if horizontal else 1
        if abs(end[axis] - start[axis]) <= ALIGN_TOLERANCE:
            return None
        dim = pcbnew.PCB_DIM_ORTHOGONAL(self.panel.board)
        dim.SetOrientation(pcbnew.PCB_DIM_ORTHOGONAL.DIR_HORIZONTAL if horizontal
                           else pcbnew.PCB_DIM_ORTHOGONAL.DIR_VERTICAL)
        dim.SetStart(VECTOR2I(int(start[0]), int(start[1])))
        dim.SetEnd(VECTOR2I(int(end[0]), int(end[1])))
        dim.SetHeight(int(crossbar - start[1 - axis]))
        self._style(dim)
        self.panel.board.Add(dim)
        return dim

    def _leader(self, center: VECTOR2I, radius: KiLength, text: str) -> pcbnew.PCB_DIM_LEADER:
        """
        Add a leader pointing at a circular feature. The chain dimensions
        occupy the top and the left side of the panel, therefore, the leader
        leaves the panel through the right or bottom edge when the feature is
        close to it. Otherwise, it points towards the panel interior.
        """
        # The position dimensions of the feature occupy two diagonal quadrants
        # around it; the quadrant towards the panel interior and the quadrant
        # towards the panel corner are free.
        sx, sy = self._nearestCorner(pos=center)
        length = radius + 2 * self.textSize
        if sx < 0 or sy < 0:
            # Leave the panel through the corner
            dx, dy, textSide = -sx, -sy, 1
            if sx < 0:
                length = max(length, (self.maxx - center.x) + self.textSize)
            else:
                length = max(length, (self.maxy - center.y) + self.textSize)
        else:
            dx, dy, textSide = sx, sy, sx
        dim = pcbnew.PCB_DIM_LEADER(self.panel.board)
        self._style(dim)
        diagonal = 1 / hypot(1, 1)
        dim.SetStart(VECTOR2I(int(center.x + dx * radius * diagonal),
                              int(center.y + dy * radius * diagonal)))
        end = VECTOR2I(int(center.x + dx * length), int(center.y + dy * length))
        dim.SetEnd(end)
        dim.SetOverrideTextEnabled(True)
        dim.SetOverrideText(text)
        dim.Update()
        textWidth = dim.GetTextBox().GetWidth()
        dim.SetTextPos(VECTOR2I(int(end.x + textSide * (textWidth // 2 + self.textSize // 2)),
                                end.y))
        dim.Update()
        self.panel.board.Add(dim)
        return dim

    def _formatLength(self, value: KiLength) -> str:
        if self.units == "mm":
            v = toMm(value)
        elif self.units == "inch":
            v = toMm(value) / 25.4
        else:
            v = toMm(value) / 0.0254
        s = f"{v:.{self.precision}f}"
        if "." in s:
            s = s.rstrip("0").rstrip(".")
        return s

    # Groups

    def _buildOverall(self, tier: int) -> None:
        hDim, vDim = self.panel.addPanelDimensions(self.layer, tier * self.offset)
        self._style(hDim, suffix=True)
        self._style(vDim, suffix=True)

    def _boardBoxes(self) -> List[Tuple[int, int, int, int]]:
        return [tuple(int(round(x)) for x in s.bounds()) for s in self.panel.substrates]

    def _chainPoints(self, horizontal: bool) -> List[Point]:
        """
        Build the list of points for a chain dimension along the top
        (horizontal) or left (vertical) edge of the panel.
        """
        # Work in a coordinate system where "a" is the chain axis and "b" the
        # perpendicular axis, so we don't have to duplicate the logic
        a, b = (0, 1) if horizontal else (1, 0)
        def pt(av: KiLength, bv: KiLength) -> Point:
            return (av, bv) if horizontal else (bv, av)

        panelMin = (self.minx, self.miny)
        panelMax = (self.maxx, self.maxy)
        edges = self.panel.frameInnerEdges
        aName, bName = ("x", "y") if horizontal else ("y", "x")
        frameMin = edges.get("min" + aName)
        frameMax = edges.get("max" + aName)
        frameB = edges.get("min" + bName, panelMin[b])

        boards = self._boardBoxes()
        line: List[Tuple[int, int, int, int]] = []
        if boards:
            first = min(boards, key=lambda x: (x[b], x[a]))
            line = sorted([x for x in boards if _overlap(x[b], x[b + 2], first[b], first[b + 2])],
                          key=lambda x: x[a])

        includeFrame = "frame" in self.include
        includeBoards = "boards" in self.include and len(line) > 0
        allCoverage = self.coverage == "all"

        points: List[Point] = []
        if includeFrame:
            points.append(pt(panelMin[a], panelMin[b]))
            if frameMin is not None:
                points.append(pt(frameMin, frameB))
            if line:
                points.append(pt(line[0][a], line[0][b]))
        if includeBoards:
            if not includeFrame:
                points.append(pt(line[0][a], line[0][b]))
            shownBoards = line if allCoverage else line[:2]
            for i, board in enumerate(shownBoards):
                if i > 0:
                    points.append(pt(board[a], board[b]))
                if allCoverage or i == 0:
                    points.append(pt(board[a + 2], board[b]))
        if includeFrame and allCoverage and line:
            if not includeBoards:
                points.append(pt(line[-1][a + 2], line[-1][b]))
            if frameMax is not None:
                points.append(pt(frameMax, frameB))
            points.append(pt(panelMax[a], panelMin[b]))
        return points

    def _buildChains(self, tier: int) -> bool:
        built = False
        hCrossbar = self.miny - tier * self.offset
        vCrossbar = self.minx - tier * self.offset
        for horizontal, crossbar in [(True, hCrossbar), (False, vCrossbar)]:
            points = self._chainPoints(horizontal)
            previousShort = False
            for start, end in zip(points, points[1:]):
                dim = self._orthogonal(start, end, horizontal, crossbar)
                if dim is None:
                    continue
                built = True
                # When the text doesn't fit the dimension, it would collide with
                # the neighbors. Therefore, move every second such text one
                # line further from the panel.
                dim.Update()
                textLength = dim.GetTextBox().GetWidth()
                short = textLength > abs(dim.GetMeasuredValue()) - 2 * self.textSize
                if short and previousShort:
                    previousShort = False
                    textPos = dim.GetTextPos()
                    shift = int(1.5 * self.textSize)
                    self._placeText(dim, VECTOR2I(textPos.x, textPos.y - shift) if horizontal
                                         else VECTOR2I(textPos.x - shift, textPos.y))
                else:
                    previousShort = short
        return built

    def _nearestCorner(self, pos: VECTOR2I) -> Tuple[int, int]:
        """
        Return direction towards the panel interior from the nearest corner as
        a tuple of signs (x, y).
        """
        sx = 1 if pos.x - self.minx <= self.maxx - pos.x else -1
        sy = 1 if pos.y - self.miny <= self.maxy - pos.y else -1
        return sx, sy

    def _dimensionFeature(self, pos: VECTOR2I, offset: KiLength) -> None:
        """
        Dimension feature position from the nearest panel edges. The dimension
        lines are offset towards the panel interior so they don't cross the
        feature.
        """
        sx, sy = self._nearestCorner(pos)
        edgeX = self.minx if sx > 0 else self.maxx
        edgeY = self.miny if sy > 0 else self.maxy
        # Place the text on the far side of the dimension line, so it doesn't
        # collide with the feature itself
        textShift = self.textSize
        hDim = self._orthogonal((edgeX, pos.y), (pos.x, pos.y), True, pos.y + sy * offset)
        if hDim is not None:
            self._placeText(hDim, VECTOR2I((edgeX + pos.x) // 2, pos.y + sy * (offset + textShift)))
        vDim = self._orthogonal((pos.x, edgeY), (pos.x, pos.y), False, pos.x + sx * offset)
        if vDim is not None:
            self._placeText(vDim, VECTOR2I(pos.x + sx * (offset + textShift), (edgeY + pos.y) // 2))

    def _placeText(self, dim: pcbnew.PCB_DIMENSION_BASE, position: VECTOR2I) -> None:
        dim.Update()
        angle = dim.GetTextAngle()
        dim.SetTextPositionMode(pcbnew.DIM_TEXT_POSITION_MANUAL)
        dim.SetTextPos(position)
        dim.SetTextAngle(angle)
        dim.Update()

    # The tooling holes and fiducials usually share the panel corners. The
    # following functions pick which instances are dimensioned and which carry
    # the leader so the annotations of the two groups don't overlap.

    def _corners(self, features) -> set:
        return {self._nearestCorner(f[0]) for f in features}

    def _shownTooling(self) -> list:
        if "tooling" not in self.include:
            return []
        holes = self.panel.toolingHoles
        return holes if self.coverage == "all" else holes[:1]

    def _shownFiducials(self) -> list:
        if "fiducials" not in self.include:
            return []
        fiducials = self.panel.fiducials
        if self.coverage == "all" or not fiducials:
            return fiducials
        toolingCorners = self._corners(self._shownTooling())
        return [next((f for f in fiducials if self._nearestCorner(f[0]) not in toolingCorners),
                     fiducials[0])]

    def _pickLeaderFeature(self, candidates: list, avoidCorners: set):
        return next((f for f in candidates if self._nearestCorner(f[0]) not in avoidCorners),
                    candidates[0])

    def _toolingLeaderHole(self):
        return self._pickLeaderFeature(self.panel.toolingHoles,
                                       self._corners(self._shownFiducials()))

    def _buildTooling(self) -> None:
        holes = self.panel.toolingHoles
        if not holes:
            return
        for pos, diameter in self._shownTooling():
            self._dimensionFeature(pos, diameter // 2 + self.textSize)
        pos, diameter = self._toolingLeaderHole()
        count = f"{len(holes)}× " if len(holes) > 1 else ""
        self._leader(pos, diameter // 2, f"{count}Ø{self._formatLength(diameter)} NPTH")

    def _buildFiducials(self) -> None:
        fiducials = self.panel.fiducials
        if not fiducials:
            return
        shown = self._shownFiducials()
        toolingCorners = self._corners(self._shownTooling())
        for pos, copper, opening in shown:
            offset = opening // 2 + self.textSize
            if self._nearestCorner(pos) in toolingCorners:
                # Make room for the tooling hole dimensions in the same corner
                offset += 2 * self.textSize
            self._dimensionFeature(pos, offset)
        leaderCorners = self._corners([self._toolingLeaderHole()]) \
                        if "tooling" in self.include and self.panel.toolingHoles else set()
        pos, copper, opening = self._pickLeaderFeature(shown, leaderCorners)
        count = f"{len(fiducials)}× " if len(fiducials) > 1 else ""
        self._leader(pos, opening // 2,
                     f"{count}FID Ø{self._formatLength(copper)}, MASK Ø{self._formatLength(opening)}")
