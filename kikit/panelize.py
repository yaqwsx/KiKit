from copy import deepcopy
import itertools
import textwrap
from pcbnewTransition import pcbnew, isV6
from kikit import sexpr
from kikit.common import normalize

from pathlib import Path

from typing import Any, Callable, Dict, Iterable, List, Set, Tuple, Union

from pcbnewTransition.pcbnew import (LoadBoard, ToMM, VECTOR2I, BOX2I, EDA_ANGLE)
from enum import Enum
from shapely.geometry import (Polygon, MultiPolygon, Point, LineString, box,
                              GeometryCollection, MultiLineString)
from shapely.prepared import prep
import shapely
import shapely.affinity
from itertools import product, chain
import numpy as np
import os
import json
import re
import fnmatch
from collections import OrderedDict
from dataclasses import dataclass

from kikit import substrate
from kikit import units
from kikit.kicadUtil import getPageDimensionsFromAst
from kikit.substrate import Substrate, linestringToKicad, extractRings, TabError
from kikit.defs import PAPER_DIMENSIONS, STROKE_T, Layer, EDA_TEXT_HJUSTIFY_T, EDA_TEXT_VJUSTIFY_T, PAPER_SIZES
from kikit.common import *
from kikit.sexpr import isElement, parseSexprF, SExpr, Atom, findNode, parseSexprListF
from kikit.annotations import AnnotationReader, TabAnnotation
from kikit.drc import DrcExclusion, readBoardDrcExclusions, serializeExclusion
from kikit.units import mm, deg, inch
from kikit.pcbnew_utils import increaseZonePriorities

class PanelError(RuntimeError):
    pass

class TooLargeError(PanelError):
    pass

class NonFatalErrors(PanelError):
    def __init__(self, errors: List[Tuple[KiPoint, str]]) -> None:
        multiple = len(errors) > 1

        message = f"There {'are' if multiple else 'is'} {len(errors)} error{'s' if multiple else ''} in the panel. The panel with error markers was saved for inspection.\n\n"
        message += "The following errors occurred:\n"
        for pos, err in errors:
            message += f"- Location [{toMm(pos[0])}, {toMm(pos[1])}]\n"
            message += textwrap.indent(err, "  ")
        super().__init__(message)

def identity(x):
    return x

class GridPlacerBase:
    def position(self, i: int, j: int, boardSize: Optional[BOX2I]) -> VECTOR2I:
        """
        Given row and col coords of a board, return physical physical position
        of the board. All function calls (except for 0, 0) also receive board
        size.

        The position of the board is relative to the top-left board, coordinates
        (0, 0) should yield placement (0, 0).
        """
        raise NotImplementedError("GridPlacerBase.position has to be overridden")

    def rotation(self, i: int, j: int) -> KiAngle:
        """
        Given row and col coords of a board, return the orientation of the board
        """
        return EDA_ANGLE(0, pcbnew.DEGREES_T)

class BasicGridPosition(GridPlacerBase):
    """
    Specify board position in the grid.
    """
    def __init__(self, horSpace: int, verSpace: int,
                 hbonewidth: int=0, vbonewidth: int=0,
                 hboneskip: int=0, vboneskip: int=0,
                 hbonefirst: int=0, vbonefirst: int=0) -> None:
        self.horSpace = horSpace
        self.verSpace = verSpace
        self.hbonewidth = hbonewidth
        self.vbonewidth = vbonewidth
        self.hboneskip = hboneskip
        self.vboneskip = vboneskip
        self.hbonefirst = hbonefirst
        self.vbonefirst = vbonefirst

    def position(self, i: int, j: int, boardSize: Optional[BOX2I]) -> VECTOR2I:
        if boardSize is None:
            assert i == 0 and j == 0
            boardSize = BOX2I(VECTOR2I(0, 0), VECTOR2I(0, 0))
        hbonecount = 0 if self.hbonewidth == 0 \
                       else max((i + self.hbonefirst)  // (self.hboneskip + 1), 0)
        vbonecount = 0 if self.vbonewidth == 0 \
                       else max((j + self.vbonefirst) // (self.vboneskip + 1), 0)
        xPos = j * (boardSize.GetWidth() + self.horSpace) + \
               vbonecount * (self.vbonewidth + self.horSpace)
        yPos = i * (boardSize.GetHeight() + self.verSpace) + \
               hbonecount * (self.hbonewidth + self.verSpace)
        return toKiCADPoint((xPos, yPos))


class OddEvenRowsPosition(BasicGridPosition):
    """
    Rotate boards by 180° for every row
    """
    def rotation(self, i: int, j: int) -> KiAngle:
        if i % 2 == 0:
            return EDA_ANGLE(0, pcbnew.DEGREES_T)
        return EDA_ANGLE(180, pcbnew.DEGREES_T)

class OddEvenColumnPosition(BasicGridPosition):
    """
    Rotate boards by 180° for every column
    """
    def rotation(self, i: int, j: int) -> KiAngle:
        if j % 2 == 0:
            return EDA_ANGLE(0, pcbnew.DEGREES_T)
        return EDA_ANGLE(180, pcbnew.DEGREES_T)

class OddEvenRowsColumnsPosition(BasicGridPosition):
    """
    Rotate boards by 180 for every row and column
    """
    def rotation(self, i: int, j: int) -> KiAngle:
        if (i % 2) == (j % 2):
            return EDA_ANGLE(0, pcbnew.DEGREES_T)
        return EDA_ANGLE(180, pcbnew.DEGREES_T)


class Origin(Enum):
    Center = 0
    TopLeft = 1
    TopRight = 2
    BottomLeft = 3
    BottomRight = 4


class NetClass():
    """
    Internal representation of a netclass. Work-around for KiCAD 6.0.6 missing
    support for netclasses in API
    """
    def __init__(self, netClassDef: Any) -> None:
        self.data = netClassDef
        self.nets: Set[str] = set()

    @property
    def name(self) -> str:
        return self.data["name"]

    @property
    def originalNets(self) -> List[str]:
        return self.data.get("nets", [])

    def addNet(self, netname: str) -> None:
        self.nets.add(netname)

    def serialize(self) -> Any:
        data = deepcopy(self.data)
        if isV6():
            data["nets"] = list(self.nets)
        return data

def getOriginCoord(origin, bBox):
    """Returns real coordinates (VECTOR2I) of the origin for given bounding box"""
    if origin == Origin.Center:
        return VECTOR2I(bBox.GetX() + bBox.GetWidth() // 2,
                        bBox.GetY() + bBox.GetHeight() // 2)
    if origin == Origin.TopLeft:
        return VECTOR2I(bBox.GetX(), bBox.GetY())
    if origin == Origin.TopRight:
        return VECTOR2I(bBox.GetX() + bBox.GetWidth(), bBox.GetY())
    if origin == Origin.BottomLeft:
        return VECTOR2I(bBox.GetX(), bBox.GetY() + bBox.GetHeight())
    if origin == Origin.BottomRight:
        return VECTOR2I(bBox.GetX() + bBox.GetWidth(), bBox.GetY() + bBox.GetHeight())

def appendItem(board: pcbnew.BOARD, item: pcbnew.BOARD_ITEM,
               yieldMapping: Optional[Callable[[str, str], None]]=None) -> None:
    """
    Make a coppy of the item and append it to the board. Allows to append items
    from one board to another.

    It can also yield mapping between old item identifier and a new one via the
    yieldMapping callback. This callback is invoked with an old ID and the new
    ID. Mapping is applicable only in v6.
    """
    try:
        newItem = item.Duplicate()
    except TypeError: # Footprint has overridden the method, cannot be called directly
        newItem = pcbnew.Cast_to_BOARD_ITEM(item).Duplicate().Cast()
    board.Add(newItem)
    if not yieldMapping:
        return
    if isinstance(item, pcbnew.FOOTPRINT):
        newFootprint = pcbnew.Cast_to_FOOTPRINT(newItem)
        for getter in [lambda x: x.Pads(), lambda x: x.GraphicalItems(), lambda x: x.Zones()]:
            oldList = getter(item)
            newList = getter(newFootprint)
            assert len(oldList) == len(newList)
            for o, n in zip(oldList, newList):
                assert o.GetPosition() == n.GetPosition()
                yieldMapping(o.m_Uuid.AsString(), n.m_Uuid.AsString())
    yieldMapping(item.m_Uuid.AsString(), newItem.m_Uuid.AsString())

def collectNetNames(board):
    return [str(x) for x in board.GetNetInfo().NetsByName() if len(str(x)) > 0]

def remapNets(collection, mapping):
    for item in collection:
        item.SetNetCode(mapping[item.GetNetname()].GetNetCode())

ToPolygonGeometry = Union[Polygon, BOX2I, Substrate]
def toPolygon(entity: Union[List[ToPolygonGeometry], ToPolygonGeometry]) -> Polygon:
    if isinstance(entity, list):
        return list([toPolygon(e) for e in entity])
    if isinstance(entity, Polygon) or isinstance(entity, MultiPolygon):
        return entity
    if isinstance(entity, BOX2I):
        return Polygon([
            (entity.GetX(), entity.GetY()),
            (entity.GetX() + entity.GetWidth(), entity.GetY()),
            (entity.GetX() + entity.GetWidth(), entity.GetY() + entity.GetHeight()),
            (entity.GetX(), entity.GetY() + entity.GetHeight())])
    if isinstance(entity, Substrate):
        return Substrate.substrates
    raise NotImplementedError("Cannot convert {} to Polygon".format(type(entity)))

def rectString(rect):
    return "({}, {}) w: {}, h: {}".format(
                ToMM(rect.GetX()), ToMM(rect.GetY()),
                ToMM(rect.GetWidth()), ToMM(rect.GetHeight()))

def expandRect(rect: BOX2I, offsetX: KiLength, offsetY: Optional[KiLength]=None):
    """
    Given a BOX2I returns a new rectangle, which is larger in all directions
    by offset. If only offsetX is passed, it used for both X and Y offset
    """
    if offsetY is None:
        offsetY = offsetX
    offsetX = int(offsetX)
    offsetY = int(offsetY)
    return BOX2I(
            VECTOR2I(rect.GetX() - offsetX, rect.GetY() - offsetY),
            VECTOR2I(rect.GetWidth() + 2 * offsetX, rect.GetHeight() + 2 * offsetY))

def rectToRing(rect):
    return [
        (rect.GetX(), rect.GetY()),
        (rect.GetX() + rect.GetWidth(), rect.GetY()),
        (rect.GetX() + rect.GetWidth(), rect.GetY() + rect.GetHeight()),
        (rect.GetX(), rect.GetY() + rect.GetHeight())
    ]

def roundPoint(point, precision=-4):
    if isinstance(point, Point):
        return Point(round(point.x, precision), round(point.y, precision))
    return Point(round(point[0], precision), round(point[1], precision))

def doTransformation(point: KiPoint, rotation: KiAngle, origin: KiPoint, translation: KiPoint) -> VECTOR2I:
    """
    Abuses KiCAD to perform a tranformation of a point
    """
    segment = pcbnew.PCB_SHAPE()
    segment.SetShape(STROKE_T.S_SEGMENT)
    segment.SetStart(toKiCADPoint(point))
    segment.SetEnd(VECTOR2I(0, 0))
    segment.Rotate(toKiCADPoint(origin), -1 * rotation)
    segment.Move(toKiCADPoint(translation))
    # We build a fresh VECTOR2I - otherwise there is a shared reference
    return VECTOR2I(segment.GetStartX(), segment.GetStartY())

def undoTransformation(point, rotation, origin, translation):
    """
    We apply a transformation "Rotate around origin and then translate" when
    placing a board. Given a point and original transformation parameters,
    return the original point position.
    """
    # Abuse PcbNew to do so
    segment = pcbnew.PCB_SHAPE()
    segment.SetShape(STROKE_T.S_SEGMENT)
    segment.SetStart(VECTOR2I(int(point[0]), int(point[1])))
    segment.SetEnd(VECTOR2I(0, 0))
    segment.Move(VECTOR2I(-translation[0], -translation[1]))
    segment.Rotate(origin, -1 * rotation)
    # We build a fresh VECTOR2I - otherwise there is a shared reference
    return VECTOR2I(segment.GetStartX(), segment.GetStartY())

def removeCutsFromFootprint(footprint):
    """
    Find all graphical items in the footprint, remove them and return them as a
    list
    """
    edges = []
    for edge in footprint.GraphicalItems():
        if edge.GetLayer() != Layer.Edge_Cuts:
            continue
        edges.append(edge)
    for e in edges:
        footprint.Remove(e)
    return edges

def renameNets(board, renamer):
    """
    Given a board and renaming function (taking original name, returning new
    name) renames the nets
    """
    originalNetNames = collectNetNames(board)
    netinfo = board.GetNetInfo()

    newNetMapping = { "": netinfo.GetNetItem("") }
    newNames = set()
    for name in originalNetNames:
        newName = renamer(name)
        newNet = pcbnew.NETINFO_ITEM(board, newName)
        newNetMapping[name] = newNet
        board.Add(newNet)
        newNames.add(newName)

    remapNets(board.GetPads(), newNetMapping)
    remapNets(board.GetTracks(), newNetMapping)
    remapNets(board.Zones(), newNetMapping)

    for name in originalNetNames:
        if name != "" and name not in newNames:
            board.RemoveNative(netinfo.GetNetItem(name))

def renameRefs(board, renamer):
    """
    Given a board and renaming function (taking original name, returning new
    name) renames the references
    """
    for footprint in board.GetFootprints():
        ref = footprint.Reference().GetText()
        footprint.Reference().SetText(renamer(ref))

def isBoardEdge(edge):
    """
    Decide whether the drawing is a board edge or not.

    The rule is: all drawings on Edge.Cuts layer are edges.
    """
    return isinstance(edge, pcbnew.PCB_SHAPE) and edge.GetLayerName() == "Edge.Cuts"

def tabSpacing(width, count):
    """
    Given a width of board edge and tab count, return an iterable with tab
    offsets.
    """
    return [width * i / (count + 1) for i in range(1, count + 1)]

def prolongCut(cut, prolongation):
    """
    Given a cut (Shapely LineString) it tangentially prolongs it by prolongation
    """
    c = list([np.array(x) for x in cut.coords])
    c[0] += normalize(c[0] - c[1]) * prolongation
    c[-1] += normalize(c[-1] - c[-2]) * prolongation
    return LineString(c)

def polygonToZone(polygon, board):
    """
    Given a polygon and target board, creates a KiCAD zone. The zone has to be
    added to the board.
    """
    zone = pcbnew.ZONE(board)
    boundary = polygon.exterior
    zone.Outline().AddOutline(linestringToKicad(boundary))
    for hole in polygon.interiors:
        boundary = hole.exterior
        zone.Outline().AddHole(linestringToKicad(boundary))
    return zone

def buildTabs(panel: "Panel", substrate: Substrate,
              partitionLines: Union[GeometryCollection, LineString],
              tabAnnotations: Iterable[TabAnnotation], fillet: KiLength = 0) -> \
                Tuple[List[Polygon], List[LineString]]:
    """
    Given substrate, partitionLines of the substrate and an iterable of tab
    annotations, build tabs. Note that if the tab does not hit the partition
    line, it is not included in the design.

    Return a pair of lists: tabs and cuts.
    """
    tabs, cuts = [], []
    for annotation in tabAnnotations:
        try:
            t, c = substrate.tab(annotation.origin, annotation.direction,
                annotation.width, partitionLines, annotation.maxLength, fillet)
            if t is not None:
                tabs.append(t)
                cuts.append(c)
        except TabError as e:
            panel._renderLines(
                [constructArrow(annotation.origin, annotation.direction, fromMm(3), fromMm(1))],
                Layer.Margin)
            panel.reportError(toKiCADPoint(e.origin), str(e))
    return tabs, cuts

def normalizePartitionLineOrientation(line):
    """
    Given a LineString or MultiLineString, normalize orientation of the
    partition line. For open linestrings, the orientation does not matter. For
    closed linerings, it has to be counter-clock-wise.
    """
    if isinstance(line, MultiLineString):
        return MultiLineString([normalizePartitionLineOrientation(x) for x in line.geoms])
    if isinstance(line, GeometryCollection):
        return GeometryCollection([normalizePartitionLineOrientation(l) for l in line.geoms])
    if not isLinestringCyclic(line):
        return line
    r = LinearRing(line.coords)
    if not r.is_ccw:
        return line
    return LineString(list(r.coords)[::-1])

def maxTabCount(edgeLen, width, minDistance):
    """
    Given a length of edge, tab width and their minimal distance, return maximal
    number of tabs.
    """
    if edgeLen < width:
        return 0
    c = 1 + (edgeLen - minDistance) // (minDistance + width)
    return max(0, int(c))

def skipBackbones(backbones: List[LineString], skip: int, first: int,
                  key: Callable[[LineString], int]) -> List[LineString]:
    """
    Given a list of backbones, get only every (skip + 1) other one. Treats
    all backbones on a given coordinate as one.
    """
    candidates = list(set(map(key, backbones)))
    candidates.sort()
    active = set(itertools.islice(candidates, first - 1, None, skip + 1))
    return [x for x in backbones if key(x) in active]

def bakeTextVars(board: pcbnew.BOARD) -> None:
    """
    Given a board, expand text variables in all text items on the board.
    """
    for drawing in board.GetDrawings():
        if not isinstance(drawing, pcbnew.PCB_TEXT):
            continue
        if isV8():
            drawing.SetText(drawing.GetShownText(True))
        else:
            drawing.SetText(drawing.GetShownText())

@dataclass
class VCutSettings:
    lineWidth: KiLength = fromMm(0.4)
    textThickness: KiLength = fromMm(0.4)
    textSize: KiLength = fromMm(2)
    endProlongation: KiLength = fromMm(3)
    textProlongation: KiLength = fromMm(3)
    layer: Layer = Layer.Cmts_User
    textTemplate: str = "V-CUT {pos_mm}"
    textOffset: KiLength = fromMm(3)
    clearance: KiLength = 0


class Panel:
    """
    Basic interface for panel building. Instance of this class represents a
    single panel. You can append boards, add substrate pieces, make cuts or add
    holes to the panel. Once you finish, you have to save the panel to a file.

    Since KiCAD 6, the board is coupled with a project files (DRC rules), so
    we have to specify a filename when creating a panel. Corresponding project
    file will be created.
    """

    def __init__(self, panelFilename):
        """
        Initializes empty panel. Note that due to the restriction of KiCAD 6,
        when boards are always associated with a project, you have to pass a
        name of the resulting file.
        """
        self.errors: List[Tuple[KiPoint, str]] = []

        self.filename = panelFilename
        self.board = pcbnew.NewBoard(panelFilename)
        self.sourcePaths = set() # A set of all board files that were appended to the panel
        self.substrates = [] # Substrates of the individual boards; e.g. for masking
        self.boardSubstrate = Substrate([]) # Keep substrate in internal representation,
                                            # Draw it just before saving
        self.backboneLines = []
        self.hVCuts = set() # Keep V-cuts as numbers and append them just before saving
        self.vVCuts = set() # to make them truly span the whole panel
        self.vCutSettings = VCutSettings()
        self.copperLayerCount = None
        self.renderedMousebiteCounter = 0
        self.zonesToRefill = pcbnew.ZONES()
        self.pageSize: Union[None, str, Tuple[int, int]] = None

        self.annotationReader: AnnotationReader = AnnotationReader.getDefault()
        self.drcExclusions: List[DrcExclusion] = []
        # At the moment (KiCAD 6.0.6) has broken support for net classes.
        # Therefore we have to handle them separately
        self.newNetClasses: Dict[str, Any] = {}
        self.netCLassPatterns: List[Dict[str, str]] = []
        self.customDRCRules: List[SExpr] = []

        # KiCAD allows to keep text variables for project. We keep a set of
        # dictionary of variables for each appended board.
        self.projectVars: List[Dict[str, str]] = []

        # We want to prolong dimensions of the panel by the size of fillet or
        # chamfer, thus, we have to remember them
        self.filletSize: Optional[KiLength] = None
        self.chamferWidth: Optional[KiLength] = None
        self.chamferHeight: Optional[KiLength] = None

    def reportError(self, position: KiPoint, message: str) -> None:
        """
        Reports a non-fatal error. The error is marked and rendered to the panel
        """
        footprint = pcbnew.FootprintLoad(KIKIT_LIB, "Error")
        footprint.SetPosition(position)
        for x in footprint.GraphicalItems():
            if not isinstance(x, pcbnew.PCB_TEXTBOX):
                continue
            text = x.GetText()
            if text == "MESSAGE":
                x.SetText(message)
        self.board.Add(footprint)

        self.errors.append((position, message))

    def hasErrors(self) -> bool:
        """
        Report if panel has any non-fatal errors presents
        """
        return len(self.errors) > 0

    def save(self, reconstructArcs: bool=False, refillAllZones: bool=False,
             edgeWidth: KiLength=fromMm(0.1)):
        """
        Saves the panel to a file and makes the requested changes to the prl and
        pro files.
        """
        panelEdges = self.boardSubstrate.serialize(reconstructArcs)
        boardsEdges = self._getRefillEdges(reconstructArcs)

        for e in panelEdges:
            e.SetWidth(edgeWidth)
        for e in boardsEdges:
            e.SetWidth(edgeWidth)

        vcuts = self._renderVCutH() + self._renderVCutV()
        keepouts = []
        for cut, clearanceArea in vcuts:
            self.board.Add(cut)
            if clearanceArea is not None:
                keepouts.append(self.addKeepout(clearanceArea))

        # Rendering happens in two phases:
        # - first, we render original board edges and save the board (to
        #   propagate all the design rules from project files)
        # - then we load the board, fill polygons and render panel edges.

        for edge in boardsEdges:
            self.board.Add(edge)

        # We mark zone to refill via name prefix - this is the only way we can
        # remember it between saves
        originalZoneNames = {}
        for i, zone in enumerate(self.zonesToRefill):
            newName = f"KIKIT_zone_{i}"
            originalZoneNames[newName] = zone.GetZoneName()
            zone.SetZoneName(newName)
        self.board.Save(self.filename)

        self.makeLayersVisible() # as they are not in KiCAD 6
        self.transferProjectSettings()
        self.writeCustomDrcRules()

        # Remove cuts
        for cut, _ in vcuts:
            self.board.Remove(cut)
        # Remove V-cuts keepouts
        for keepout in keepouts:
            self.board.Remove(keepout)
        # Remove edges
        for edge in panelEdges:
            self.board.Remove(edge)

        # Handle zone refilling in a separate board
        fillBoard = pcbnew.LoadBoard(self.filename)
        fillerTool = pcbnew.ZONE_FILLER(fillBoard)
        if refillAllZones:
            fillerTool.Fill(fillBoard.Zones())

        for edge in collectEdges(fillBoard, Layer.Edge_Cuts):
            fillBoard.Remove(edge)
        for edge in panelEdges:
            fillBoard.Add(edge)
        if self.vCutSettings.layer == Layer.Edge_Cuts:
            vcuts = self._renderVCutH() + self._renderVCutV()
            for cut, _ in vcuts:
                fillBoard.Add(cut)

        zonesToRefill = pcbnew.ZONES()
        for zone in fillBoard.Zones():
            zName = zone.GetZoneName()
            if zName.startswith("KIKIT_zone_"):
                zonesToRefill.append(zone)
                zone.SetZoneName(originalZoneNames[zName])
        fillerTool.Fill(zonesToRefill)

        fillBoard.Save(self.filename)
        self._adjustPageSize()

    def _getRefillEdges(self, reconstructArcs: bool):
        """
        Builds a list of edges that represent boards outlines and panel
        surrounding as independent pieces of substrate
        """
        boardsEdges = list(chain(*[sub.serialize(reconstructArcs) for sub in self.substrates]))

        surrounding = self.boardSubstrate.substrates.simplify(fromMm(0.01)).difference(
            shapely.ops.unary_union(list(
                sub.substrates.buffer(fromMm(0.2)) for sub in self.substrates)).simplify(fromMm(0.01)))
        surroundingSubstrate = Substrate([])
        surroundingSubstrate.union(surrounding)
        boardsEdges += surroundingSubstrate.serialize()
        return boardsEdges

    def _uniquePrefix(self):
        return "Board_{}-".format(len(self.substrates))

    def getProFilepath(self, path=None):
        if path == None:
            p = self.filename
        else:
            p = path
        return os.path.splitext(p)[0]+'.kicad_pro'

    def getPrlFilepath(self, path=None):
        if path == None:
            p = self.filename
        else:
            p = path
        return os.path.splitext(p)[0]+'.kicad_prl'

    def getDruFilepath(self, path=None):
        if path == None:
            p = self.filename
        else:
            p = path
        return os.path.splitext(p)[0]+'.kicad_dru'

    def makeLayersVisible(self):
        """
        Modify corresponding *.prl files so all the layers are visible by
        default
        """
        try:
            with open(self.getPrlFilepath(), encoding="utf-8") as f:
                # We use ordered dict, so we preserve the ordering of the keys and
                # thus, formatting
                prl = json.load(f, object_pairs_hook=OrderedDict)
            prl["board"]["visible_layers"] = "fffffff_ffffffff"
            with open(self.getPrlFilepath(), "w", encoding="utf-8") as f:
                json.dump(prl, f, indent=2)
        except IOError:
            # The PRL file is not always created, ignore it
            pass

    def writeCustomDrcRules(self):
        with open(self.getDruFilepath(), "w+", encoding="utf-8") as f:
            f.write("(version 1)\n\n")
            for r in self.customDRCRules:
                f.write(str(r))

    def transferProjectSettings(self):
        """
        Examine DRC rules of the source boards, merge them into a single set of
        rules and store them in *.kicad_pro file. Also stores board DRC
        exclusions.

        Also, transfers the list of net classes from the internal representation
        into the project file.
        """
        if len(self.sourcePaths) > 1:
            raise RuntimeError("Merging of DRC rules of multiple boards is currently unsupported")
        if len(self.sourcePaths) == 0:
            return # Nothing to merge

        sPath = list(self.sourcePaths)[0]
        try:
            with open(self.getProFilepath(sPath), encoding="utf-8") as f:
                sourcePro = json.load(f)
        except (IOError, FileNotFoundError):
            # This means there is no original project file. Probably comes from
            # v5, thus there is nothing to transfer
            return
        try:
            with open(self.getProFilepath(), encoding="utf-8") as f:
                currentPro = json.load(f, object_pairs_hook=OrderedDict)
            currentPro["board"]["design_settings"] = sourcePro["board"]["design_settings"]
            currentPro["board"]["design_settings"]["drc_exclusions"] = [
                serializeExclusion(e) for e in self.drcExclusions]
            currentPro["board"]["design_settings"]["rule_severities"] = sourcePro["board"]["design_settings"]["rule_severities"]
            currentPro["text_variables"] = sourcePro.get("text_variables", {})

            currentPro["net_settings"]["classes"] = sourcePro["net_settings"]["classes"]
            currentPro["net_settings"]["classes"] += [x.serialize() for x in self.newNetClasses.values()]
            currentPro["net_settings"]["netclass_patterns"] = self.netCLassPatterns

            with open(self.getProFilepath(), "w", encoding="utf-8") as f:
                json.dump(currentPro, f, indent=2)
        except (KeyError, FileNotFoundError):
            # This means the source board has no DRC setting. Probably a board
            # without attached project
            pass

    def _assignNetToClasses(self, nets: Iterable[str], patterns: List[Tuple[str, str]])\
            -> Dict[str, Set[str]]:
        def safeCompile(p):
            try:
                return re.compile(p)
            except Exception:
                return None

        regexes = [
            (netclass, safeCompile(pattern)) for netclass, pattern in patterns
        ]

        assignment: Dict[str, Set[str]] = {
            netclass: set() for netclass, _ in patterns
        }

        for net in nets:
            for netclass, pattern in patterns:
                if fnmatch.fnmatch(net, pattern):
                    assignment[netclass].add(net)
            for netclass, regex in regexes:
                if regex is not None and regex.match(net):
                    assignment[netclass].add(net)

        return assignment

    def _inheritNetClasses(self, board, netRenamer):
        """
        KiCADhas broken API for net classes. Therefore, we have to load and save
        the net classes manually in the project file.

        KiCAD 6 uses the approach of explicitly listing all nets, KiCAD 7 uses
        patterns instead. The code below tries to cover both cases in a
        non-conflicting way.
        """
        proFilename = os.path.splitext(board.GetFileName())[0]+'.kicad_pro'
        try:
            with open(proFilename, encoding="utf-8") as f:
                project = json.load(f)
        except FileNotFoundError:
            # If the source board doesn't contain project, there's nothing to
            # inherit.
            return

        boardNetsNames = collectNetNames(board)
        netClassPatterns = [
            (p["netclass"], p["pattern"])
            for p in project["net_settings"].get("netclass_patterns", [])
        ]
        netAssignment = self._assignNetToClasses(boardNetsNames, netClassPatterns)

        seenNets = set()
        for c in project["net_settings"]["classes"]:
            origName = c["name"]
            c["name"] = netRenamer(c["name"])
            nc = NetClass(c)
            for net in chain(nc.originalNets, netAssignment.get(origName, [])):
                seenNets.add(net)
                nc.addNet(netRenamer(net))
            self.newNetClasses[nc.name] = nc

        defaultNetClass = self.newNetClasses[netRenamer("Default")]
        for name in boardNetsNames:
            if name in seenNets:
                continue
            defaultNetClass.addNet(netRenamer(name))

        for net in defaultNetClass.nets:
            self.netCLassPatterns.append({
                "netclass": defaultNetClass.name,
                "pattern": net
            })
        for netclass, pattern in netClassPatterns:
            self.netCLassPatterns.append({
                "netclass": netRenamer(netclass),
                "pattern": netRenamer(pattern)
            })

    def _inheriCustomDrcRules(self, board, netRenamer):
        """
        KiCADhas has no API for custom DRC rules, so we read the source files
        instead.

        The inheritance works as follows:
        - we rename each rule via net renamer
        - if the rule contains condition, we identify boolean operations equals
          and not equals for net names and net classes and rename the nets
        """
        proFilename = os.path.splitext(board.GetFileName())[0]+'.kicad_dru'
        try:
            with open(proFilename, encoding="utf-8") as f:
                rules = parseSexprListF(f)
        except FileNotFoundError:
            # If the source board doesn't contain DRU files, there's nothing to
            # inherit.
            return

        conditionRegex = re.compile(r"((A|B)\.Net(Class|Name)\s*?(==|!=)\s*?)'(.*?)'")

        for rule in rules:
            if isElement("version")(rule):
                continue
            elif isElement("rule")(rule):
                # Rename rule
                rule.items[1].value = netRenamer(rule.items[1].value)
                for clause in rule.items[2:]:
                    if isElement("condition")(clause):
                        # Rename net classes and names in the condition
                        clause.items[1].value = conditionRegex.sub(
                            lambda m: f"{m.group(1)}'{netRenamer(m.group(5))}'", clause.items[1].value)
                self.customDRCRules.append(rule)
            else:
                raise RuntimeError(f"Unkwnown custom DRC rule {rule}")

    def _adjustPageSize(self) -> None:
        """
        Open the just saved panel file and syntactically change the page size.
        At the moment, there is no API do so, therefore this extra step is
        required.
        """
        if self.pageSize is None:
            return
        with open(self.filename, "r", encoding="utf-8") as f:
            tree = parseSexprF(f, limit=10) # Introduce limit to speed up parsing
        # Find paper property
        paperExpr = None
        for subExpr in tree:
            if not isinstance(subExpr, SExpr):
                continue
            if len(subExpr) > 0 and isinstance(subExpr[0], Atom) and subExpr[0].value == "paper":
                paperExpr = subExpr
                break
        assert paperExpr is not None

        if isinstance(self.pageSize, str):
            paperProps = self.pageSize.split("-")
            paperExpr.items = [
                Atom("paper"),
                Atom(paperProps[0], " ", quoted=True)
            ]
            if len(paperProps) > 1:
                paperExpr.items.append(Atom("portrait", " "))
        else:
            pageSize = [float(x) / units.mm for x in self.pageSize]
            paperExpr.items = [
                Atom("paper"),
                Atom("User", " ", quoted=True),
                Atom(str(pageSize[0]), " "),
                Atom(str(pageSize[1]), " "),
            ]

        with open(self.filename, "w", encoding="utf-8") as f:
            f.write(str(tree))


    def inheritDesignSettings(self, board):
        """
        Inherit design settings from the given board specified by a filename or
        a board
        """
        if not isinstance(board, pcbnew.BOARD):
            board = pcbnew.LoadBoard(board)
        self.setDesignSettings(board.GetDesignSettings())

    def setDesignSettings(self, designSettings):
        """
        Set design settings
        """
        d = self.board.GetDesignSettings()
        d.CloneFrom(designSettings)

    def inheritProperties(self, board):
        """
        Inherit text properties from a board specified by a filename or a board
        """
        if not isinstance(board, pcbnew.BOARD):
            board = pcbnew.LoadBoard(board)
        self.board.SetProperties(board.GetProperties())

    def inheritPageSize(self, board: Union[pcbnew.BOARD, str]) -> None:
        """
        Inherit page size from a board specified by a filename or a board
        """
        if not isinstance(board, pcbnew.BOARD):
            board = pcbnew.LoadBoard(board)
        self.board.SetPageSettings(board.GetPageSettings())
        self.pageSize = None

        # What follows is a hack as KiCAD has no API for page access. Therefore,
        # we have to read out the page size from the source board and save it so
        # we can recover it.
        with open(board.GetFileName(), "r", encoding="utf-8") as f:
            tree = parseSexprF(f, limit=10) # Introduce limit to speed up parsing
        self._inheritedPageDimensions = getPageDimensionsFromAst(tree)

    def setPageSize(self, size: Union[str, Tuple[int, int]] ) -> None:
        """
        Set page size - either a string name (e.g., A4) or size in KiCAD units
        """
        if isinstance(size, str):
            if size not in PAPER_SIZES:
                raise RuntimeError(f"Unknown paper size: {size}")
        self.pageSize = size

    def getPageDimensions(self) -> Tuple[KiLength, KiLength]:
        """
        Get page size in KiCAD units for the current panel
        """
        if self.pageSize is None:
            return self._inheritedPageDimensions
        if isinstance(self.pageSize, tuple):
            return self.pageSize
        if isinstance(self.pageSize, str):
            if self.pageSize.endswith("-portrait"):
                # Portrait
                pageSize = PAPER_DIMENSIONS[self.pageSize.split("-")[0]]
                return pageSize[1], pageSize[0]
            else:
                return PAPER_DIMENSIONS[self.pageSize]
        raise RuntimeError("Unknown page dimension - this is probably a bug and you should report it.")

    def setProperties(self, properties):
        """
        Set text properties cached in the board
        """
        self.board.SetProperties(properties)

    def inheritTitleBlock(self, board):
        """
        Inherit title block from a board specified by a filename or a board
        """
        if not isinstance(board, pcbnew.BOARD):
            board = pcbnew.LoadBoard(board)
        self.setTitleBlock(board.GetTitleBlock())

    def setTitleBlock(self, titleBlock):
        """
        Set panel title block
        """
        self.board.SetTitleBlock(titleBlock)

    def appendBoard(self, filename: Union[str, Path], destination: VECTOR2I,
                    sourceArea: Optional[BOX2I] = None,
                    origin: Origin = Origin.Center,
                    rotationAngle: KiAngle = fromDegrees(0),
                    shrink: bool = False, tolerance: KiLength = 0,
                    bufferOutline: KiLength = fromMm(0.001),
                    netRenamer: Optional[Callable[[int, str], str]] = None,
                    refRenamer: Optional[Callable[[int, str], str]] = None,
                    inheritDrc: bool = True, interpretAnnotations: bool=True,
                    bakeText: bool = False):
        """
        Appends a board to the panel.

        The sourceArea (BOX2I) of the board specified by filename is extracted
        and placed at destination (VECTOR2I). The source area (BOX2I) can be
        auto detected if it is not provided. Only board items which fit entirely
        into the source area are selected. You can also specify rotation. Both
        translation and rotation origin are specified by origin. Origin
        specifies which point of the sourceArea is used for translation and
        rotation (origin it is placed to destination). It is possible to specify
        coarse source area and automatically shrink it if shrink is True.
        Tolerance enlarges (even shrinked) source area - useful for inclusion of
        filled zones which can reach out of the board edges or footprints that
        extend outside the board outline, like connectors.

        You can also specify functions which will rename the net and ref names.
        By default, nets are renamed to "Board_{n}-{orig}", refs are unchanged.
        The renamers are given board seq number and original name.

        You can also decide whether you would like to inherit design rules from
        this boards or not.

        Similarly, you can substitute variables in the text via bakeText.

        Returns bounding box (BOX2I) of the extracted area placed at the
        destination and the extracted substrate of the board.
        """
        # Since we want to follow KiCAD's new API, we require angles to be given
        # as EDA_ANGLE. However, there might be old scripts that will pass a
        # number.
        if not isinstance(rotationAngle, EDA_ANGLE):
            raise RuntimeError("Board rotation has to be passed as EDA_ANGLE, not a number")


        board = LoadBoard(str(filename))
        if inheritDrc:
            self.sourcePaths.add(filename)
        if bakeText:
            bakeTextVars(board)

        thickness = board.GetDesignSettings().GetBoardThickness()
        if len(self.substrates) == 0:
            self.board.GetDesignSettings().SetBoardThickness(thickness)
        else:
            panelThickness = self.board.GetDesignSettings().GetBoardThickness()
            if panelThickness != thickness:
                raise PanelError(f"Cannot append board {filename} as its " \
                                 f"thickness ({toMm(thickness)} mm) differs from " \
                                 f"thickness of the panel ({toMm(panelThickness)}) mm")
        self.inheritCopperLayers(board)

        if not sourceArea:
            sourceArea = findBoardBoundingBox(board)
        elif shrink:
            sourceArea = findBoardBoundingBox(board, sourceArea)
        enlargedSourceArea = expandRect(sourceArea, tolerance)
        originPoint = getOriginCoord(origin, sourceArea)
        translation = VECTOR2I(destination[0] - originPoint[0],
                              destination[1] - originPoint[1])

        if netRenamer is None:
            netRenamer = lambda x, y: self._uniquePrefix() + y
        bId = len(self.substrates)
        netRenamerFn = lambda x: netRenamer(bId, x)

        self._inheritNetClasses(board, netRenamerFn)
        self._inheriCustomDrcRules(board, netRenamerFn)

        renameNets(board, netRenamerFn)
        if refRenamer is not None:
            renameRefs(board, lambda x: refRenamer(len(self.substrates), x))

        drawings = collectItems(board.GetDrawings(), enlargedSourceArea)
        footprints = collectFootprints(board.GetFootprints(), enlargedSourceArea)
        tracks = collectItems(board.GetTracks(), enlargedSourceArea)
        zones = collectZones(board.Zones(), enlargedSourceArea)

        itemMapping: Dict[str, str] = {} # string KIID to string KIID
        def yieldMapping(old: str, new: str) -> None:
            nonlocal itemMapping
            itemMapping[old] = new

        edges = []
        annotations = []
        for footprint in footprints:
            # We want to rotate text within footprints by the requested amount,
            # even if that text has "keep upright" attribute set. For that,
            # the attribute must be first removed without changing the
            # orientation of the text.
            for item in (*footprint.GraphicalItems(), footprint.Value(), footprint.Reference()):
                if isinstance(item, pcbnew.FIELD_TYPE) and item.IsKeepUpright():
                    actualOrientation = item.GetDrawRotation()
                    item.SetKeepUpright(False)
                    alteredOrientation = item.GetDrawRotation()
                    item.SetTextAngle(item.GetTextAngle() + (alteredOrientation - actualOrientation))
            footprint.Rotate(originPoint, rotationAngle)
            footprint.Move(translation)
            edges += removeCutsFromFootprint(footprint)
            if interpretAnnotations and self.annotationReader.isAnnotation(footprint):
                annotations.extend(self.annotationReader.convertToAnnotation(footprint))
            else:
                appendItem(self.board, footprint, yieldMapping)
        for track in tracks:
            track.Rotate(originPoint, rotationAngle)
            track.Move(translation)
            appendItem(self.board, track, yieldMapping)
        for zone in zones:
            zone.Rotate(originPoint, rotationAngle)
            zone.Move(translation)
            appendItem(self.board, zone, yieldMapping)
        for netId in board.GetNetInfo().NetsByNetcode():
            self.board.Add(board.GetNetInfo().GetNetItem(netId))

        # Treat drawings differently since they contains board edges
        for drawing in drawings:
            drawing.Rotate(originPoint, rotationAngle)
            drawing.Move(translation)
        edges += [edge for edge in drawings if isBoardEdge(edge)]
        otherDrawings = [edge for edge in drawings if not isBoardEdge(edge)]

        def makeRevertTransformation(angle, origin, translation):
            def f(point):
                return undoTransformation(point, angle, origin, translation)
            return f

        revertTransformation = makeRevertTransformation(rotationAngle, originPoint, translation)
        try:
            s = Substrate(edges, 0,
                revertTransformation=revertTransformation)
            self.boardSubstrate.union(s)
            self.substrates.append(s)
            self.substrates[-1].annotations = annotations
        except substrate.PositionError as e:
            point = undoTransformation(e.point, rotationAngle, originPoint, translation)
            raise substrate.PositionError(f"{filename}: {e.origMessage}", point)
        for drawing in otherDrawings:
            appendItem(self.board, drawing, yieldMapping)

        try:
            exclusions = readBoardDrcExclusions(board)
            for drcE in exclusions:
                try:
                    newObjects = [self.board.GetItem(pcbnew.KIID(itemMapping[x.m_Uuid.AsString()])) for x in drcE.objects]
                    assert all(x is not None for x in newObjects)
                    newPosition = doTransformation(drcE.position, rotationAngle, originPoint, translation)
                    self.drcExclusions.append(DrcExclusion(
                        drcE.type,
                        newPosition,
                        newObjects
                    ))
                except KeyError as e:
                    continue # We cannot handle DRC exclusions with board edges
        except FileNotFoundError:
            pass # Ignore boards without a project

        self.projectVars.append(self._readProjectVariables(board))

        return findBoundingBox(edges)

    def _readProjectVariables(self, board: pcbnew.BOARD) -> Dict[str, str]:
        projectPath = self.getProFilepath(board.GetFileName())
        try:
            with open(projectPath, "r", encoding="utf-8") as f:
                project = json.load(f)
                return project.get("text_variables", {})
        except Exception:
            # We silently ignore missing project (e.g, the source is a v5 board)
            return {}

    def appendSubstrate(self, substrate: ToPolygonGeometry) -> None:
        """
        Append a piece of substrate or a list of pieces to the panel. Substrate
        can be either BOX2I or Shapely polygon. Newly appended corners can be
        rounded by specifying non-zero filletRadius.
        """
        polygon = toPolygon(substrate)
        self.boardSubstrate.union(polygon)

    def boardsBBox(self):
        """
        Return common bounding box for all boards in the design (ignores the
        individual pieces of substrate) as a shapely box.
        """
        if len(self.substrates) == 0:
            raise RuntimeError("There are no substrates, cannot compute bounding box")
        bbox = self.substrates[0].bounds()
        for p in islice(self.substrates, 1, None):
            bbox = shpBBoxMerge(bbox, p.bounds())
        return bbox

    def panelBBox(self):
        """
        Return bounding box of the panel as a shapely box.
        """
        return self.boardSubstrate.bounds()

    def addVCutH(self, pos):
        """
        Adds a horizontal V-CUT at pos (integer in KiCAD units).
        """
        self.hVCuts.add(pos)

    def addVCutV(self, pos):
        """
        Adds a horizontal V-CUT at pos (integer in KiCAD units).
        """
        self.vVCuts.add(pos)

    def _setVCutSegmentStyle(self, segment):
        segment.SetShape(STROKE_T.S_SEGMENT)
        segment.SetLayer(self.vCutSettings.layer)
        segment.SetWidth(self.vCutSettings.lineWidth)

    def _setVCutLabelStyle(self, label, origin, position):
        variables = {
            "pos_mm": f"{(position - origin) / mm:.2f} mm",
            "pos_inv_mm": f"{(origin - position) / mm:.2f} mm",
            "pos_inch": f"{(position - origin) / inch:.3f} mm",
            "pos_inv_inch": f"{(origin - position) / inch:.3f} mm",
        }
        label.SetText(self.vCutSettings.textTemplate.format(**variables))
        label.SetLayer(self.vCutSettings.layer)
        label.SetTextThickness(self.vCutSettings.textThickness)
        label.SetTextSize(toKiCADPoint((self.vCutSettings.textSize, self.vCutSettings.textSize)))
        label.SetHorizJustify(EDA_TEXT_HJUSTIFY_T.GR_TEXT_HJUSTIFY_LEFT)

    def _renderVCutV(self):
        """ return list of PCB_SHAPE V-Cuts """
        bBox = self.boardSubstrate.boundingBox()
        minY, maxY = bBox.GetY() - self.vCutSettings.textProlongation, bBox.GetY() + bBox.GetHeight() + self.vCutSettings.endProlongation
        segments = []
        for cut in self.vVCuts:
            segment = pcbnew.PCB_SHAPE()
            self._setVCutSegmentStyle(segment)
            segment.SetStart(toKiCADPoint((cut, minY)))
            segment.SetEnd(toKiCADPoint((cut, maxY)))

            keepout = None
            if self.vCutSettings.clearance != 0:
                keepout = shapely.geometry.box(
                    cut - self.vCutSettings.clearance / 2,
                    bBox.GetY(),
                    cut + self.vCutSettings.clearance / 2,
                    bBox.GetY() + bBox.GetHeight())
            segments.append((segment, keepout))

            label = pcbnew.PCB_TEXT(segment)
            self._setVCutLabelStyle(label, self.getAuxiliaryOrigin()[0], cut)
            label.SetPosition(toKiCADPoint((cut, minY - self.vCutSettings.textOffset)))
            label.SetTextAngle(fromDegrees(90))
            segments.append((label, None))
        return segments

    def _renderVCutH(self):
        """ return list of PCB_SHAPE V-Cuts """
        bBox = self.boardSubstrate.boundingBox()
        minX, maxX = bBox.GetX() - self.vCutSettings.endProlongation, bBox.GetX() + bBox.GetWidth() + self.vCutSettings.textProlongation
        segments = []
        for cut in self.hVCuts:
            segment = pcbnew.PCB_SHAPE()
            self._setVCutSegmentStyle(segment)
            segment.SetStart(toKiCADPoint((minX, cut)))
            segment.SetEnd(toKiCADPoint((maxX, cut)))

            keepout = None
            if self.vCutSettings.clearance != 0:
                keepout = shapely.geometry.box(
                    bBox.GetX(),
                    cut - self.vCutSettings.clearance / 2,
                    bBox.GetX() + bBox.GetWidth(),
                    cut + self.vCutSettings.clearance / 2)
            segments.append((segment, keepout))


            label = pcbnew.PCB_TEXT(segment)
            self._setVCutLabelStyle(label, self.getAuxiliaryOrigin()[1], cut)
            label.SetPosition(toKiCADPoint((maxX + self.vCutSettings.textOffset, cut)))
            segments.append((label, None))
        return segments

    def makeGrid(self, boardfile: str, sourceArea: BOX2I, rows: int, cols: int,
                 destination: VECTOR2I, placer: GridPlacerBase,
                 rotation: KiAngle=fromDegrees(0), netRenamePattern: str="Board_{n}-{orig}",
                 refRenamePattern: str="Board_{n}-{orig}", tolerance: KiLength=0,
                 bakeText: bool=False) \
                     -> List[Substrate]:
        """
        Place the given board in a grid pattern with given spacing. The board
        position of the gride is guided via placer. The nets and references are
        renamed according to the patterns.

        Parameters:

        boardfile - the path to the filename of the board to be added

        sourceArea - the region within the file specified to be selected (see
        also tolerance, below)
            set to None to automatically calculate the board area from the board
            file with the given tolerance

        rows - the number of boards to place in the vertical direction

        cols - the number of boards to place in the horizontal direction

        destination - the center coordinates of the first board in the grid (for
        example, VECTOR2I(100 * mm, 50 * mm))

        rotation - the rotation angle to be applied to the source board before
        placing it

        placer - the placement rules for boards. The builtin classes are:
            BasicGridPosition - places each board in its original orientation
            OddEvenColumnPosition - every second column has the boards rotated
            by 180 degrees OddEvenRowPosition - every second row has the boards
            rotated by 180 degrees OddEvenRowsColumnsPosition - every second row
            and column has the boards rotated by 180 degrees

        netRenamePattern - the pattern according to which the net names are
        transformed
            The default pattern is "Board_{n}-{orig}" which gives each board its
            own instance of its nets, i.e. GND becomes Board_0-GND for the first
            board , and Board_1-GND for the second board etc

        refRenamePattern - the pattern according to which the reference
        designators are transformed
            The default pattern is "Board_{n}-{orig}" which gives each board its
            own instance of its reference designators, so R1 becomes Board_0-R1
            for the first board, Board_1-R1 for the second board etc. To keep
            references the same as in the original, set this to "{orig}"

        tolerance - if no sourceArea is specified, the distance by which the
        selection
            area for the board should extend outside the board edge. If you have
            any objects that are on or outside the board edge, make sure this is
            big enough to include them. Such objects often include zone outlines
            and connectors.

        bakeText - substitute variables in text elements

        Returns a list of the placed substrates. You can use these to generate
        tabs, frames, backbones, etc.
        """
        if not isinstance(rotation, EDA_ANGLE):
            raise RuntimeError(f"Rotation values have to be passed as `EDA_ANGLE` not {type(rotation)}")
        substrateCount = len(self.substrates)
        netRenamer = lambda x, y: netRenamePattern.format(n=x, orig=y)
        refRenamer = lambda x, y: refRenamePattern.format(n=x, orig=y)

        boardSize = None
        topLeftSize = None
        for i, j in product(range(rows), range(cols)):
            dest = destination + placer.position(i, j, topLeftSize)
            boardRotation = rotation + placer.rotation(i, j)
            boardSize = self.appendBoard(
                boardfile, dest, sourceArea=sourceArea,
                tolerance=tolerance, origin=Origin.Center,
                rotationAngle=boardRotation, netRenamer=netRenamer,
                refRenamer=refRenamer, bakeText=bakeText)
            if not topLeftSize:
                topLeftSize = boardSize

        return self.substrates[substrateCount:]

    def makeFrame(self, width: KiLength, hspace: KiLength, vspace: KiLength,
                  minWidth: KiLength = 0, minHeight: KiLength = 0,
                  maxWidth: Optional[KiLength] = None, maxHeight: Optional[KiLength] = None) \
                     -> Tuple[Iterable[LineString], Iterable[LineString]]:
        """
        Build a frame around the boards. Specify width and spacing between the
        boards substrates and the frame. Return a tuple of vertical and
        horizontal cuts.

        Parameters:

        width - width of substrate around board outlines

        slotwidth - width of milled-out perimeter around board outline

        hspace - horizontal space between board outline and substrate

        vspace - vertical space between board outline and substrate

        minWidth - if the panel doesn't meet this width, it is extended

        minHeight - if the panel doesn't meet this height, it is extended

        maxWidth - if the panel doesn't meet this width, error is set and marked

        maxHeight - if the panel doesn't meet this height, error is set and marked
        """
        frameInnerRect = expandRect(shpBoxToRect(self.boardsBBox()), hspace, vspace)
        frameOuterRect = expandRect(frameInnerRect, width)

        sizeErrors = []
        if maxWidth is not None and frameOuterRect.GetWidth() > maxWidth:
            sizeErrors.append(f"Panel width {frameOuterRect.GetWidth() / units.mm} mm exceeds the limit {maxWidth / units.mm} mm")
        if maxHeight is not None and frameOuterRect.GetHeight() > maxHeight:
            sizeErrors.append(f"Panel height {frameOuterRect.GetHeight() / units.mm} mm exceeds the limit {maxHeight / units.mm} mm")
        if len(sizeErrors) > 0:
            self.reportError(toKiCADPoint(frameOuterRect.GetEnd()),
                             "Panel doesn't meet size constraints:\n" + "\n".join(f"- {x}" for x in sizeErrors))

        if frameOuterRect.GetWidth() < minWidth:
            diff = minWidth - frameOuterRect.GetWidth()
            frameOuterRect.SetX(frameOuterRect.GetX() - diff // 2)
            frameOuterRect.SetWidth(frameOuterRect.GetWidth() + diff)
        if frameOuterRect.GetHeight() < minHeight:
            diff = minHeight - frameOuterRect.GetHeight()
            frameOuterRect.SetY(frameOuterRect.GetY() - diff // 2)
            frameOuterRect.SetHeight(frameOuterRect.GetHeight() + diff)
        outerRing = rectToRing(frameOuterRect)
        innerRing = rectToRing(frameInnerRect)
        polygon = Polygon(outerRing, [innerRing])
        self.appendSubstrate(polygon)

        innerArea = self.substrates[0].boundingBox()
        for s in self.substrates:
            innerArea = combineBoundingBoxes(innerArea, s.boundingBox())
        frameCutsV = self.makeFrameCutsV(innerArea, frameInnerRect, frameOuterRect)
        frameCutsH = self.makeFrameCutsH(innerArea, frameInnerRect, frameOuterRect)
        return frameCutsV, frameCutsH

    def makeTightFrame(self, width: KiLength, slotwidth: KiLength,
                      hspace: KiLength, vspace: KiLength,  minWidth: KiLength=0,
                      minHeight: KiLength=0, maxWidth: Optional[KiLength] = None,
                      maxHeight: Optional[KiLength] = None) -> None:
        """
        Build a full frame with board perimeter milled out.
        Add your boards to the panel first using appendBoard or makeGrid.

        Parameters:

        width - width of substrate around board outlines

        slotwidth - width of milled-out perimeter around board outline

        hspace - horizontal space between board outline and substrate

        vspace - vertical space between board outline and substrate

        minWidth - if the panel doesn't meet this width, it is extended

        minHeight - if the panel doesn't meet this height, it is extended

        maxWidth - if the panel doesn't meet this width, error is set

        maxHeight - if the panel doesn't meet this height, error is set
        """
        self.makeFrame(width, hspace, vspace, minWidth, minHeight, maxWidth, maxHeight)
        boardSlot = GeometryCollection()
        for s in self.substrates:
            boardSlot = boardSlot.union(s.exterior())
        boardSlot = boardSlot.buffer(slotwidth, join_style="mitre")
        frameBody = box(*self.boardSubstrate.bounds()).difference(boardSlot)
        self.appendSubstrate(frameBody)

    def makeRailsTb(self, thickness: KiLength, minHeight: KiLength = 0,
                    maxHeight: Optional[KiLength] = None) -> None:
        """
        Adds a rail to top and bottom. You can specify minimal height the panel
        has to feature. You can also specify maximal height of the panel. If the
        height would be exceeded, error is set.
        """
        minx, miny, maxx, maxy = self.panelBBox()
        height = maxy - miny + 2 * thickness
        if maxHeight is not None and height > maxHeight:
            self.reportError(toKiCADPoint((maxx, maxy)), f"Panel height {height / units.mm} mm exceeds the limit {maxHeight / units.mm} mm")
        if height < minHeight:
            thickness = (minHeight - maxy + miny) // 2
        topRail = box(minx, maxy, maxx, maxy + thickness)
        bottomRail = box(minx, miny, maxx, miny - thickness)
        self.appendSubstrate(topRail)
        self.appendSubstrate(bottomRail)

    def makeRailsLr(self, thickness: KiLength, minWidth: KiLength = 0,
                    maxWidth: Optional[KiLength] = None) -> None:
        """
        Adds a rail to left and right. You can specify minimal width the panel
        has to feature.
        """
        minx, miny, maxx, maxy = self.panelBBox()
        width = maxx - minx + 2 * thickness
        if maxWidth is not None and width > maxWidth:
            self.reportError(toKiCADPoint((maxx, maxy)), f"Panel width {width / units.mm} mm exceeds the limit {maxWidth / units.mm} mm")
        if width < minWidth:
            thickness = (minWidth - maxx + minx) // 2
        leftRail = box(minx - thickness, miny, minx, maxy)
        rightRail = box(maxx, miny, maxx + thickness, maxy)
        self.appendSubstrate(leftRail)
        self.appendSubstrate(rightRail)

    def makeFrameCutsV(self, innerArea, frameInnerArea, outerArea):
        """
        Generate vertical cuts for the frame corners and return them
        """
        x_coords = [ innerArea.GetX(),
                     innerArea.GetX() + innerArea.GetWidth() ]
        y_coords = sorted([ frameInnerArea.GetY(),
                            frameInnerArea.GetY() + frameInnerArea.GetHeight(),
                            outerArea.GetY(),
                            outerArea.GetY() + outerArea.GetHeight() ])
        cuts =  [ [(x_coord, y_coords[0]), (x_coord, y_coords[1])] for x_coord in x_coords ]
        cuts += [ [(x_coord, y_coords[2]), (x_coord, y_coords[3])] for x_coord in x_coords ]
        return map(LineString, cuts)

    def makeFrameCutsH(self, innerArea, frameInnerArea, outerArea):
        """
        Generate horizontal cuts for the frame corners and return them
        """
        y_coords = [ innerArea.GetY(),
                     innerArea.GetY() + innerArea.GetHeight() ]
        x_coords = sorted([ frameInnerArea.GetX(),
                            frameInnerArea.GetX() + frameInnerArea.GetWidth(),
                            outerArea.GetX(),
                            outerArea.GetX() + outerArea.GetWidth() ])
        cuts =  [ [(x_coords[0], y_coord), (x_coords[1], y_coord)] for y_coord in y_coords ]
        cuts += [ [(x_coords[2], y_coord), (x_coords[3], y_coord)] for y_coord in y_coords ]
        return map(LineString, cuts)

    def makeVCuts(self, cuts, boundCurves=False, offset=fromMm(0)):
        """
        Take a list of lines to cut and performs V-CUTS. When boundCurves is
        set, approximate curved cuts by a line from the first and last point.
        Otherwise, make an approximate cut and report error.
        """
        for cut in cuts:
            if len(cut.simplify(SHP_EPSILON).coords) > 2 and not boundCurves:
                message = "Cannot V-Cut a curve or a line that is either not horizontal or vertical.\n"
                message += "Possible cause might be:\n"
                message += "- your tabs hit a curved boundary of your PCB,\n"
                message += "- your vertical or horizontal PCB edges are not precisely vertical or horizontal.\n"
                message += "Modify the design or accept curve approximation via V-cuts."
                self._renderLines([cut], Layer.Margin)
                self.reportError(toKiCADPoint(cut[0]), message)
                continue
            cut = cut.simplify(1).parallel_offset(offset, "left")
            start = roundPoint(cut.coords[0])
            end = roundPoint(cut.coords[-1])
            if start.x == end.x or (abs(start.x - end.x) <= fromMm(0.5) and boundCurves):
                self.addVCutV((start.x + end.x) / 2)
            elif start.y == end.y or (abs(start.y - end.y) <= fromMm(0.5) and boundCurves):
                self.addVCutH((start.y + end.y) / 2)
            else:
                description = f"[{toMm(start.x)}, {toMm(start.y)}] -> [{toMm(end.x)}, {toMm(end.y)}]"
                message = f"Cannot perform V-Cut which is not horizontal or vertical ({description}).\n"
                message += "Possible cause might be:\n"
                message += "- check that intended edges are truly horizonal or vertical\n"
                message += "- check your tab placement if it as expected\n"
                message += "You can use layer style of cuts to see them and validate them."
                self._renderLines([cut], Layer.Margin)
                self.reportError(toKiCADPoint(cut[0]), message)
                continue

    def makeMouseBites(self, cuts, diameter, spacing, offset=fromMm(0.25),
        prolongation=fromMm(0.5)):
        """
        Take a list of cuts and perform mouse bites. The cuts can be prolonged
        to
        """
        bloatedSubstrate = prep(self.boardSubstrate.substrates.buffer(SHP_EPSILON))
        offsetCuts = []
        for cut in cuts:
            cut = cut.simplify(SHP_EPSILON) # Remove self-intersecting geometry
            cut = prolongCut(cut, prolongation)
            offsetCut = cut.parallel_offset(offset, "left")
            offsetCuts.append(offsetCut)

        for cut in listGeometries(shapely.ops.unary_union(offsetCuts).simplify(SHP_EPSILON)):
            self.renderedMousebiteCounter += 1
            length = cut.length
            count = int(length / spacing) + 1
            for i in range(count):
                if count == 1:
                    hole = cut.interpolate(0.5, normalized=True)
                else:
                    hole = cut.interpolate( i * length / (count - 1) )
                if bloatedSubstrate.intersects(hole):
                    self.addNPTHole(toKiCADPoint((hole.x, hole.y)), diameter,
                                    ref=f"KiKit_MB_{self.renderedMousebiteCounter}_{i+1}",
                                    excludedFromPos=True)

    def makeCutsToLayer(self, cuts, layer=Layer.Cmts_User, prolongation=fromMm(0), width=fromMm(0.3)):
        """
        Take a list of cuts and render them as lines on given layer. The cuts
        can be prolonged just like with mousebites.

        The purpose of this is to aid debugging when KiKit refuses to perform
        cuts. Rendering them into lines can give the user better understanding
        of where is the problem.
        """
        for cut in cuts:
            cut = prolongCut(cut, prolongation)
            for a, b in zip(cut.coords, cut.coords[1:]):
                segment = pcbnew.PCB_SHAPE()
                segment.SetShape(STROKE_T.S_SEGMENT)
                segment.SetLayer(layer)
                segment.SetStart(toKiCADPoint(a))
                segment.SetEnd(toKiCADPoint(b))
                segment.SetWidth(width)
                self.board.Add(segment)

    def addNPTHole(self, position: VECTOR2I, diameter: KiLength,
                   paste: bool=False, ref: Optional[str]=None,
                   excludedFromPos: bool=False,
                   solderMaskMargin: Optional[KiLength] = None,
    ) -> None:
        """
        Add a drilled non-plated hole to the position (`VECTOR2I`) with given
        diameter. The paste option allows to place the hole on the paste layers.
        """
        footprint = pcbnew.FootprintLoad(KIKIT_LIB, "NPTH")
        footprint.SetPosition(position)
        for pad in footprint.Pads():
            pad.SetDrillSize(toKiCADPoint((diameter, diameter)))
            pad.SetSize(toKiCADPoint((diameter, diameter)))
            if solderMaskMargin is not None:
                footprint.SetLocalSolderMaskMargin(solderMaskMargin)
            if paste:
                layerSet = pad.GetLayerSet()
                layerSet.AddLayer(Layer.F_Paste)
                layerSet.AddLayer(Layer.B_Paste)
                pad.SetLayerSet(layerSet)
        if ref is not None:
            footprint.SetReference(ref)
        if hasattr(footprint, "SetExcludedFromPosFiles"): # KiCAD 6 doesn't support this attribute
            footprint.SetExcludedFromPosFiles(excludedFromPos)
        if hasattr(footprint, "SetBoardOnly"):
            footprint.SetBoardOnly(True)
        self.board.Add(footprint)

    def addFiducial(self, position: VECTOR2I, copperDiameter: KiLength,
                    openingDiameter: KiLength, bottom: bool = False,
                    paste: bool = False, ref: Optional[str] = None) -> None:
        """
        Add fiducial, i.e round copper pad with solder mask opening to the
        position (`VECTOR2I`), with given copperDiameter and openingDiameter. By
        setting bottom to True, the fiducial is placed on bottom side. The
        fiducial can also have an opening on the stencil. This is enabled by
        paste = True.
        """
        footprint = pcbnew.FootprintLoad(KIKIT_LIB, "Fiducial")
        # As of V6, the footprint first needs to be added to the board,
        # then we can change its properties. Otherwise, it misses parent pointer
        # and KiCAD crashes.
        self.board.Add(footprint)
        if ref is not None:
            footprint.SetReference(ref)
        for pad in footprint.Pads():
            pad.SetSize(toKiCADPoint((copperDiameter, copperDiameter)))
            pad.SetLocalSolderMaskMargin(int((openingDiameter - copperDiameter) / 2))
            pad.SetLocalClearance(int((openingDiameter - copperDiameter) / 2))
            if paste:
                layerSet = pad.GetLayerSet()
                layerSet.AddLayer(Layer.F_Paste)
                pad.SetLayerSet(layerSet)

        for drawing in footprint.GraphicalItems():
            if drawing.GetShape() != pcbnew.SHAPE_T_CIRCLE:
                continue
            if drawing.GetLayer() == Layer.F_Fab:
                drawing.SetEnd(toKiCADPoint((openingDiameter / 2, 0)))
            if drawing.GetLayer() == Layer.F_CrtYd:
                drawing.SetEnd(toKiCADPoint((openingDiameter / 2 + fromMm(0.1), 0)))

        footprint.SetPosition(position)

        if bottom:
            footprint.Flip(position, False)


    def panelCorners(self, horizontalOffset=0, verticalOffset=0):
        """
        Return the list of top-left, top-right, bottom-left and bottom-right
        corners of the panel. You can specify offsets.
        """
        minx, miny, maxx, maxy = self.panelBBox()
        topLeft = toKiCADPoint((minx + horizontalOffset, miny + verticalOffset))
        topRight = toKiCADPoint((maxx - horizontalOffset, miny + verticalOffset))
        bottomLeft = toKiCADPoint((minx + horizontalOffset, maxy - verticalOffset))
        bottomRight = toKiCADPoint((maxx - horizontalOffset, maxy - verticalOffset))
        return [topLeft, topRight, bottomLeft, bottomRight]

    def addCornerFiducials(self, fidCount: int, horizontalOffset: KiLength,
                           verticalOffset: KiLength, copperDiameter: KiLength,
                           openingDiameter: KiLength, paste: bool = False) -> None:
        """
        Add up to 4 fiducials to the top-left, top-right, bottom-left and
        bottom-right corner of the board (in this order). This function expects
        there is enough space on the board/frame/rail to place the feature.

        The offsets are measured from the outer edges of the substrate.
        """
        for i, pos in enumerate(self.panelCorners(horizontalOffset, verticalOffset)[:fidCount]):
            self.addFiducial(pos, copperDiameter, openingDiameter, False,
                             paste, ref = f"KiKit_FID_T_{i+1}")
            self.addFiducial(pos, copperDiameter, openingDiameter, True,
                             paste, ref = f"KiKit_FID_B_{i+1}")

    def addCornerTooling(self, holeCount, horizontalOffset, verticalOffset,
                         diameter, paste=False, solderMaskMargin: Optional[KiLength]=None):
        """
        Add up to 4 tooling holes to the top-left, top-right, bottom-left and
        bottom-right corner of the board (in this order). This function expects
        there is enough space on the board/frame/rail to place the feature.

        The offsets are measured from the outer edges of the substrate.

        Optionally, a solder mask margin (diameter) can also be specified.
        """
        for i, pos in enumerate(self.panelCorners(horizontalOffset, verticalOffset)[:holeCount]):
            self.addNPTHole(pos, diameter, paste, ref=f"KiKit_TO_{i+1}", excludedFromPos=False,
                            solderMaskMargin=solderMaskMargin)

    def addMillFillets(self, millRadius):
        """
        Add fillets to inner conernes which will be produced a by mill with
        given radius. This operation simulares milling.
        """
        self.boardSubstrate.millFillets(millRadius)

    def addTabMillFillets(self, millRadius):
        """
        Add fillets to inner conernes which will be produced a by mill with
        given radius. Simulates milling only on the outside of the board;
        internal features of the board are not affected.
        """
        self.boardSubstrate.millFillets(millRadius)
        holes = []
        for s in self.substrates:
            for int in s.interiors():
                holes.append(Polygon(int.coords))
        self.boardSubstrate.cut(shapely.ops.unary_union(holes))

    def clearTabsAnnotations(self):
        """
        Remove all existing tab annotations from the panel.
        """
        for s in self.substrates:
            s.annotations = list(
                filter(lambda x: not isinstance(x, TabAnnotation), s.annotations))

    def buildTabsFromAnnotations(self, fillet: KiLength) -> List[LineString]:
        """
        Given annotations for the individual substrates, create tabs for them.
        Tabs are appended to the panel, cuts are returned.

        Expects that a valid partition line is assigned to the the panel.
        """
        tabs, cuts = [], []
        for s in self.substrates:
            t, c = buildTabs(self, s, s.partitionLine, s.annotations, fillet)
            tabs.extend(t)
            cuts.extend(c)
        self.boardSubstrate.union(tabs)
        return cuts

    def _buildTabAnnotationForEdge(self, edge, dir, count, width):
        """
        Given an edge as AxialLine, dir and count, return a list of
        annotations.
        """
        pos = lambda offset: (
            abs(dir[0]) * edge.x + abs(dir[1]) * (edge.min + offset),
            abs(dir[1]) * edge.x + abs(dir[0]) * (edge.min + offset))
        return [TabAnnotation(None, pos(offset), dir, width)
            for offset in tabSpacing(edge.length, count)]

    def _buildTabAnnotations(self, countFn, widthFn, ghostSubstrates):
        """
        Add tab annotations for the individual substrates based on their
        bounding boxes. Assign tabs annotations to the edges of the bounding
        box. You provide a function countFn, widthFn that take edge length and
        direction that return number of tabs per edge or tab width
        respectively.

        You can also specify ghost substrates (for the future framing).
        """
        neighbors = substrate.SubstrateNeighbors(self.substrates + ghostSubstrates)
        S = substrate.SubstrateNeighbors
        sides = [
            (S.leftC, shpBBoxLeft, [1, 0]),
            (S.rightC, shpBBoxRight,[-1, 0]),
            (S.topC, shpBBoxTop, [0, 1]),
            (S.bottomC, shpBBoxBottom,[0, -1])
        ]
        for i, s in enumerate(self.substrates):
            for query, side, dir in sides:
                for n, shadow in query(neighbors, s):
                    edge = side(s.bounds())
                    for section in shadow.intervals:
                        edge.min, edge.max = section.min, section.max
                        tWidth = widthFn(edge.length, dir)
                        tCount = countFn(edge.length, dir)
                        a = self._buildTabAnnotationForEdge(edge, dir, tCount, tWidth)
                        self.substrates[i].annotations.extend(a)

    def buildTabAnnotationsFixed(self, hcount, vcount, hwidth, vwidth,
            minDistance, ghostSubstrates):
        """
        Add tab annotations for the individual substrates based on number of
        tabs in horizontal and vertical direction. You can specify individual
        width in each direction.

        If the edge is short for the specified number of tabs with given minimal
        spacing, the count is reduced.

        You can also specify ghost substrates (for the future framing).
        """
        def widthFn(edgeLength, dir):
            return abs(dir[0]) * hwidth + abs(dir[1]) * vwidth
        def countFn(edgeLength, dir):
            countLimit = abs(dir[0]) * hcount + abs(dir[1]) * vcount
            width = widthFn(edgeLength, dir)
            return min(countLimit, maxTabCount(edgeLength, width, minDistance))
        return self._buildTabAnnotations(countFn, widthFn, ghostSubstrates)


    def buildTabAnnotationsSpacing(self, spacing, hwidth, vwidth, ghostSubstrates):
        """
        Add tab annotations for the individual substrates based on their spacing.

        You can also specify ghost substrates (for the future framing).
        """
        def widthFn(edgeLength, dir):
            return abs(dir[0]) * hwidth + abs(dir[1]) * vwidth
        def countFn(edgeLength, dir):
            return maxTabCount(edgeLength, widthFn(edgeLength, dir), spacing)
        return self._buildTabAnnotations(countFn, widthFn, ghostSubstrates)

    def buildTabAnnotationsCorners(self, width):
        """
        Add tab annotations to the corners of the individual substrates.
        """
        for i, s in enumerate(self.substrates):
            minx, miny, maxx, maxy = s.bounds()
            midx = (minx + maxx) / 2
            midy = (miny + maxy) / 2

            for x, y in product([minx, maxx], [miny, maxy]):
                dir = normalize((np.sign(midx - x), np.sign(midy - y)))
                a = TabAnnotation(None, (x, y), dir, width)
                self.substrates[i].annotations.append(a)

    def _buildSingleFullTab(self, s: Substrate, a: KiPoint, b: KiPoint,
                            cutoutDepth: KiLength, patchConrners: bool) \
            -> Tuple[List[LineString], List[Polygon]]:
        partitionFace = LineString([a, b])

        npa, npb = np.array(a), np.array(b)

        spanDirection = np.around(normalize(npb - npa), 2)
        spanDirection = np.array([spanDirection[1], -spanDirection[0]])

        # We have to ensure that the direction always points towards the substrate
        midpoint = np.array(s.midpoint())
        if np.dot(midpoint - npa, spanDirection) < 0:
            spanDirection = -spanDirection

        spanDistance = max(partitionFace.distance(Point(*x)) for x in s.exteriorRing().coords)

        sideEdge = spanDirection * spanDistance
        candidateBox = Polygon([npa - spanDirection, npb - spanDirection, npb + sideEdge, npa + sideEdge])
        faceCandidate = s.exterior().intersection(candidateBox)

        expectedDirection = np.around(normalize(npb - npa), 2)
        faceSegments = [LineString(x) for x in linestringToSegments(faceCandidate.exterior)
            if np.array_equal(
                np.around(normalize(np.array(x[0]) - np.array(x[1])), 2),
                expectedDirection) or
               np.array_equal(
                np.around(normalize(np.array(x[1]) - np.array(x[0])), 2),
                expectedDirection)]
        faceDistances = [(x, np.around(partitionFace.distance(x), 2)) for x in faceSegments]
        minFaceDistance = min(faceDistances, key=lambda x: x[1])[1]

        cutFaces = [x for x, d in faceDistances if abs(d - minFaceDistance) < SHP_EPSILON]
        tabs, cuts = [], []
        for cutLine in listGeometries(shapely.ops.unary_union(cutFaces)):
            if minFaceDistance > 0: # Do not generate degenerated polygons
                polygon = Polygon(list(cutLine.coords) +
                    [np.array(cutLine.coords[-1]) - minFaceDistance * spanDirection,
                    np.array(cutLine.coords[0]) - minFaceDistance * spanDirection])
                tabs.append(polygon)
            cuts.append(LineString(list(cutLine.coords)[::-1]))

        solidThickness = max(0, minFaceDistance - cutoutDepth)
        if solidThickness != 0:
            tabs.append(Polygon([npa, npb,
                                 npb + spanDirection * solidThickness,
                                 npa + spanDirection * solidThickness]))
        if patchConrners:
            # Generate corner patches - we don't want cutouts on the board corners,
            # so we create a triangle that will patch it.
            for point in [npa, npb]:
                corner = min(s.exteriorRing().coords, key=lambda x: Point(*x).distance(Point(*point)))
                patch = Polygon([point, corner, corner - minFaceDistance * spanDirection])
                tabs.append(patch)
        return cuts, tabs


    def buildFullTabs(self, cutoutDepth: KiLength, patchCorners: bool = True) \
            -> List[shapely.geometry.LineString]:
        """
        Make full tabs. This strategy basically cuts the bounding boxes of the
        PCBs. Not suitable for mousebites or PCB that doesn't have a rectangular
        outline. Expects there is a valid partition line.

        Return a list of cuts.
        """
        # The general idea is to take each partition line, extrude it towards
        # the PCB and find the intersection. From the intersection we extract
        # all lines that are parallel to the partition line and only choose the
        # closest one. Those line should be the facing edges of the PCB and
        # thus, the cust we want to perfom. To make the tabs stiffer, we fill up
        # the cutouts.
        cuts = []
        for s in self.substrates:
            for fragment in listGeometries(s.partitionLine):
                for a, b in linestringToSegments(fragment):
                    c, t = self._buildSingleFullTab(s, a, b, cutoutDepth, patchCorners)
                    self.appendSubstrate(t)
                    cuts += c

        return cuts

    def inheritLayerNames(self, board):
        for layer in pcbnew.LSET.AllLayersMask().Seq():
            name = board.GetLayerName(layer)
            self.board.SetLayerName(layer, name)

    def inheritCopperLayers(self, board):
        """
        Update the panel's layer count to match the design being panelized.
        Raise an error if this is attempted twice with inconsistent layer count
        boards.
        """
        if self.copperLayerCount is None:
            self.setCopperLayers(board.GetCopperLayerCount())

        elif(self.copperLayerCount != board.GetCopperLayerCount()):
            raise RuntimeError("Attempting to panelize boards together of mixed layer counts")

    def setCopperLayers(self, count):
        """
        Sets the copper layer count of the panel
        """
        self.copperLayerCount = count
        self.board.SetCopperLayerCount(self.copperLayerCount)

    def copperFillNonBoardAreas(self, clearance: KiLength=fromMm(1),
            layers: List[Layer]=[Layer.F_Cu,Layer.B_Cu], hatched: bool=False,
            strokeWidth: KiLength=fromMm(1), strokeSpacing: KiLength=fromMm(1),
            orientation: KiAngle=fromDegrees(45)) -> None:
        """
        This function is deprecated, please, use panel features instead.

        Fill given layers with copper on unused areas of the panel (frame, rails
        and tabs). You can specify the clearance, if it should be hatched
        (default is solid) or shape the strokes of hatched pattern.

        By default, fills top and bottom layer, but you can specify any other
        copper layer that is enabled.
        """
        _, _, maxx, maxy = self.panelBBox()
        if not self.boardSubstrate.isSinglePiece():
            self.reportError(toKiCADPoint((maxx, maxy)), "The substrate has to be a single piece to fill unused areas")
        if len(layers) == 0:
            self.reportError(toKiCADPoint((maxx, maxy)), "No layers to add copper to")
        increaseZonePriorities(self.board)

        zoneArea = self.boardSubstrate.exterior()
        for substrate in self.substrates:
            zoneArea = zoneArea.difference(substrate.exterior().buffer(clearance))

        geoms = [zoneArea] if isinstance(zoneArea, Polygon) else zoneArea.geoms

        for g in geoms:
            zoneContainer = pcbnew.ZONE(self.board)
            if hatched:
                zoneContainer.SetFillMode(pcbnew.ZONE_FILL_MODE_HATCH_PATTERN)
                zoneContainer.SetHatchOrientation(orientation)
                zoneContainer.SetHatchGap(strokeSpacing)
                zoneContainer.SetHatchThickness(strokeWidth)
            zoneContainer.Outline().AddOutline(linestringToKicad(g.exterior))
            for hole in g.interiors:
                zoneContainer.Outline().AddHole(linestringToKicad(hole))
            zoneContainer.SetAssignedPriority(0)

            for l in layers:
                if not self.board.GetEnabledLayers().Contains(l):
                    continue
                zoneContainer = zoneContainer.Duplicate()
                zoneContainer.SetLayer(l)
                self.board.Add(zoneContainer)
                self.zonesToRefill.append(zoneContainer)

    def locateBoard(inputFilename, expandDist=None):
        """
        Given a board filename, find its source area and optionally expand it by the given distance.

        Parameters:

        inputFilename - the path to the board file

        expandDist - the distance by which to expand the board outline in each direction to ensure elements that are outside the board are included
        """
        inputBoard = pcbnew.LoadBoard(inputFilename)
        boardArea=findBoardBoundingBox(inputBoard)
        if expandDist is None:
            return boardArea
        sourceArea=expandRect(boardArea, expandDist)

    def addKeepout(self, area, noTracks=True, noVias=True, noCopper=True):
        """
        Add a keepout area to all copper layers. Area is a shapely
        polygon. Return the keepout area.
        """
        zone = polygonToZone(area, self.board)
        zone.SetIsRuleArea(True)
        zone.SetDoNotAllowTracks(noTracks)
        zone.SetDoNotAllowVias(noVias)
        zone.SetDoNotAllowCopperPour(noCopper)

        zone.SetLayerSet(pcbnew.LSET.AllCuMask(self.copperLayerCount))

        self.board.Add(zone)
        return zone

    def addText(self, text, position, orientation=fromDegrees(0),
                width=fromMm(1.5), height=fromMm(1.5), thickness=fromMm(0.3),
                hJustify=EDA_TEXT_HJUSTIFY_T.GR_TEXT_HJUSTIFY_CENTER,
                vJustify=EDA_TEXT_VJUSTIFY_T.GR_TEXT_VJUSTIFY_CENTER,
                layer=Layer.F_SilkS):
        """
        Add text at given position to the panel. If appending to the bottom
        side, text is automatically mirrored.
        """
        textObject = pcbnew.PCB_TEXT(self.board)
        textObject.SetText(text)
        textObject.SetTextX(position[0])
        textObject.SetTextY(position[1])
        textObject.SetTextThickness(thickness)
        textObject.SetTextSize(toKiCADPoint((width, height)))
        textObject.SetHorizJustify(hJustify)
        textObject.SetVertJustify(vJustify)
        textObject.SetTextAngle(orientation)
        textObject.SetLayer(layer)
        textObject.SetMirrored(isBottomLayer(layer))
        self.board.Add(textObject)

    def setAuxiliaryOrigin(self, point):
        """
        Set the auxiliary origin used e.g., for drill files
        """
        self.board.GetDesignSettings().SetAuxOrigin(point)

    def getAuxiliaryOrigin(self):
        return self.board.GetDesignSettings().GetAuxOrigin()

    def setGridOrigin(self, point):
        """
        Set grid origin
        """
        self.board.GetDesignSettings().SetGridOrigin(point)

    def getGridOrigin(self):
        return self.board.GetDesignSettings().GetGridOrigin()

    def _buildPartitionLineFromBB(self, partition):
        for s in self.substrates:
            hLines, vLines = partition.partitionSubstrate(s)
            hSLines = [((l.min, l.x), (l.max, l.x)) for l in hLines]
            vSLines = [((l.x, l.min), (l.x, l.max)) for l in vLines]
            lines = hSLines + vSLines
            multiline = shapely.ops.linemerge(lines)
            multiline = normalizePartitionLineOrientation(multiline)

            s.partitionLine = multiline

    def _buildBackboneLineFromBB(self, partition, boundarySubstrates):
        hBoneLines, vBoneLines = set(), set()
        for s in self.substrates:
            hLines, vLines = partition.partitionSubstrate(s)
            hBoneLines.update(hLines)
            vBoneLines.update(vLines)
        for s in boundarySubstrates:
            hLines, vLines = partition.partitionSubstrate(s)
            for l in hLines:
                # When edge overlaps with boundary substrate, the line is not
                # present
                if l in hBoneLines:
                    hBoneLines.remove(l)
            for l in vLines:
                # Ditto as above
                if l in vBoneLines:
                    vBoneLines.remove(l)
        minx, miny, maxx, maxy = self.boardSubstrate.bounds()
        # Cut backbone on substrates boundaries:
        cut = lambda xs, y: chain(*[x.cut(y) for x in xs])
        hBoneLines = cut(cut(hBoneLines, minx), maxx)
        vBoneLines = cut(cut(vBoneLines, miny), maxy)
        hBLines = [LineString([(l.min, l.x), (l.max, l.x)]) for l in hBoneLines]
        vBLines = [LineString([(l.x, l.min), (l.x, l.max)]) for l in vBoneLines]
        self.backboneLines = list(chain(hBLines, vBLines))

    def buildPartitionLineFromBB(self, boundarySubstrates=[], safeMargin=0):
        """
        Builds partition & backbone line from bounding boxes of the substrates.
        You can optionally pass extra substrates (e.g., for frame). Without
        these extra substrates no partition line would be generated on the side
        where the boundary is, therefore, there won't be any tabs.
        """
        partition = substrate.SubstratePartitionLines(
            self.substrates, boundarySubstrates,
            safeMargin, safeMargin)
        self._buildPartitionLineFromBB(partition)
        self._buildBackboneLineFromBB(partition, boundarySubstrates)

    def addLine(self, start, end, thickness, layer):
        """
        Add a line to the panel based on starting and ending point
        """
        segment = pcbnew.PCB_SHAPE()
        segment.SetShape(STROKE_T.S_SEGMENT)
        segment.SetLayer(layer)
        segment.SetWidth(thickness)
        segment.SetStart(toKiCADPoint((start[0], start[1])))
        segment.SetEnd(toKiCADPoint((end[0], end[1])))
        self.board.Add(segment)
        return segment

    def _renderLines(self, lines, layer, thickness=fromMm(0.5)):
        for geom in lines:
            for linestring in listGeometries(geom):
                for start, end in linestringToSegments(linestring):
                    self.addLine(start, end, thickness, layer)

    def debugRenderPartitionLines(self):
        """
        Render partition line to the panel to be easily able to inspect them via
        Pcbnew.
        """
        lines = [s.partitionLine for s in self.substrates]
        self._renderLines(lines, Layer.Eco1_User, fromMm(0.5))

    def debugRenderBackboneLines(self):
        """
        Render partition line to the panel to be easily able to inspect them via
        Pcbnew.
        """
        self._renderLines(self.backboneLines, Layer.Eco2_User, fromMm(0.5))

    def debugRenderBoundingBoxes(self):
        lines = [box(*s.bounds()).exterior for s in self.substrates]
        self._renderLines(lines, Layer.Cmts_User, fromMm(0.5))

    def renderBackbone(self, vthickness: KiLength, hthickness: KiLength,
            vcut: bool, hcut: bool, vskip: int=0, hskip: int=0,
            vfirst: int=0, hfirst: int=0):
        """
        Render horizontal and vertical backbone lines. If zero thickness is
        specified, no backbone is rendered.

        vcut, hcut specifies if vertical or horizontal backbones should be cut.

        vskip and hskip specify how many backbones should be skipped before
        rendering one (i.e., skip 1 meand that every other backbone will be
        rendered)

        vfirst and hfirst are indices of the first backbone to render. They are
        1-indexed.

        Return a list of cuts
        """
        if vfirst == 0:
            vfirst = vskip + 1
        if hfirst == 0:
            hfirst = hskip + 1

        hbones = [] if hthickness == 0 \
                    else list(filter(lambda l: isHorizontal(l.coords[0], l.coords[1]), self.backboneLines))
        activeHbones = skipBackbones(hbones, hskip, hfirst, lambda x: x.coords[0][1])

        vbones = [] if vthickness == 0 \
                    else list(filter(lambda l: isVertical(l.coords[0], l.coords[1]), self.backboneLines))
        activeVbones = skipBackbones(vbones, vskip, vfirst, lambda x: x.coords[0][0])

        cutpoints = commonPoints(self.backboneLines)
        pieces, cuts = [], []

        for l in activeHbones:
            start = l.coords[0]
            end = l.coords[1]

            minX = min(start[0], end[0])
            maxX = max(start[0], end[0])
            bb = box(minX, start[1] - hthickness // 2,
                        maxX, start[1] + hthickness // 2)
            pieces.append(bb)
            if not hcut:
                continue

            candidates = []

            if cutpoints[start] > 2:
                candidates.append(((start[0] + vthickness // 2, start[1]), -1))

            if cutpoints[end] == 2:
                candidates.append((end, 1))
            elif cutpoints[end] > 2:
                candidates.append(((end[0] - vthickness // 2, end[1]), 1))

            for x, c in candidates:
                cut = LineString([
                    (x[0], x[1] - c * hthickness // 2),
                    (x[0], x[1] + c * hthickness // 2)])
                cuts.append(cut)

        for l in activeVbones:
            start = l.coords[0]
            end = l.coords[1]

            minY = min(start[1], end[1])
            maxY = max(start[1], end[1])
            bb = box(start[0] - vthickness // 2, minY,
                        start[0] + vthickness // 2, maxY)
            pieces.append(bb)
            if not vcut:
                continue

            candidates = []

            if cutpoints[start] > 2:
                candidates.append(((start[0], start[1] + hthickness // 2), 1))

            if cutpoints[end] == 2:
                candidates.append((end, -1))
            elif cutpoints[end] > 2:
                candidates.append(((end[0], end[1] - hthickness // 2), -1))

            for x, c in candidates:
                cut = LineString([
                    (x[0] - c * vthickness // 2, x[1]),
                    (x[0] + c * vthickness // 2, x[1])])
                cuts.append(cut)

        self.appendSubstrate(pieces)
        return cuts

    def addCornerFillets(self, radius):
        self.filletSize = radius
        corners = self.panelCorners()
        filletOrigins = self.panelCorners(radius, radius)
        for corner, opposite in zip(corners, filletOrigins):
            square = shapely.geometry.box(
                min(corner[0], opposite[0]),
                min(corner[1], opposite[1]),
                max(corner[0], opposite[0]),
                max(corner[1], opposite[1])
            )
            filletCircle = Point(opposite).buffer(radius, resolution=16)

            cutShape = square.difference(filletCircle)
            self.boardSubstrate.cut(cutShape)

    def addCornerChamfers(self, horizontalSize: KiLength, verticalSize: Optional[KiLength] = None):
        """
        Add chamfers to the panel frame. The chamfer is specified as size in
        horizontal and vertical direction. If you specify only the horizontal
        one, the chamfering will be 45°.
        """
        if verticalSize is None:
            verticalSize = horizontalSize
        self.chamferWidth = horizontalSize
        self.chamferHeight = verticalSize

        corners = self.panelCorners(-SHP_EPSILON, -SHP_EPSILON)
        verticalStops = self.panelCorners(-SHP_EPSILON, verticalSize)
        horizontalStops = self.panelCorners(horizontalSize, -SHP_EPSILON)
        for t, v, h in zip(corners, verticalStops, horizontalStops):
            cutPoly = Polygon([t, v, h, t])
            self.boardSubstrate.cut(cutPoly)

    def translate(self, vec):
        """
        Translates the whole panel by vec. Such a feature can be useful to
        specify the panel placement in the sheet. When we translate panel as the
        last operation, none of the operations have to be placement-aware.
        """
        vec = toKiCADPoint(vec)
        for drawing in self.board.GetDrawings():
            drawing.Move(vec)
        for footprint in self.board.GetFootprints():
            footprint.Move(vec)
        for track in self.board.GetTracks():
            track.Move(vec)
        for zone in self.board.Zones():
            zone.Move(vec)
        for substrate in self.substrates:
            substrate.translate(vec)
        self.boardSubstrate.translate(vec)
        self.backboneLines = [shapely.affinity.translate(bline, vec[0], vec[1])
                              for bline in self.backboneLines]
        self.hVCuts = [c + vec[1] for c in self.hVCuts]
        self.vVCuts = [c + vec[0] for c in self.vVCuts]
        for c in self.vVCuts:
            c += vec[1]
        self.setAuxiliaryOrigin(self.getAuxiliaryOrigin() + vec)
        self.setGridOrigin(self.getGridOrigin() + vec)
        for error in self.errors:
            error = (error[0] + vec, error[1])
        for drcE in self.drcExclusions:
            drcE.position += vec

    def addPanelDimensions(self, layer: Layer, offset: KiLength) -> None:
        """
        Add vertial and horizontal dimensions to the panel
        """
        minx, miny, maxx, maxy = self.panelBBox()

        hDim = pcbnew.PCB_DIM_ORTHOGONAL(self.board)
        hDim.SetOrientation(pcbnew.PCB_DIM_ORTHOGONAL.DIR_HORIZONTAL)
        hDim.SetHeight(-offset)
        hDim.SetStart(toKiCADPoint((minx, miny)))
        hDim.SetEnd(toKiCADPoint((maxx, miny)))
        hDim.SetLayer(layer)
        hDim.SetUnitsMode(pcbnew.DIM_UNITS_MODE_MILLIMETRES)
        hDim.SetSuppressZeroes(True)
        if self.chamferHeight is not None:
            hDim.SetExtensionOffset(-self.chamferHeight)
        if self.filletSize is not None:
            hDim.SetExtensionOffset(-self.filletSize)
        self.board.Add(hDim)

        vDim = pcbnew.PCB_DIM_ORTHOGONAL(self.board)
        vDim.SetOrientation(pcbnew.PCB_DIM_ORTHOGONAL.DIR_VERTICAL)
        vDim.SetHeight(-offset)
        vDim.SetStart(toKiCADPoint((minx, miny)))
        vDim.SetEnd(toKiCADPoint((minx, maxy)))
        vDim.SetLayer(layer)
        vDim.SetUnitsMode(pcbnew.DIM_UNITS_MODE_MILLIMETRES)
        vDim.SetSuppressZeroes(True)
        if self.chamferWidth is not None:
            vDim.SetExtensionOffset(-self.chamferWidth)
        if self.filletSize is not None:
            vDim.SetExtensionOffset(-self.filletSize)
        self.board.Add(vDim)

    def apply(self, feature: Any) -> None:
        """
        Apply given feature to the panel
        """
        feature.apply(self)


def getFootprintByReference(board, reference):
    """
    Return a footprint by with given reference
    """
    for f in board.GetFootprints():
        if f.GetReference() == reference:
            return f
    raise RuntimeError(f"Footprint with reference '{reference}' not found")

def extractSourceAreaByAnnotation(board, reference):
    """
    Given a board and a reference to annotation in the form of symbol
    `kikit:Board`, extract the source area. The source area is a bounding box of
    continuous lines in the Edge.Cuts on which the arrow in reference point.
    """
    try:
        annotation = getFootprintByReference(board, reference)
    except Exception:
        raise RuntimeError(f"Cannot extract board - boards is specified via footprint with reference '{reference}' which was not found")
    tip = annotation.GetPosition()
    edges = collectEdges(board, Layer.Edge_Cuts)
    # KiCAD 6 will need an adjustment - method Collide was introduced with
    # different parameters. But v6 API is not available yet, so we leave this
    # to future ourselves.
    pointedAt = indexOf(edges, lambda x: x.HitTest(tip))
    rings = extractRings(edges)
    ringPointedAt = indexOf(rings, lambda x: pointedAt in x)
    if ringPointedAt == -1:
        raise RuntimeError("Annotation symbol '{reference}' does not point to a board edge")
    return findBoundingBox([edges[i] for i in rings[ringPointedAt]])


