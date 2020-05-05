from pcbnew import GetBoard, LoadBoard, FromMM, ToMM, wxPoint, wxRect, wxRectMM, wxPointMM
import pcbnew
from enum import Enum, IntEnum
from shapely.geometry import Polygon, MultiPolygon, Point, LineString
from shapely.prepared import prep
import shapely
from itertools import product, chain
import numpy as np
import os

from kikit import substrate
from kikit.substrate import Substrate
from kikit.defs import STROKE_T, Layer, EDA_TEXT_HJUSTIFY_T

PKG_BASE = os.path.dirname(__file__)
KIKIT_LIB = os.path.join(PKG_BASE, "resources/kikit.pretty")

def identity(x):
    return x

def fromDegrees(angle):
    return angle * 10

def fromKicadAngle(angle):
    return angle / 10

def fromMm(mm):
    """Convert millimeters to KiCAD internal units"""
    return pcbnew.FromMM(mm)

def toMm(kiUnits):
    """Convert KiCAD internal units to millimeters"""
    return pcbnew.ToMM(kiUnits)

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


def fitsIn(what, where):
    """ Return true iff 'what' (wxRect) is fully contained in 'where' (wxRect) """
    return (what.GetX() >= where.GetX() and
            what.GetX() + what.GetWidth() <= where.GetX() + where.GetWidth() and
            what.GetY() >= where.GetY() and
            what.GetY() + what.GetHeight() <= where.GetY() + where.GetHeight())

def combineBoundingBoxes(a, b):
    """ Retrun wxRect as a combination of source bounding boxes """
    x = min(a.GetX(), b.GetX())
    y = min(a.GetY(), b.GetY())
    topLeft = wxPoint(x, y)
    x = max(a.GetX() + a.GetWidth(), b.GetX() + b.GetWidth())
    y = max(a.GetY() + a.GetHeight(), b.GetY() + b.GetHeight())
    bottomRight = wxPoint(x, y)
    return wxRect(topLeft, bottomRight)

def collectEdges(board, layerName, sourceArea=None):
    """ Collect edges in sourceArea on given layer including modules """
    edges = []
    for edge in chain(board.GetDrawings(), *[m.GraphicalItems() for m in board.GetModules()]):
        if edge.GetLayerName() != layerName:
            continue
        if not sourceArea or fitsIn(edge.GetBoundingBox(), sourceArea):
            edges.append(edge)
    return edges

def collectItems(boardCollection, sourceArea):
    """ Returns a list of board items fully contained in the source area """
    return list([x for x in boardCollection if fitsIn(x.GetBoundingBox(), sourceArea)])

def appendItem(board, item):
    """
    Make a coppy of the item and append it to the board. Allows to append items
    from one board to another.
    """
    try:
        newItem = item.Duplicate()
    except TypeError: # Module has overridden the method, cannot be called directly
        newItem = pcbnew.Cast_to_BOARD_ITEM(item).Duplicate().Cast()
    board.Add(newItem)

def transformArea(board, sourceArea, translate, origin, rotationAngle):
    """
    Rotates and translates all board items in given source area
    """
    for drawing in collectItems(board.GetDrawings(), sourceArea):
        drawing.Rotate(origin, rotationAngle)
        drawing.Move(translate)
    for module in collectItems(board.GetModules(), sourceArea):
        module.Rotate(origin, rotationAngle)
        module.Move(translate)
    for track in collectItems(board.GetTracks(), sourceArea):
        track.Rotate(origin, rotationAngle)
        track.Move(translate)
    for zone in collectItems(board.Zones(), sourceArea):
        zone.Rotate(origin, rotationAngle)
        zone.Move(translate)

def getBBoxWithoutContours(edge):
    width = edge.GetWidth()
    edge.SetWidth(0)
    bBox = edge.GetBoundingBox()
    edge.SetWidth(width)
    return bBox

def findBoundingBox(edges):
    """
    Return a bounding box of all drawings in edges
    """
    if len(edges) == 0:
        raise RuntimeError("No board edges found")
    boundingBox = getBBoxWithoutContours(edges[0])
    for edge in edges[1:]:
        boundingBox = combineBoundingBoxes(boundingBox, getBBoxWithoutContours(edge))
    return boundingBox

def findBoardBoundingBox(board, sourceArea=None):
    """
    Returns a bounding box (wxRect) of all Edge.Cuts items either in
    specified source area (wxRect) or in the whole board
    """
    edges = collectEdges(board, "Edge.Cuts", sourceArea)
    return findBoundingBox(edges)

def collectNetNames(board):
    return [str(x) for x in board.GetNetInfo().NetsByName() if len(str(x)) > 0]

def remapNets(collection, mapping):
    for item in collection:
        item.SetNetCode(mapping[item.GetNetname()].GetNet())

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
    return wxRect(rect.GetX() - offsetX, rect.GetY() - offsetY,
        rect.GetWidth() + 2 * offsetX, rect.GetHeight() + 2 * offsetY)

def translateRect(rect, translation):
    """
    Given a wxRect return a new rect translated by transaltion (tuple-like object)
    """
    return wxRect(rect.GetX() + translation[0], rect.GetY() + translation[1],
        rect.GetWidth(), rect.GetHeight())

def normalizeRect(rect):
    """ If rectangle is specified via negative width/height, corrects it """
    if rect.GetHeight() < 0:
        rect.SetY(rect.GetY() + rect.GetHeight())
        rect.SetHeight(-rect.GetHeight())
    if rect.GetWidth() < 0:
        rect.SetX(rect.GetX() + rect.GetWidth())
        rect.SetWidth(-rect.GetWidth())
    return rect

def flipRect(rect):
    return wxRect(rect.GetY(), rect.GetX(), rect.GetHeight(), rect.GetWidth())

def mirrorRectX(rect, axis):
    return wxRect(2 * axis - rect.GetX() - rect.GetWidth(), rect.GetY(),
                  rect.GetWidth(), rect.GetHeight())

def mirrorRectY(rect, axis):
    return wxRect(rect.GetX(), 2 * axis - rect.GetY() - rect.GetHeight(),
                  rect.GetWidth(), rect.GetHeight())

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

def undoTransformation(point, rotation, origin, translation):
    """
    We apply a transformation "Rotate around origin and then translate" when
    placing a board. Given a point and original transformation parameters,
    return the original point position.
    """
    # Abuse PcbNew to do so
    segment = pcbnew.DRAWSEGMENT()
    segment.SetShape(STROKE_T.S_SEGMENT)
    segment.SetStart(wxPoint(point[0], point[1]))
    segment.SetEnd(wxPoint(0, 0))
    segment.Move(wxPoint(-translation[0], -translation[1]))
    segment.Rotate(origin, -rotation)
    return segment.GetStart()

def removeCutsFromModule(module):
    """
    Find all graphical items in the module, remove them and return them as a
    list
    """
    edges = []
    for edge in module.GraphicalItems():
        if edge.GetLayerName() != "Edge.Cuts":
            continue
        module.Remove(edge)
        edges.append(edge)
    return edges

def renameNets(board, renamer):
    """
    Given a board and renaming function (taking original name, returning new
    name) renames the nets
    """
    originalNetNames = collectNetNames(board)
    netinfo = board.GetNetInfo()

    newNetMapping = { "": netinfo.GetNetItem("") }
    for name in originalNetNames:
        newNet = pcbnew.NETINFO_ITEM(board, renamer(name))
        newNetMapping[name] = newNet
        board.Add(newNet)

    remapNets(board.GetPads(), newNetMapping)
    remapNets(board.GetTracks(), newNetMapping)
    remapNets(board.Zones(), newNetMapping)

    for name in originalNetNames:
        if name != "":
            board.RemoveNative(netinfo.GetNetItem(name))

def renameRefs(board, renamer):
    """
    Given a board and renaming function (taking original name, returning new
    name) renames the references
    """
    for module in board.GetModules():
        ref = module.Reference().GetText()
        module.Reference().SetText(renamer(ref))

def isBoardEdge(edge):
    """
    Decide whether the drawing is a board edge or not.

    The rule is: all drawings on Edge.Cuts layer are edges.
    """
    return isinstance(edge, pcbnew.DRAWSEGMENT) and edge.GetLayerName() == "Edge.Cuts"

class Panel:
    """
    Basic interface for panel building. Instance of this class represents a
    single panel. You can append boards, add substrate pieces, make cuts or add
    holes to the panel. Once you finish, you have to save the panel to a file.
    """
    def __init__(self):
        """
        Initializes empty panel.
        """
        self.board = pcbnew.BOARD()
        self.boardCounter = 0
        self.boardSubstrate = Substrate([]) # Keep substrate in internal representation,
                                            # Draw it just before saving
        self.hVCuts = set() # Keep V-cuts as numbers and append them just before saving
        self.vVCuts = set() # to make them truly span the whole panel

    def save(self, filename):
        """
        Saves the panel to a file.
        """
        for edge in self.boardSubstrate.serialize():
            self.board.Add(edge)
        vcuts = self._renderVCutH() + self._renderVCutV()
        for cut in vcuts:
            self.board.Add(cut)
        self.board.Save(filename)
        for edge in collectEdges(self.board, "Edge.Cuts"):
            self.board.Remove(edge)
        for cut in vcuts:
            self.board.Remove(cut)

    def _uniquePrefix(self):
        return "Board_{}-".format(self.boardCounter)

    def appendBoard(self, filename, destination, sourceArea=None,
                    origin=Origin.Center, rotationAngle=0, shrink=False,
                    tolerance=0, bufferOutline=fromMm(0.001), netRenamer=None,
                    refRenamer=None):
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
        filled zones which can reach out of the board edges.

        You can also specify functions which will rename the net and ref names.
        By default, nets are renamed to "Board_{n}-{orig}", refs are unchanged.
        The renamers are given board seq number and original name

        Returns bounding box (wxRect) of the extracted area placed at the
        destination.
        """
        board = LoadBoard(filename)
        self.boardCounter += 1

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
        renameNets(board, lambda x: netRenamer(self.boardCounter, x))
        if refRenamer is not None:
            renameRefs(board, lambda x: refRenamer(self.boardCounter, x))

        drawings = collectItems(board.GetDrawings(), enlargedSourceArea)
        modules = collectItems(board.GetModules(), enlargedSourceArea)
        tracks = collectItems(board.GetTracks(), enlargedSourceArea)
        zones = collectItems(board.Zones(), enlargedSourceArea)

        edges = []
        for module in modules:
            module.Rotate(originPoint, rotationAngle)
            module.Move(translation)
            edges += removeCutsFromModule(module)
            appendItem(self.board, module)
        for track in tracks:
            track.Rotate(originPoint, rotationAngle)
            track.Move(translation)
            appendItem(self.board, track)
        for zone in zones:
            zone.Rotate(originPoint, rotationAngle)
            zone.Move(translation)
            appendItem(self.board, zone)
        for netId in board.GetNetInfo().NetsByNetcode():
            self.board.Add(board.GetNetInfo().GetNetItem(netId))

        # Treat drawings differently since they contains board edges
        for drawing in drawings:
            drawing.Rotate(originPoint, rotationAngle)
            drawing.Move(translation)
        edges += [edge for edge in drawings if isBoardEdge(edge)]
        otherDrawings = [edge for edge in drawings if not isBoardEdge(edge)]
        try:
            self.boardSubstrate.union(Substrate(edges, bufferOutline))
        except substrate.PositionError as e:
            point = undoTransformation(e.point, rotationAngle, originPoint, translation)
            raise substrate.PositionError(filename + ": " + e.origMessage, point)
        for drawing in otherDrawings:
            appendItem(self.board, drawing)
        return findBoundingBox(edges)

    def appendSubstrate(self, substrate):
        """
        Append a piece of substrate or a list of pieces to the panel. Substrate
        can be either wxRect or Shapely polygon. Newly appended corners can be
        rounded by specifying non-zero filletRadius.
        """
        polygon = toPolygon(substrate)
        self.boardSubstrate.union(polygon)

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

    def _setVCutSegmentStyle(self, segment, layer):
        segment.SetShape(STROKE_T.S_SEGMENT)
        segment.SetLayer(layer)
        segment.SetWidth(fromMm(0.4))

    def _setVCutLabelStyle(self, label, layer):
        label.SetText("V-CUT")
        label.SetLayer(layer)
        label.SetThickness(fromMm(0.4))
        label.SetTextSize(pcbnew.wxSizeMM(2, 2))
        label.SetHorizJustify(EDA_TEXT_HJUSTIFY_T.GR_TEXT_HJUSTIFY_LEFT)

    def _renderVCutV(self, layer=Layer.Cmts_User):
        """ return list of DRAWSEGMENT V-Cuts """
        bBox = self.boardSubstrate.boundingBox()
        minY, maxY = bBox.GetY() - fromMm(3), bBox.GetY() + bBox.GetHeight() + fromMm(3)
        segments = []
        for cut in self.vVCuts:
            segment = pcbnew.DRAWSEGMENT()
            self._setVCutSegmentStyle(segment, layer)
            segment.SetStart(pcbnew.wxPoint(cut, minY))
            segment.SetEnd(pcbnew.wxPoint(cut, maxY))
            segments.append(segment)

            label = pcbnew.TEXTE_PCB(segment)
            self._setVCutLabelStyle(label, layer)
            label.SetPosition(wxPoint(cut, minY - fromMm(3)))
            label.SetTextAngle(900)
            segments.append(label)
        return segments

    def _renderVCutH(self, layer=Layer.Cmts_User):
        """ return list of DRAWSEGMENT V-Cuts """
        bBox = self.boardSubstrate.boundingBox()
        minX, maxX = bBox.GetX() - fromMm(3), bBox.GetX() + bBox.GetWidth() + fromMm(3)
        segments = []
        for cut in self.hVCuts:
            segment = pcbnew.DRAWSEGMENT()
            self._setVCutSegmentStyle(segment, layer)
            segment.SetStart(pcbnew.wxPoint(minX, cut))
            segment.SetEnd(pcbnew.wxPoint(maxX, cut))
            segments.append(segment)

            label = pcbnew.TEXTE_PCB(segment)
            self._setVCutLabelStyle(label, layer)
            label.SetPosition(wxPoint(maxX + fromMm(3), cut))
            segments.append(label)
        return segments

    def _boardGridPos(self, destination, i, j, boardSize, horSpace, verSpace):
        return wxPoint(destination[0] + j * (boardSize.GetWidth() + horSpace),
                       destination[1] + i * (boardSize.GetHeight() + verSpace))

    def _placeBoardsInGrid(self, boardfile, rows, cols, destination, sourceArea, tolerance,
                  verSpace, horSpace, rotation, netRenamer, refRenamer):
        """
        Create a grid of boards, return source board size aligned at the top
        left corner
        """
        boardSize = wxRect(0, 0, 0, 0)
        topLeftSize = None
        for i, j in product(range(rows), range(cols)):
            dest = self._boardGridPos(destination, i, j, boardSize, horSpace, verSpace)
            boardSize = self.appendBoard(boardfile, dest, sourceArea=sourceArea,
                                         tolerance=tolerance, origin=Origin.TopLeft,
                                         rotationAngle=rotation, netRenamer=netRenamer,
                                         refRenamer=refRenamer)
            if not topLeftSize:
                topLeftSize = boardSize
        return topLeftSize

    def _makeFullHorizontalTabs(self, destination, rows, cols, boardSize,
                                verSpace, horSpace, outerVerSpace, outerHorSpace):
        """
        Crate full tabs for given grid.

        Return tab body, list of cut edges and list of fillet candidates as a
        tuple.
        """
        width = cols * boardSize.GetWidth() + (cols - 1) * horSpace
        height = rows * boardSize.GetHeight() + (rows - 1) * verSpace
        polygons = []
        cuts = []
        for i in range(cols - 1):
            pos = (i + 1) * boardSize.GetWidth() + i * horSpace
            tl = destination + wxPoint(pos, -outerVerSpace)
            tr = destination + wxPoint(pos + horSpace, -outerVerSpace)
            br = destination + wxPoint(pos + horSpace, height + outerVerSpace)
            bl = destination + wxPoint(pos, height + outerVerSpace)
            if horSpace > 0:
                polygon = Polygon([tl, tr, br, bl])
                polygons.append(polygon)
                cuts.append(LineString([tl, bl]))
            cuts.append(LineString([br, tr]))
        if outerHorSpace > 0:
            # Outer tabs
            polygons.append(Polygon([
                destination + wxPoint(-outerHorSpace, -outerVerSpace),
                destination + wxPoint(0, -outerVerSpace),
                destination + wxPoint(0, height + outerVerSpace),
                destination + wxPoint(-outerHorSpace, height + outerVerSpace)]))
            polygons.append(Polygon([
                destination + wxPoint(width + outerHorSpace, -outerVerSpace),
                destination + wxPoint(width, -outerVerSpace),
                destination + wxPoint(width, height + outerVerSpace),
                destination + wxPoint(width + outerHorSpace, height + outerVerSpace)]))

            cuts.append(LineString([destination + wxPoint(0, height + outerVerSpace),
                destination + wxPoint(0, -outerVerSpace)]))
            cuts.append(LineString([destination + wxPoint(width, -outerVerSpace),
                destination + wxPoint(width, height + outerVerSpace)]))
        return polygons, cuts

    def _makeFullVerticalTabs(self, destination, rows, cols, boardSize,
                                   verSpace, horSpace, outerVerSpace, outerHorSpace):
        """
        Crate full tabs for given grid.

        Return tab body, list of cut edges and list of fillet candidates as a
        tuple.
        """
        width = cols * boardSize.GetWidth() + (cols - 1) * horSpace
        height = rows * boardSize.GetHeight() + (rows - 1) * verSpace
        polygons = []
        cuts = []
        for i in range(rows - 1):
            pos = (i + 1) * boardSize.GetHeight() + i * verSpace
            tl = destination + wxPoint(-outerHorSpace, pos)
            tr = destination + wxPoint(width + outerHorSpace, pos)
            br = destination + wxPoint(width + outerHorSpace, pos + verSpace)
            bl = destination + wxPoint(-outerHorSpace, pos + verSpace)
            if verSpace > 0:
                polygon = Polygon([tl, tr, br, bl])
                polygons.append(polygon)
                cuts.append(LineString([tr, tl]))
            cuts.append(LineString([bl, br]))
        if outerVerSpace > 0:
            # Outer tabs
            polygons.append(Polygon([
                destination + wxPoint(-outerHorSpace, 0),
                destination + wxPoint(-outerHorSpace, -outerVerSpace),
                destination + wxPoint(outerHorSpace + width, - outerVerSpace),
                destination + wxPoint(outerHorSpace + width, 0)]))
            polygons.append(Polygon([
                destination + wxPoint(-outerHorSpace, height),
                destination + wxPoint(-outerHorSpace, height + outerVerSpace),
                destination + wxPoint(outerHorSpace + width, height + outerVerSpace),
                destination + wxPoint(outerHorSpace + width, height)]))
            cuts.append(LineString([destination + wxPoint(-outerHorSpace, 0),
                destination + wxPoint(width + outerHorSpace, 0)]))
            cuts.append(LineString([destination + wxPoint(width + outerHorSpace, height),
                destination + wxPoint(-outerHorSpace, height)]))
        return polygons, cuts

    def _tabSpacing(self, width, count):
        """
        Given a width of board edge and tab count, return an iterable with tab
        offsets.
        """
        return [width * i / (count + 1) for i in range(1, count + 1)]

    def _makeVerGridTabs(self, destination, rows, cols, boardSize, verSpace,
                      horSpace, verTabWidth, horTabWidth, verTabCount,
                      horTabCount, outerVerTabThickness, outerHorTabThickness):
        polygons = []
        cuts = []
        for i, j in product(range(rows), range(cols)):
            dest = self._boardGridPos(destination, i, j, boardSize, horSpace, verSpace)
            if (i != 0 and verSpace > 0) or outerVerTabThickness > 0: # Add tabs to the top side
                tabThickness = outerVerTabThickness if i == 0 else verSpace / 2
                for tabPos in self._tabSpacing(boardSize.GetWidth(), verTabCount):
                    t, f = self.boardSubstrate.tab(
                        dest + wxPoint(tabPos, -tabThickness), [0, 1], verTabWidth)
                    polygons.append(t)
                    cuts.append(f)
            if (i != rows - 1 and verSpace > 0) or outerVerTabThickness > 0: # Add tabs to the bottom side
                tabThickness = outerVerTabThickness if i == rows - 1 else verSpace / 2
                for tabPos in self._tabSpacing(boardSize.GetWidth(), verTabCount):
                    origin = dest + wxPoint(tabPos, boardSize.GetHeight() + tabThickness)
                    t, f = self.boardSubstrate.tab(origin, [0, -1], verTabWidth)
                    polygons.append(t)
                    cuts.append(f)
        return polygons, cuts

    def _makeHorGridTabs(self, destination, rows, cols, boardSize, verSpace,
                      horSpace, verTabWidth, horTabWidth, verTabCount,
                      horTabCount, outerVerTabThickness, outerHorTabThickness):
        polygons = []
        cuts = []
        for i, j in product(range(rows), range(cols)):
            dest = self._boardGridPos(destination, i, j, boardSize, horSpace, verSpace)
            if (j != 0 and horSpace > 0) or outerHorTabThickness > 0: # Add tabs to the left side
                tabThickness = outerHorTabThickness if j == 0 else horSpace / 2
                for tabPos in self._tabSpacing(boardSize.GetHeight(), horTabCount):
                    t, f = self.boardSubstrate.tab(
                        dest + wxPoint(-tabThickness, tabPos), [1, 0], horTabWidth)
                    polygons.append(t)
                    cuts.append(f)
            if (j != cols - 1 and horSpace > 0) or outerHorTabThickness > 0: # Add tabs to the right side
                tabThickness = outerHorTabThickness if j == cols - 1 else horSpace / 2
                for tabPos in self._tabSpacing(boardSize.GetHeight(), horTabCount):
                    origin = dest + wxPoint(boardSize.GetWidth() + tabThickness, tabPos)
                    t, f = self.boardSubstrate.tab(
                        origin, [-1, 0], horTabWidth)
                    polygons.append(t)
                    cuts.append(f)
        return polygons, cuts

    def makeGrid(self, boardfile, rows, cols, destination, sourceArea=None,
                 tolerance=0, verSpace=0, horSpace=0, verTabCount=1,
                 horTabCount=1, verTabWidth=0, horTabWidth=0,
                 outerVerTabThickness=0, outerHorTabThickness=0, rotation=0,
                 netRenamePattern="Board_{n}-{orig}",
                 refRenamePattern="Board_{n}-{orig}"):
        """
        Creates a grid of boards (row x col) as a panel at given destination
        separated by V-CUTS. The source can be either extracted automatically or
        from given sourceArea. There can be a spacing between the individual
        board (verSpacing, horSpacing) and the tab width can be adjusted
        (verTabWidth, horTabWidth). Also, the user can control whether to append
        the outer tabs (e.g. to connect it to a frame) by setting
        outerVerTabsWidth and outerHorTabsWidth.

        Returns a tuple - wxRect with the panel bounding box (excluding
        outerTabs) and a list of cuts (list of lines) to make. You can use the
        list to either create a V-CUTS via makeVCuts or mouse bites via
        makeMouseBites.
        """
        netRenamer = lambda x, y: netRenamePattern.format(n=x, orig=y)
        refRenamer = lambda x, y: refRenamePattern.format(n=x, orig=y)
        boardSize = self._placeBoardsInGrid(boardfile, rows, cols, destination,
                                    sourceArea, tolerance, verSpace, horSpace,
                                    rotation, netRenamer, refRenamer)
        gridDest = wxPoint(boardSize.GetX(), boardSize.GetY())
        tabs, cuts = [], []

        if verTabCount != 0:
            if verTabWidth == 0:
                t, c = self._makeFullVerticalTabs(gridDest, rows, cols,
                    boardSize, verSpace, horSpace, outerVerTabThickness, outerHorTabThickness)
            else:
                t, c = self._makeVerGridTabs(gridDest, rows, cols, boardSize,
                    verSpace, horSpace, verTabWidth, horTabWidth, verTabCount,
                    horTabCount, outerVerTabThickness, outerHorTabThickness)
            tabs += t
            cuts += c

        if horTabCount != 0:
            if horTabWidth == 0:
                t, c = self._makeFullHorizontalTabs(gridDest, rows, cols,
                    boardSize, verSpace, horSpace, outerVerTabThickness, outerHorTabThickness)
            else:
                t, c = self._makeHorGridTabs(gridDest, rows, cols, boardSize,
                    verSpace, horSpace, verTabWidth, horTabWidth, verTabCount,
                    horTabCount, outerVerTabThickness, outerHorTabThickness)
            tabs += t
            cuts += c

        tabs = list([t.buffer(fromMm(0.001), join_style=2) for t in tabs])
        self.appendSubstrate(tabs)

        return (wxRect(gridDest[0], gridDest[1],
                       cols * boardSize.GetWidth() + (cols - 1) * horSpace,
                       rows * boardSize.GetHeight() + (rows - 1) * verSpace),
                cuts)


    def makeTightGrid(self, boardfile, rows, cols, destination, verSpace,
                      horSpace, slotWidth, width, height, sourceArea=None,
                      tolerance=0, verTabWidth=0, horTabWidth=0,
                      verTabCount=1, horTabCount=1, rotation=0,
                      netRenamePattern="Board_{n}-{orig}",
                      refRenamePattern="Board_{n}-{orig}"):
        """
        Creates a grid of boards just like `makeGrid`, however, it creates a
        milled slot around perimeter of each board and 4 tabs.
        """
        netRenamer = lambda x, y: netRenamePattern.format(n=x, orig=y)
        refRenamer = lambda x, y: refRenamePattern.format(n=x, orig=y)
        boardSize = self._placeBoardsInGrid(boardfile, rows, cols, destination,
                                    sourceArea, tolerance, verSpace, horSpace,
                                    rotation, netRenamer, refRenamer)
        gridDest = wxPoint(boardSize.GetX(), boardSize.GetY())
        panelSize = wxRect(destination[0], destination[1],
                       cols * boardSize.GetWidth() + (cols - 1) * horSpace,
                       rows * boardSize.GetHeight() + (rows - 1) * verSpace)

        tabs, cuts = [], []
        if verTabCount != 0:
            t, c = self._makeVerGridTabs(gridDest, rows, cols, boardSize,
                    verSpace, horSpace, verTabWidth, horTabWidth, verTabCount,
                    horTabCount, slotWidth, slotWidth)
            tabs += t
            cuts += c
        if horTabCount != 0:
            t, c = self._makeHorGridTabs(gridDest, rows, cols, boardSize,
                    verSpace, horSpace, verTabWidth, horTabWidth, verTabCount,
                    horTabCount, slotWidth, slotWidth)
            tabs += t
            cuts += c

        xDiff = (width - panelSize.GetWidth()) // 2
        if xDiff < 0:
            raise RuntimeError("The frame is to small")
        yDiff = (height - panelSize.GetHeight()) // 2
        if yDiff < 0:
            raise RuntimeError("The frame is to small")
        outerRect = expandRect(panelSize, xDiff, yDiff)
        outerRing = rectToRing(outerRect)
        frame = Polygon(outerRing)
        frame = frame.difference(self.boardSubstrate.exterior().buffer(slotWidth))
        self.appendSubstrate(frame)

        tabs = list([t.buffer(fromMm(0.001), join_style=2) for t in tabs])
        self.appendSubstrate(tabs)

        if verTabCount != 0 or horTabCount != 0:
            self.boardSubstrate.removeIslands()

        return (outerRect, cuts)


    def makeFrame(self, innerArea, width, height, offset):
        """
        Adds a frame around given `innerArea` (`wxRect`), which can be obtained,
        e.g., by `makeGrid`, with given `width` and `height`. Space with width
        `offset` is added around the `innerArea`.
        """
        innerArea = expandRect(innerArea, offset)
        innerArea = expandRect(innerArea, -fromMm(0.01))
        xDiff = (width - innerArea.GetWidth()) // 2
        if xDiff < 0:
            raise RuntimeError("The frame is to small")
        yDiff = (height - innerArea.GetHeight()) // 2
        if yDiff < 0:
            raise RuntimeError("The frame is to small")
        innerRing = rectToRing(innerArea)
        outerRect = expandRect(innerArea, xDiff, yDiff)
        outerRing = rectToRing(outerRect)
        polygon = Polygon(outerRing, [innerRing])
        self.appendSubstrate(polygon)
        return outerRect

    def makeVCuts(self, cuts, boundCurves=False):
        """
        Take a list of lines to cut and performs V-CUTS. When boundCurves is
        set, approximate curved cuts by a line from the first and last point.
        Otherwise, raise an exception.
        """
        for cut in cuts:
            if len(cut.simplify(fromMm(0.01)).coords) > 2 and not boundCurves:
                raise RuntimeError("Cannot V-Cut a curve")
            start = roundPoint(cut.coords[0])
            end = roundPoint(cut.coords[-1])
            if start.x == end.x or (abs(start.x - end.x) <= fromMm(0.5) and boundCurves):
                self.addVCutV((start.x + end.x) / 2)
            elif start.y == end.y or (abs(start.y - end.y) <= fromMm(0.5) and boundCurves):
                self.addVCutH((start.y + end.y) / 2)
            else:
                raise RuntimeError("Cannot perform V-Cut which is not horizontal or vertical")

    def makeMouseBites(self, cuts, diameter, spacing, offset=fromMm(0.25)):
        """
        Take a list of cuts and perform mouse bites.
        """
        bloatedSubstrate = prep(self.boardSubstrate.substrates.buffer(fromMm(0.01)))
        for cut in cuts:
            cut = cut.simplify(fromMm(0.001)) # Remove self-intersecting geometry
            offsetCut = cut.parallel_offset(offset, "left")
            length = offsetCut.length
            count = int(length / spacing) + 1
            for i in range(count):
                if count == 1:
                    hole = offsetCut.interpolate(0.5, normalized=True)
                else:
                    hole = offsetCut.interpolate( i * length / (count - 1) )
                if bloatedSubstrate.intersects(hole.buffer(0.8 * diameter / 2)):
                    self.addNPTHole(wxPoint(hole.x, hole.y), diameter)

    def addNPTHole(self, position, diameter):
        """
        Add a drilled non-plated hole to the position (`wxPoint`) with given
        diameter.
        """
        module = pcbnew.PCB_IO().FootprintLoad(KIKIT_LIB, "NPTH")
        module.SetPosition(position)
        for pad in module.Pads():
            pad.SetDrillSize(pcbnew.wxSize(diameter, diameter))
            pad.SetSize(pcbnew.wxSize(diameter, diameter))
        self.board.Add(module)

    def addFiducial(self, position, copperDiameter, openingDiameter, bottom=False):
        """
        Add fiducial, i.e round copper pad with solder mask opening to the position (`wxPoint`),
        with given copperDiameter and openingDiameter. By setting bottom to True, the fiducial
        is placed on bottom side.
        """
        module = pcbnew.PCB_IO().FootprintLoad(KIKIT_LIB, "Fiducial")
        module.SetPosition(position)
        if(bottom):
            module.Flip(position)
        for pad in module.Pads():
            pad.SetSize(pcbnew.wxSize(copperDiameter, copperDiameter))
            pad.SetLocalSolderMaskMargin(int((openingDiameter - copperDiameter) / 2))
            pad.SetLocalClearance(int((openingDiameter - copperDiameter) / 2))
        self.board.Add(module)

    def addMillFillets(self, millRadius):
        """
        Add fillets to inner conernes which will be produced a by mill with
        given radius.
        """
        self.boardSubstrate.millFillets(millRadius)

    def layerToTabs(self, layerName, tabWidth):
        """
        Take all line drawsegments from the given layer and convert them to
        tabs.

        The tabs are created by placing a tab origin into the line starting
        point and spanning the tab in the line direction up to the line length.
        Therefore, it is necessary that the line is long enough to penetarete
        the boardoutline.

        The lines are deleted from panel.

        Returns list of tabs substrates and a list of cuts to perform.
        """
        lines = [element for element in self.board.GetDrawings()
                    if isinstance(element, pcbnew.DRAWSEGMENT) and
                       element.GetShape() == STROKE_T.S_SEGMENT and
                       element.GetLayerName() == layerName]
        tabs, cuts = [], []
        for line in lines:
            origin = line.GetStart()
            direction = line.GetEnd() - line.GetStart()
            tab, cut = self.boardSubstrate.tab(origin, direction, tabWidth,
                line.GetLength())
            tabs.append(tab)
            cuts.append(cut)
            self.board.Remove(line)
        return tabs, cuts