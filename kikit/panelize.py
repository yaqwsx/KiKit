from pcbnewTransition import pcbnew, isV6
from kikit import sexpr
from kikit.common import normalize

from typing import Any, Callable, Dict, List, Tuple, Union

from pcbnew import (GetBoard, LoadBoard,
                    FromMM, ToMM, wxPoint, wxRect, wxRectMM, wxPointMM)
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
from collections import OrderedDict

from kikit import substrate
from kikit import units
from kikit.substrate import Substrate, linestringToKicad, extractRings
from kikit.defs import STROKE_T, Layer, EDA_TEXT_HJUSTIFY_T, EDA_TEXT_VJUSTIFY_T, PAPER_SIZES
from kikit.common import *
from kikit.sexpr import parseSexprF, SExpr, Atom
from kikit.annotations import AnnotationReader, TabAnnotation
from kikit.drc import DrcExclusion, readBoardDrcExclusions, serializeExclusion

class PanelError(RuntimeError):
    pass

def identity(x):
    return x

class BasicGridPosition:
    """
    Specify board position in the grid. This class
    """
    def __init__(self, destination, boardSize, horSpace, verSpace):
        self.destination = destination
        self.boardSize = boardSize
        self.horSpace = horSpace
        self.verSpace = verSpace

    def position(self, i, j):
        return wxPoint(self.destination[0] + j * (self.boardSize.GetWidth() + self.horSpace),
                       self.destination[1] + i * (self.boardSize.GetHeight() + self.verSpace))

    def rotation(self, i, j):
        return 0

class OddEvenRowsPosition(BasicGridPosition):
    """
    Rotate boards by 180° for every row
    """
    def rotation(self, i, j):
        if i % 2 == 0:
            return 0
        return 1800

class OddEvenColumnPosition(BasicGridPosition):
    """
    Rotate boards by 180° for every column
    """
    def rotation(self, i, j):
        if j % 2 == 0:
            return 0
        return 1800

class OddEvenRowsColumnsPosition(BasicGridPosition):
    """
    Rotate boards by 180 for every row and column
    """
    def rotation(self, i, j):
        if (i % 2) == (j % 2):
            return 0
        return 1800


class Origin(Enum):
    Center = 0
    TopLeft = 1
    TopRight = 2
    BottomLeft = 3
    BottomRight = 4

def getOriginCoord(origin, bBox):
    """Returns real coordinates (wxPoint) of the origin for given bounding box"""
    if origin == Origin.Center:
        return wxPoint(bBox.GetX() + bBox.GetWidth() // 2,
                       bBox.GetY() + bBox.GetHeight() // 2)
    if origin == Origin.TopLeft:
        return wxPoint(bBox.GetX(), bBox.GetY())
    if origin == Origin.TopRight:
        return wxPoint(bBox.GetX() + bBox.GetWidth(), bBox.GetY())
    if origin == Origin.BottomLeft:
        return wxPoint(bBox.GetX(), bBox.GetY() + bBox.GetHeight())
    if origin == Origin.BottomRight:
        return wxPoint(bBox.GetX() + bBox.GetWidth(), bBox.GetY() + bBox.GetHeight())

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
    if not isV6() or not yieldMapping:
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

def toPolygon(entity):
    if isinstance(entity, list):
        return list([toPolygon(e) for e in entity])
    if isinstance(entity, Polygon) or isinstance(entity, MultiPolygon):
        return entity
    if isinstance(entity, wxRect):
        return Polygon([
            (entity.GetX(), entity.GetY()),
            (entity.GetX() + entity.GetWidth(), entity.GetY()),
            (entity.GetX() + entity.GetWidth(), entity.GetY() + entity.GetHeight()),
            (entity.GetX(), entity.GetY() + entity.GetHeight())])
    raise NotImplementedError("Cannot convert {} to Polygon".format(type(entity)))

def rectString(rect):
    return "({}, {}) w: {}, h: {}".format(
                ToMM(rect.GetX()), ToMM(rect.GetY()),
                ToMM(rect.GetWidth()), ToMM(rect.GetHeight()))

def expandRect(rect, offsetX, offsetY=None):
    """
    Given a wxRect returns a new rectangle, which is larger in all directions
    by offset. If only offsetX is passed, it used for both X and Y offset
    """
    if offsetY is None:
        offsetY = offsetX
    offsetX = int(offsetX)
    offsetY = int(offsetY)
    return wxRect(rect.GetX() - offsetX, rect.GetY() - offsetY,
        rect.GetWidth() + 2 * offsetX, rect.GetHeight() + 2 * offsetY)

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

def doTransformation(point: KiKitPoint, rotation: int, origin: KiKitPoint, translation: KiKitPoint) -> wxPoint:
    """
    Abuses KiCAD to perform a tranformation of a point
    """
    segment = pcbnew.PCB_SHAPE()
    segment.SetShape(STROKE_T.S_SEGMENT)
    segment.SetStart(wxPoint(int(point[0]), int(point[1])))
    segment.SetEnd(wxPoint(0, 0))
    segment.Rotate(wxPoint(int(origin[0]), int(origin[1])), -rotation)
    segment.Move(wxPoint(translation[0], translation[1]))
    # We build a fresh wxPoint - otherwise there is a shared reference
    return wxPoint(segment.GetStartX(), segment.GetStartY())

def undoTransformation(point, rotation, origin, translation):
    """
    We apply a transformation "Rotate around origin and then translate" when
    placing a board. Given a point and original transformation parameters,
    return the original point position.
    """
    # Abuse PcbNew to do so
    segment = pcbnew.PCB_SHAPE()
    segment.SetShape(STROKE_T.S_SEGMENT)
    segment.SetStart(wxPoint(int(point[0]), int(point[1])))
    segment.SetEnd(wxPoint(0, 0))
    segment.Move(wxPoint(-translation[0], -translation[1]))
    segment.Rotate(origin, -rotation)
    # We build a fresh wxPoint - otherwise there is a shared reference
    return wxPoint(segment.GetStartX(), segment.GetStartY())

def removeCutsFromFootprint(footprint):
    """
    Find all graphical items in the footprint, remove them and return them as a
    list
    """
    edges = []
    for edge in footprint.GraphicalItems():
        if edge.GetLayerName() != "Edge.Cuts":
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

def increaseZonePriorities(board, amount=1):
    for zone in board.Zones():
        zone.SetPriority(zone.GetPriority() + amount)

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

def buildTabs(substrate, partitionLines, tabAnnotations):
    """
    Given substrate, partitionLines of the substrate and an iterable of tab
    annotations, build tabs. Note that if the tab does not hit the partition
    line, it is not included in the design.

    Return a pair of lists: tabs and cuts.
    """
    tabs, cuts = [], []
    for annotation in tabAnnotations:
        t, c = substrate.tab(annotation.origin, annotation.direction,
            annotation.width, partitionLines, annotation.maxLength)
        if t is not None:
            tabs.append(t)
            cuts.append(c)
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
        self.filename = panelFilename
        self.board = pcbnew.NewBoard(panelFilename)
        self.sourcePaths = set() # A set of all board files that were appended to the panel
        self.substrates = [] # Substrates of the individual boards; e.g. for masking
        self.boardSubstrate = Substrate([]) # Keep substrate in internal representation,
                                            # Draw it just before saving
        self.backboneLines = []
        self.hVCuts = set() # Keep V-cuts as numbers and append them just before saving
        self.vVCuts = set() # to make them truly span the whole panel
        self.vCutLayer = Layer.Cmts_User
        self.vCutClearance = 0
        self.copperLayerCount = None
        self.zonesToRefill = pcbnew.ZONES()
        self.pageSize: Union[None, str, Tuple[int, int]] = None

        self.annotationReader: AnnotationReader = AnnotationReader.getDefault()
        self.drcExclusions: List[DrcExclusion] = []

    def save(self):
        """
        Saves the panel to a file and makes the requested changes to the prl and
        pro files.
        """
        newEdges = self.boardSubstrate.serialize()
        for edge in newEdges:
            self.board.Add(edge)
        vcuts = self._renderVCutH() + self._renderVCutV()
        keepouts = []
        for cut, clearanceArea in vcuts:
            self.board.Add(cut)
            if clearanceArea is not None:
                keepouts.append(self.addKeepout(clearanceArea))
        fillerTool = pcbnew.ZONE_FILLER(self.board)
        fillerTool.Fill(self.zonesToRefill)
        self.board.Save(self.filename)
        # Remove cuts
        for cut, _ in vcuts:
            self.board.Remove(cut)
        # Remove V-cuts keepouts
        for keepout in keepouts:
            self.board.Remove(keepout)
        # Remove edges
        for edge in newEdges:
            self.board.Remove(edge)

        if isV6():
            self.makeLayersVisible() # as they are not in KiCAD 6
            self.mergeDrcRules()
        self._adjustPageSize()

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

    def makeLayersVisible(self):
        """
        Modify corresponding *.prl files so all the layers are visible by
        default
        """
        assert isV6()
        try:
            with open(self.getPrlFilepath()) as f:
                # We use ordered dict, so we preserve the ordering of the keys and
                # thus, formatting
                prl = json.load(f, object_pairs_hook=OrderedDict)
            prl["board"]["visible_layers"] = "fffffff_ffffffff"
            with open(self.getPrlFilepath(), "w") as f:
                json.dump(prl, f, indent=2)
        except IOError:
            # The PRL file is not always created, ignore it
            pass

    def mergeDrcRules(self):
        """
        Examine DRC rules of the source boards, merge them into a single set of
        rules and store them in *.kicad_pro file. Also stores board DRC
        exclusions.
        """
        assert isV6()

        if len(self.sourcePaths) > 1:
            raise RuntimeError("Merging of DRC rules of multiple boards is currently unsupported")
        if len(self.sourcePaths) == 0:
            return # Nothing to merge

        sPath = list(self.sourcePaths)[0]
        try:
            with open(self.getProFilepath(sPath)) as f:
                sourcePro = json.load(f)
        except (IOError, FileNotFoundError):
            # This means there is no original project file. Probably comes from
            # v5, thus there is nothing to transfer
            return
        try:
            with open(self.getProFilepath()) as f:
                currentPro = json.load(f, object_pairs_hook=OrderedDict)
            currentPro["board"]["design_settings"] = sourcePro["board"]["design_settings"]
            currentPro["board"]["design_settings"]["drc_exclusions"] = [
                serializeExclusion(e) for e in self.drcExclusions]
            with open(self.getProFilepath(), "w") as f:
                json.dump(currentPro, f, indent=2)
        except (KeyError, FileNotFoundError):
            # This means the source board has no DRC setting. Probably a board
            # without attached project
            pass

    def _adjustPageSize(self) -> None:
        """
        Open the just saved panel file and syntactically change the page size.
        At the moment, there is no API do so, therefore this extra step is
        required.
        """
        if self.pageSize is None:
            return
        with open(self.filename, "r") as f:
            tree = parseSexprF(f)
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

        with open(self.filename, "w") as f:
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
        if isV6():
            d = self.board.GetDesignSettings()
            d.CloneFrom(designSettings)
        else:
            self.board.SetDesignSettings(designSettings)

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

    def setPageSize(self, size: Union[str, Tuple[int, int]] ) -> None:
        """
        Set page size - either a string name (e.g., A4) or size in KiCAD units
        """
        if isinstance(size, str):
            if size not in PAPER_SIZES:
                raise RuntimeError(f"Unknown paper size: {size}")
        self.pageSize = size

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

    def appendBoard(self, filename, destination, sourceArea=None,
                    origin=Origin.Center, rotationAngle=0, shrink=False,
                    tolerance=0, bufferOutline=fromMm(0.001), netRenamer=None,
                    refRenamer=None, inheritDrc=True, interpretAnnotations=True):
        """
        Appends a board to the panel.

        The sourceArea (wxRect) of the board specified by filename is extracted
        and placed at destination (wxPoint). The source area (wxRect) can be
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

        Returns bounding box (wxRect) of the extracted area placed at the
        destination and the extracted substrate of the board.
        """
        board = LoadBoard(filename)
        if inheritDrc:
            self.sourcePaths.add(filename)

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
        translation = wxPoint(destination[0] - originPoint[0],
                              destination[1] - originPoint[1])

        if netRenamer is None:
            netRenamer = lambda x, y: self._uniquePrefix() + y
        renameNets(board, lambda x: netRenamer(len(self.substrates), x))
        if refRenamer is not None:
            renameRefs(board, lambda x: refRenamer(len(self.substrates), x))

        drawings = collectItems(board.GetDrawings(), enlargedSourceArea)
        footprints = collectFootprints(board.GetFootprints(), enlargedSourceArea)
        tracks = collectItems(board.GetTracks(), enlargedSourceArea)
        zones = collectItems(board.Zones(), enlargedSourceArea)

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
                if isinstance(item, pcbnew.FP_TEXT) and item.IsKeepUpright():
                    actualOrientation = item.GetDrawRotation()
                    item.SetKeepUpright(False)
                    item.SetTextAngle(actualOrientation - footprint.GetOrientation())
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
            raise substrate.PositionError(filename + ": " + e.origMessage, point)
        for drawing in otherDrawings:
            appendItem(self.board, drawing, yieldMapping)

        if isV6():
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
        return findBoundingBox(edges)

    def appendSubstrate(self, substrate):
        """
        Append a piece of substrate or a list of pieces to the panel. Substrate
        can be either wxRect or Shapely polygon. Newly appended corners can be
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

    def setVCutLayer(self, layer):
        """
        Set layer on which the V-Cuts will be rendered
        """
        self.vCutLayer = layer

    def setVCutClearance(self, clearance):
        """
        Set V-cut clearance
        """
        self.vCutClearance = clearance

    def _setVCutSegmentStyle(self, segment, layer):
        segment.SetShape(STROKE_T.S_SEGMENT)
        segment.SetLayer(layer)
        segment.SetWidth(fromMm(0.4))

    def _setVCutLabelStyle(self, label, layer):
        label.SetText("V-CUT")
        label.SetLayer(layer)
        label.SetTextThickness(fromMm(0.4))
        label.SetTextSize(pcbnew.wxSizeMM(2, 2))
        label.SetHorizJustify(EDA_TEXT_HJUSTIFY_T.GR_TEXT_HJUSTIFY_LEFT)

    def _renderVCutV(self):
        """ return list of PCB_SHAPE V-Cuts """
        bBox = self.boardSubstrate.boundingBox()
        minY, maxY = bBox.GetY() - fromMm(3), bBox.GetY() + bBox.GetHeight() + fromMm(3)
        segments = []
        for cut in self.vVCuts:
            segment = pcbnew.PCB_SHAPE()
            self._setVCutSegmentStyle(segment, self.vCutLayer)
            segment.SetStart(pcbnew.wxPoint(cut, minY))
            segment.SetEnd(pcbnew.wxPoint(cut, maxY))

            keepout = None
            if self.vCutClearance != 0:
                keepout = shapely.geometry.box(
                    cut - self.vCutClearance / 2,
                    bBox.GetY(),
                    cut + self.vCutClearance / 2,
                    bBox.GetY() + bBox.GetHeight())
            segments.append((segment, keepout))

            label = pcbnew.PCB_TEXT(segment)
            self._setVCutLabelStyle(label, self.vCutLayer)
            label.SetPosition(wxPoint(cut, minY - fromMm(3)))
            label.SetTextAngle(900)
            segments.append((label, None))
        return segments

    def _renderVCutH(self):
        """ return list of PCB_SHAPE V-Cuts """
        bBox = self.boardSubstrate.boundingBox()
        minX, maxX = bBox.GetX() - fromMm(3), bBox.GetX() + bBox.GetWidth() + fromMm(3)
        segments = []
        for cut in self.hVCuts:
            segment = pcbnew.PCB_SHAPE()
            self._setVCutSegmentStyle(segment, self.vCutLayer)
            segment.SetStart(pcbnew.wxPoint(minX, cut))
            segment.SetEnd(pcbnew.wxPoint(maxX, cut))

            keepout = None
            if self.vCutClearance != 0:
                keepout = shapely.geometry.box(
                    bBox.GetX(),
                    cut - self.vCutClearance / 2,
                    bBox.GetX() + bBox.GetWidth(),
                    cut + self.vCutClearance / 2)
            segments.append((segment, keepout))


            label = pcbnew.PCB_TEXT(segment)
            self._setVCutLabelStyle(label, self.vCutLayer)
            label.SetPosition(wxPoint(maxX + fromMm(3), cut))
            segments.append((label, None))
        return segments

    def _placeBoardsInGrid(self, boardfile, rows, cols, destination, sourceArea, tolerance,
                  verSpace, horSpace, rotation, netRenamer, refRenamer,
                  placementClass):
        """
        Create a grid of boards, return source board size aligned at the top
        left corner
        """
        boardSize = wxRect(0, 0, 0, 0)
        topLeftSize = None
        placement = placementClass(destination, boardSize, horSpace, verSpace)
        for i, j in product(range(rows), range(cols)):
            placement.boardSize = boardSize
            dest = placement.position(i, j)
            boardRotation = rotation + placement.rotation(i, j)
            boardSize = self.appendBoard(
                boardfile, dest, sourceArea=sourceArea,
                tolerance=tolerance, origin=Origin.Center,
                rotationAngle=boardRotation, netRenamer=netRenamer,
                refRenamer=refRenamer)
            if not topLeftSize:
                topLeftSize = boardSize
        return topLeftSize

    def makeGrid(self, boardfile, sourceArea, rows, cols, destination,
                    verSpace, horSpace, rotation,
                    placementClass=BasicGridPosition,
                    netRenamePattern="Board_{n}-{orig}",
                    refRenamePattern="Board_{n}-{orig}", tolerance=0):
        """
        Place the given board in a regular grid pattern with given spacing
        (verSpace, horSpace). The board position can be fine-tuned via
        placementClass. The nets and references are renamed according to the
        patterns.

        Parameters:

        boardfile - the path to the filename of the board to be added

        sourceArea - the region within the file specified to be selected (see also tolerance, below)
            set to None to automatically calculate the board area from the board file with the given tolerance

        rows - the number of boards to place in the vertical direction

        cols - the number of boards to place in the horizontal direction

        destination - the center coordinates of the first board in the grid (for example, wxPointMM(100,50))

        verSpace - the vertical spacing (distance, not pitch) between boards

        horSpace - the horizontal spacing (distance, not pitch) between boards

        rotation - the rotation angle to be applied to the source board before placing it

        placementClass - the placement rules for boards. The builtin classes are:
            BasicGridPosition - places each board in its original orientation
            OddEvenColumnPosition - every second column has the boards rotated by 180 degrees
            OddEvenRowPosition - every second row has the boards rotated by 180 degrees
            OddEvenRowsColumnsPosition - every second row and column has the boards rotated by 180 degrees

        netRenamePattern - the pattern according to which the net names are transformed
            The default pattern is "Board_{n}-{orig}" which gives each board its own instance of its nets,
            i.e. GND becomes Board_0-GND for the first board , and Board_1-GND for the second board etc

        refRenamePattern - the pattern according to which the reference designators are transformed
            The default pattern is "Board_{n}-{orig}" which gives each board its own instance of its reference designators,
            so R1 becomes Board_0-R1 for the first board, Board_1-R1 for the recond board etc. To keep references the
            same as in the original, set this to "{orig}"

        tolerance - if no sourceArea is specified, the distance by which the selection
            area for the board should extend outside the board edge.
            If you have any objects that are on or outside the board edge, make sure this is big enough to include them.
            Such objects often include zone outlines and connectors.

        Returns a list of the placed substrates. You can use these to generate
        tabs, frames, backbones, etc.
        """

        substrateCount = len(self.substrates)
        netRenamer = lambda x, y: netRenamePattern.format(n=x, orig=y)
        refRenamer = lambda x, y: refRenamePattern.format(n=x, orig=y)
        self._placeBoardsInGrid(boardfile, rows, cols, destination,
                                sourceArea, tolerance, verSpace, horSpace,
                                rotation, netRenamer, refRenamer, placementClass)
        return self.substrates[substrateCount:]

    def makeFrame(self, width, hspace, vspace):
        """
        Build a frame around the boards. Specify width and spacing between the
        boards substrates and the frame. Return a tuple of vertical and
        horizontal cuts.

        Parameters:

        width - width of substrate around board outlines

        slotwidth - width of milled-out perimeter around board outline

        hspace - horizontal space between board outline and substrate

        vspace - vertical space between board outline and substrate

        """
        frameInnerRect = expandRect(shpBoxToRect(self.boardsBBox()), hspace, vspace)
        frameOuterRect = expandRect(frameInnerRect, width)
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

    def makeTightFrame(self, width, slotwidth, hspace, vspace):
        """
        Build a full frame with board perimeter milled out.
        Add your boards to the panel first using appendBoard or makeGrid.

        Parameters:

        width - width of substrate around board outlines

        slotwidth - width of milled-out perimeter around board outline

        hspace - horizontal space between board outline and substrate

        vspace - vertical space between board outline and substrate

        """
        self.makeFrame(width, hspace, vspace)
        boardSlot = GeometryCollection()
        for s in self.substrates:
            boardSlot = boardSlot.union(s.exterior())
        boardSlot = boardSlot.buffer(slotwidth)
        frameBody = box(*self.boardSubstrate.bounds()).difference(boardSlot)
        self.appendSubstrate(frameBody)

    def makeRailsTb(self, thickness):
        """
        Adds a rail to top and bottom.
        """
        minx, miny, maxx, maxy = self.panelBBox()
        topRail = box(minx, maxy, maxx, maxy + thickness)
        bottomRail = box(minx, miny, maxx, miny - thickness)
        self.appendSubstrate(topRail)
        self.appendSubstrate(bottomRail)

    def makeRailsLr(self, thickness):
        """
        Adds a rail to left and right.
        """
        minx, miny, maxx, maxy = self.panelBBox()
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

    def makeVCuts(self, cuts, boundCurves=False):
        """
        Take a list of lines to cut and performs V-CUTS. When boundCurves is
        set, approximate curved cuts by a line from the first and last point.
        Otherwise, raise an exception.
        """
        for cut in cuts:
            if len(cut.simplify(SHP_EPSILON).coords) > 2 and not boundCurves:
                raise RuntimeError("Cannot V-Cut a curve")
            start = roundPoint(cut.coords[0])
            end = roundPoint(cut.coords[-1])
            if start.x == end.x or (abs(start.x - end.x) <= fromMm(0.5) and boundCurves):
                self.addVCutV((start.x + end.x) / 2)
            elif start.y == end.y or (abs(start.y - end.y) <= fromMm(0.5) and boundCurves):
                self.addVCutH((start.y + end.y) / 2)
            else:
                raise RuntimeError("Cannot perform V-Cut which is not horizontal or vertical")

    def makeMouseBites(self, cuts, diameter, spacing, offset=fromMm(0.25),
        prolongation=fromMm(0.5)):
        """
        Take a list of cuts and perform mouse bites. The cuts can be prolonged
        to
        """
        bloatedSubstrate = prep(self.boardSubstrate.substrates.buffer(SHP_EPSILON))
        for cut in cuts:
            cut = cut.simplify(SHP_EPSILON) # Remove self-intersecting geometry
            cut = prolongCut(cut, prolongation)
            offsetCut = cut.parallel_offset(offset, "left")
            length = offsetCut.length
            count = int(length / spacing) + 1
            for i in range(count):
                if count == 1:
                    hole = offsetCut.interpolate(0.5, normalized=True)
                else:
                    hole = offsetCut.interpolate( i * length / (count - 1) )
                if bloatedSubstrate.intersects(hole):
                    self.addNPTHole(wxPoint(hole.x, hole.y), diameter)

    def addNPTHole(self, position, diameter, paste=False):
        """
        Add a drilled non-plated hole to the position (`wxPoint`) with given
        diameter. The paste option allows to place the hole on the paste layers.
        """
        footprint = pcbnew.FootprintLoad(KIKIT_LIB, "NPTH")
        footprint.SetPosition(position)
        for pad in footprint.Pads():
            pad.SetDrillSize(pcbnew.wxSize(diameter, diameter))
            pad.SetSize(pcbnew.wxSize(diameter, diameter))
            if paste:
                layerSet = pad.GetLayerSet()
                layerSet.AddLayer(Layer.F_Paste)
                layerSet.AddLayer(Layer.B_Paste)
                pad.SetLayerSet(layerSet)
        self.board.Add(footprint)

    def addFiducial(self, position, copperDiameter, openingDiameter, bottom=False):
        """
        Add fiducial, i.e round copper pad with solder mask opening to the position (`wxPoint`),
        with given copperDiameter and openingDiameter. By setting bottom to True, the fiducial
        is placed on bottom side.
        """
        footprint = pcbnew.FootprintLoad(KIKIT_LIB, "Fiducial")
        # As of V6, the footprint first needs to be added to the board,
        # then we can change its properties. Otherwise, it misses parent pointer
        # and KiCAD crashes.
        self.board.Add(footprint)
        footprint.SetPosition(position)
        if(bottom):
            if isV6():
                footprint.Flip(position, False)
            else:
                footprint.Flip(position)
        for pad in footprint.Pads():
            pad.SetSize(pcbnew.wxSize(copperDiameter, copperDiameter))
            pad.SetLocalSolderMaskMargin(int((openingDiameter - copperDiameter) / 2))
            pad.SetLocalClearance(int((openingDiameter - copperDiameter) / 2))


    def panelCorners(self, horizontalOffset=0, verticalOffset=0):
        """
        Return the list of top-left, top-right, bottom-left and bottom-right
        corners of the panel. You can specify offsets.
        """
        minx, miny, maxx, maxy = self.panelBBox()
        topLeft = wxPoint(minx + horizontalOffset, miny + verticalOffset)
        topRight = wxPoint(maxx - horizontalOffset, miny + verticalOffset)
        bottomLeft = wxPoint(minx + horizontalOffset, maxy - verticalOffset)
        bottomRight = wxPoint(maxx - horizontalOffset, maxy - verticalOffset)
        return [topLeft, topRight, bottomLeft, bottomRight]

    def addCornerFiducials(self, fidCount, horizontalOffset, verticalOffset,
            copperDiameter, openingDiameter):
        """
        Add up to 4 fiducials to the top-left, top-right, bottom-left and
        bottom-right corner of the board (in this order). This function expects
        there is enough space on the board/frame/rail to place the feature.

        The offsets are measured from the outer edges of the substrate.
        """
        for pos in self.panelCorners(horizontalOffset, verticalOffset)[:fidCount]:
            self.addFiducial(pos, copperDiameter, openingDiameter, False)
            self.addFiducial(pos, copperDiameter, openingDiameter, True)

    def addCornerTooling(self, holeCount, horizontalOffset, verticalOffset,
                         diameter, paste=False):
        """
        Add up to 4 tooling holes to the top-left, top-right, bottom-left and
        bottom-right corner of the board (in this order). This function expects
        there is enough space on the board/frame/rail to place the feature.

        The offsets are measured from the outer edges of the substrate.
        """
        for pos in self.panelCorners(horizontalOffset, verticalOffset)[:holeCount]:
            self.addNPTHole(pos, diameter, paste)

    def addMillFillets(self, millRadius):
        """
        Add fillets to inner conernes which will be produced a by mill with
        given radius.
        """
        self.boardSubstrate.millFillets(millRadius)

    def clearTabsAnnotations(self):
        """
        Remove all existing tab annotations from the panel.
        """
        for s in self.substrates:
            s.annotations = list(
                filter(lambda x: not isinstance(x, TabAnnotation), s.annotations))

    def buildTabsFromAnnotations(self):
        """
        Given annotations for the individual substrates, create tabs for them.
        Tabs are appended to the panel, cuts are returned.

        Expects that a valid partition line is assigned to the the panel.
        """
        tabs, cuts = [], []
        for s in self.substrates:
            t, c = buildTabs(s, s.partitionLine, s.annotations)
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
                dir = normalize((midx - x, midy - y))
                a = TabAnnotation(None, (x, y), dir, width)
                self.substrates[i].annotations.append(a)


    def buildFullTabs(self, framingOffsets):
        """
        Make full tabs. This strategy basically cuts the bounding boxes of the
        PCBs. Not suitable for mousebites. Expects there is a valid partition
        line.

        Return a list of cuts.
        """
        # Compute the bounding box gap polygon. Note that we cannot just merge a
        # rectangle as that would remove internal holes
        bBoxes = box(*self.substrates[0].bounds())
        for s in islice(self.substrates, 1, None):
            bBoxes = bBoxes.union(box(*s.bounds()))
        outerBounds = self.substrates[0].partitionLine.bounds
        for s in islice(self.substrates, 1, None):
            outerBounds = shpBBoxMerge(outerBounds, s.partitionLine.bounds)
        fill = box(*outerBounds).difference(bBoxes)
        self.appendSubstrate(fill)

        # Make the cuts from the bounding boxes of the PCB
        substrateBoundaries = [linestringToSegments(rectToShpBox(s.boundingBox()).exterior)
            for s in self.substrates]
        substrateCuts = [LineString(x) for x in chain(*substrateBoundaries)]

        # Remove outer edges (if any)
        vspace, hspace = framingOffsets
        xvalues = list(chain(*[map(lambda x: x[0], line.coords) for line in substrateCuts]))
        yvalues = list(chain(*[map(lambda x: x[1], line.coords) for line in substrateCuts]))
        minx, maxx = min(xvalues), max(xvalues)
        miny, maxy = min(yvalues), max(yvalues)

        substrateCuts = [x for x in substrateCuts if not (
            (hspace is None and x.coords[0][0] == x.coords[1][0] and x.coords[0][0] in [minx, maxx]) or
            (vspace is None and x.coords[0][1] == x.coords[1][1] and x.coords[0][1] in [miny, maxy])
        )]

        return substrateCuts

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

    def copperFillNonBoardAreas(self, layers=[Layer.F_Cu,Layer.B_Cu]):
        """
        Fill given layers with copper on unused areas of the panel
        (frame, rails and tabs)

        takes a list of layer ids (Default [kikit.defs.Layer.F_Cu, kikit.defs.Layer.B_Cu])
        """
        if not self.boardSubstrate.isSinglePiece():
            raise RuntimeError("The substrate has to be a single piece to fill unused areas")
        if not len(layers)>0:
            raise RuntimeError("No layers to add copper to")
        increaseZonePriorities(self.board)

        zoneContainer = pcbnew.ZONE(self.board)
        boundary = self.boardSubstrate.exterior().boundary
        zoneContainer.Outline().AddOutline(linestringToKicad(boundary))
        for substrate in self.substrates:
            boundary = substrate.exterior().boundary
            zoneContainer.Outline().AddHole(linestringToKicad(boundary))
        zoneContainer.SetPriority(0)

        zoneContainer.SetLayer(layers[0])
        self.board.Add(zoneContainer)
        self.zonesToRefill.append(zoneContainer)
        for l in layers[1:]:
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
        Add a keepout area from top and bottom layers. Area is a shapely
        polygon. Return the keepout area.
        """
        zone = polygonToZone(area, self.board)
        zone.SetIsRuleArea(True)
        zone.SetDoNotAllowTracks(noTracks)
        zone.SetDoNotAllowVias(noVias)
        zone.SetDoNotAllowCopperPour(noCopper)

        zone.SetLayer(Layer.F_Cu)
        layerSet = zone.GetLayerSet()
        layerSet.AddLayer(Layer.B_Cu)
        zone.SetLayerSet(layerSet)

        self.board.Add(zone)
        return zone

    def addText(self, text, position, orientation=0,
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
        textObject.SetTextSize(pcbnew.wxSize(width, height))
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
        if isV6():
            self.board.GetDesignSettings().SetAuxOrigin(point)
        else:
            self.board.SetAuxOrigin(point)

    def getAuxiliaryOrigin(self):
        if isV6():
            return self.board.GetDesignSettings().GetAuxOrigin()
        else:
            return self.board.GetAuxOrigin()

    def setGridOrigin(self, point):
        """
        Set grid origin
        """
        if isV6():
            self.board.GetDesignSettings().SetGridOrigin(point)
        else:
            self.board.SetGridOrigin(point)

    def getGridOrigin(self):
        if isV6():
            return self.board.GetDesignSettings().GetGridOrigin()
        else:
            return self.board.GetGridOrigin()

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
        segment.SetStart(pcbnew.wxPoint(start[0], start[1]))
        segment.SetEnd(pcbnew.wxPoint(end[0], end[1]))
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

    def renderBackbone(self, vthickness, hthickness, vcut, hcut):
        """
        Render horizontal and vertical backbone lines. If zero thickness is
        specified, no backbone is rendered.

        vcut, hcut specifies if vertical or horizontal backbones should be cut.

        Return a list of cuts
        """
        cutpoints = commonPoints(self.backboneLines)
        pieces, cuts = [], []
        for l in self.backboneLines:
            start = l.coords[0]
            end = l.coords[1]
            if isHorizontal(start, end) and hthickness > 0:
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
            if isVertical(start, end) and vthickness > 0:
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

    def addCornerChamfers(self, size):
        corners = self.panelCorners()
        verticalStops = self.panelCorners(0, size)
        horizontalStops = self.panelCorners(size, 0)
        for t, v, h in zip(corners, verticalStops, horizontalStops):
            cutPoly = Polygon([t, v, h, t])
            self.boardSubstrate.cut(cutPoly)

    def translate(self, vec):
        """
        Translates the whole panel by vec. Such a feature can be useful to
        specify the panel placement in the sheet. When we translate panel as the
        last operation, none of the operations have to be placement-aware.
        """
        vec = wxPoint(vec[0], vec[1])
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
        for drcE in self.drcExclusions:
            drcE.position += vec


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
    annotation = getFootprintByReference(board, reference)
    tip = annotation.GetPosition()
    edges = collectEdges(board, "Edge.Cuts")
    # KiCAD 6 will need an adjustment - method Collide was introduced with
    # different parameters. But v6 API is not available yet, so we leave this
    # to future ourselves.
    pointedAt = indexOf(edges, lambda x: x.HitTest(tip))
    rings = extractRings(edges)
    ringPointedAt = indexOf(rings, lambda x: pointedAt in x)
    if ringPointedAt == -1:
        raise RuntimeError("Annotation symbol '{reference}' does not point to a board edge")
    return findBoundingBox([edges[i] for i in rings[ringPointedAt]])


