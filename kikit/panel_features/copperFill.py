from dataclasses import dataclass, field
from ..substrate import linestringToKicad
from ..defs import Layer
from ..common import KiAngle, KiLength, fromDegrees, fromMm
from ..pcbnew_utils import increaseZonePriorities
from pcbnewTransition import pcbnew
from ..panelize import Panel
from .baseFeature import PanelFeature
from typing import Any, List, Tuple
import numpy as np
from shapely.geometry import (
    Polygon,
    MultiPolygon)
from shapely.ops import unary_union

class KiCADCopperFillMixin(PanelFeature):
    """
    Build solid infill of non-board areas
    """
    def _adjustZoneParameters(self, zone: pcbnew.ZONE):
        """
        Allow an inherited class to override KiCAD zone parameters
        """
        pass  # solid infill does nothing

    def apply(self, panel: Any) -> None:
        if not len(self.layers) > 0:
            raise RuntimeError("No layers to add copper to")
        increaseZonePriorities(panel.board)

        zoneArea = panel.boardSubstrate.substrates.buffer(-self.edgeclearance)
        zoneArea = zoneArea.difference(unary_union(
            [substrate.exterior().buffer(self.clearance) for substrate in panel.substrates]
        ))

        geoms = [zoneArea] if isinstance(zoneArea, Polygon) else zoneArea.geoms

        for g in geoms:
            if len(g.exterior.coords) == 0:
                # Skip empty geometries
                continue
            zoneContainer = pcbnew.ZONE(panel.board)
            self._adjustZoneParameters(zoneContainer)
            zoneContainer.Outline().AddOutline(linestringToKicad(g.exterior))
            for hole in g.interiors:
                zoneContainer.Outline().AddHole(linestringToKicad(hole))
            zoneContainer.SetAssignedPriority(0)

            for l in self.layers:
                if not panel.board.GetEnabledLayers().Contains(l):
                    continue
                zoneContainer = zoneContainer.Duplicate()
                zoneContainer.SetLayer(l)
                panel.board.Add(zoneContainer)
                panel.zonesToRefill.append(zoneContainer)


@dataclass
class SolidCopperFill(KiCADCopperFillMixin):
    """
    Build solid infill of non-board areas
    """
    clearance: KiLength = field(default_factory=lambda: fromMm(1))
    edgeclearance: KiLength = field(default_factory=lambda: fromMm(1))
    layers: List[Layer] = field(default_factory=lambda: [Layer.F_Cu, Layer.B_Cu])

    def _adjustZoneParameters(self, zone: pcbnew.ZONE) -> None:
        pass # There are no adjustments for solid infill


@dataclass
class HatchedCopperFill(KiCADCopperFillMixin):
    """
    Build hatched infill of non-board areas
    """
    clearance: KiLength = field(default_factory=lambda: fromMm(1))
    edgeclearance: KiLength = field(default_factory=lambda: fromMm(1))
    layers: List[Layer] = field(default_factory=lambda: [Layer.F_Cu, Layer.B_Cu])
    strokeWidth: KiLength = field(default_factory=lambda: fromMm(1))
    strokeSpacing: KiLength = field(default_factory=lambda: fromMm(1))
    orientation: KiAngle = field(default_factory=lambda: fromDegrees(45))

    def _adjustZoneParameters(self, zoneContainer: pcbnew.ZONE) -> None:
        zoneContainer.SetFillMode(pcbnew.ZONE_FILL_MODE_HATCH_PATTERN)
        zoneContainer.SetHatchOrientation(self.orientation)
        zoneContainer.SetHatchGap(self.strokeSpacing)
        zoneContainer.SetHatchThickness(self.strokeWidth)

@dataclass
class HexCopperFill(PanelFeature):
    """
    Build hex infill of non-board areas
    """
    clearance: KiLength = field(default_factory=lambda: fromMm(1))
    edgeclearance: KiLength = field(default_factory=lambda: fromMm(1))
    layers: List[Layer] = field(default_factory=lambda: [Layer.F_Cu, Layer.B_Cu])
    diameter: KiLength = field(default_factory=lambda: fromMm(7))
    space: KiLength = field(default_factory=lambda: fromMm(0.5))
    threshold: float = field(default_factory=lambda: 0.25)

    def _buildHexagonsPolygon(self, area: Tuple[float, float, float, float]) -> MultiPolygon:
        horizontalSpacing = self.space + np.sqrt(3) / 2 * self.diameter
        verticalSpacing = 3 / 4 * self.diameter + np.sqrt(3) / 2 * self.space

        minx, miny, maxx, maxy = area

        maxx += horizontalSpacing
        maxy += horizontalSpacing

        hexagons = []
        y = miny
        shifted = False
        while y <= maxy:
            x = minx - (horizontalSpacing / 2 if shifted else 0)
            while x <= maxx:
                hexagons.append(Polygon([
                    (x + self.diameter / 2 * np.cos(np.pi / 6 + i / 3 * np.pi),
                     y + self.diameter / 2 * np.sin(np.pi / 6 + i / 3 * np.pi)) for i in range(6)
                ]))
                x += horizontalSpacing
            y += verticalSpacing
            shifted = not shifted

        return MultiPolygon(hexagons)

    def apply(self, panel: Panel) -> None:
        if not len(self.layers) > 0:
            raise RuntimeError("No layers to add copper to")

        increaseZonePriorities(panel.board)

        zoneArea = panel.boardSubstrate.substrates.buffer(-self.edgeclearance)
        zoneArea = zoneArea.intersection(panel.boardSubstrate.substrates)
        zoneArea = zoneArea.difference(unary_union(
            [substrate.exterior().buffer(self.clearance) for substrate in panel.substrates]
        ))

        hexagons = self._buildHexagonsPolygon(zoneArea.bounds)
        hexagons = hexagons.intersection(zoneArea)

        baseHexArea = 3 * np.sqrt(3) * (self.diameter / 2) ** 2 / 2

        geoms = [hexagons] if isinstance(hexagons, Polygon) else hexagons.geoms
        for g in geoms:
            if g.area < self.threshold * baseHexArea:
                continue
            zoneContainer = pcbnew.ZONE(panel.board)
            zoneContainer.Outline().AddOutline(linestringToKicad(g.exterior))
            for hole in g.interiors:
                zoneContainer.Outline().AddHole(linestringToKicad(hole))
            zoneContainer.SetAssignedPriority(0)

            for l in self.layers:
                if not panel.board.GetEnabledLayers().Contains(l):
                    continue
                zoneContainer = zoneContainer.Duplicate()
                zoneContainer.SetLayer(l)
                panel.board.Add(zoneContainer)
                panel.zonesToRefill.append(zoneContainer)
