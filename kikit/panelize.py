from pcbnew import GetBoard, LoadBoard, FromMM, ToMM, wxPoint, wxRect, wxRectMM, wxPointMM
import pcbnew
from enum import Enum, IntEnum
from shapely.geometry import Polygon, MultiPolygon, Point
import shapely
from itertools import product
import numpy as np
import os

from kikit import substrate
from kikit.substrate import Substrate
from kikit.defs import STROKE_T, Layer, EDA_TEXT_HJUSTIFY_T

PKG_BASE = os.path.dirname(__file__)
KIKIT_LIB = os.path.join(PKG_BASE, "resources/kikit.pretty")

def fromDegrees(angle):
    return angle * 10

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
        return wxPoint(bBox.GetX() + bBox.GetWidth(), bbox.GetY() + bBox.GetHeight())


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
    """ Collect edges in sourceArea on given layer """
    edges = []
    for edge in board.GetDrawings():
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

def findBoardBoundingBox(board, sourceArea=None):
    """
    Returns a bounding box (wxRect) of all Edge.Cuts items either in
    specified source area (wxRect) or in the whole board
    """
    edges = collectEdges(board, "Edge.Cuts", sourceArea)
    if len(edges) == 0:
        raise RuntimeError("No board edges found")
    boundingBox = getBBoxWithoutContours(edges[0])
    for edge in edges[1:]:
        boundingBox = combineBoundingBoxes(boundingBox, getBBoxWithoutContours(edge))
    return boundingBox

def collectNetNames(board):
    return [str(x) for x in board.GetNetInfo().NetsByName() if len(str(x)) > 0]

def remapNets(collection, mapping):
    for item in collection:
        item.SetNetCode(mapping[item.GetNetname()].GetNet())

def toPolygon(entity):
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
                    tolerance=0):
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

        Returns bounding box (wxRect) of the extracted area.
        """
        board = LoadBoard(filename)
        self.boardCounter += 1

        if not sourceArea:
            sourceArea = findBoardBoundingBox(board)
        elif shrink:
            sourceArea = findBoardBoundingBox(board, sourceArea)
        enlargedSourceArea = expandRect(sourceArea, tolerance)
        originPoint = getOriginCoord(origin, sourceArea)
        translate = wxPoint(destination[0] - originPoint[0],
                            destination[1] - originPoint[1])

        self._makeNetNamesUnique(board)

        drawings = collectItems(board.GetDrawings(), enlargedSourceArea)
        modules = collectItems(board.GetModules(), enlargedSourceArea)
        tracks = collectItems(board.GetTracks(), enlargedSourceArea)
        zones = collectItems(board.Zones(), enlargedSourceArea)

        for module in modules:
            module.Rotate(originPoint, rotationAngle)
            module.Move(translate)
            appendItem(self.board, module)
        for track in tracks:
            track.Rotate(originPoint, rotationAngle)
            track.Move(translate)
            appendItem(self.board, track)
        for zone in zones:
            zone.Rotate(originPoint, rotationAngle)
            zone.Move(translate)
            appendItem(self.board, zone)
        for netId in board.GetNetInfo().NetsByNetcode():
            self.board.Add(board.GetNetInfo().GetNetItem(netId))

        # Treat drawings differently since they contains board edges
        for drawing in drawings:
            drawing.Rotate(originPoint, rotationAngle)
            drawing.Move(translate)
        edges = [edge for edge in drawings if edge.GetLayerName() == "Edge.Cuts"]
        otherDrawings = [edge for edge in drawings if edge.GetLayerName() != "Edge.Cuts"]
        self.boardSubstrate.union(Substrate(edges))
        for drawing in otherDrawings:
            appendItem(self.board, drawing)
        return sourceArea

    def appendSubstrate(self, substrate, filletRadius=0):
        """
        Append a piece of substrate to the panel. Substrate can be either wxRect
        or Shapely polygon. Newly appended corners can be rounded by specifying
        non-zero filletRadius.
        """
        polygon = toPolygon(substrate)
        if filletRadius == 0:
            self.boardSubstrate.union(polygon)
            return
        filletCandidates = self.boardSubstrate.boundary().intersection(polygon.boundary)
        self.boardSubstrate.union(polygon)
        for geom in filletCandidates:
            if not isinstance(geom, Point):
                continue
            # We found a candidate point for fillet, try to round it
            self.boardSubstrate.fillet(geom, filletRadius)

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

    def _renderVCutV(self, layer=Layer.Cmts_User):
        """ return list of DRAWSEGMENT V-Cuts """
        bBox = self.boardSubstrate.boundingBox()
        minY, maxY = bBox.GetY() - fromMm(10), bBox.GetY() + bBox.GetHeight() + fromMm(10)
        segments = []
        for cut in self.vVCuts:
            segment = pcbnew.DRAWSEGMENT()
            segment.SetShape(STROKE_T.S_SEGMENT)
            segment.SetLayer(layer)
            segment.SetStart(pcbnew.wxPoint(cut, minY))
            segment.SetEnd(pcbnew.wxPoint(cut, maxY))
            segments.append(segment)

            label = pcbnew.TEXTE_PCB(segment)
            label.SetText("V-CUT")
            label.SetLayer(layer)
            label.SetThickness(fromMm(0.3))
            label.SetPosition(wxPoint(cut, minY - fromMm(3)))
            label.SetTextSize(pcbnew.wxSizeMM(3, 3))
            label.SetHorizJustify(EDA_TEXT_HJUSTIFY_T.GR_TEXT_HJUSTIFY_LEFT)
            label.SetTextAngle(900)
            segments.append(label)
        return segments

    def _renderVCutH(self, layer=Layer.Cmts_User):
        """ return list of DRAWSEGMENT V-Cuts """
        bBox = self.boardSubstrate.boundingBox()
        minX, maxX = bBox.GetX() - fromMm(10), bBox.GetX() + bBox.GetWidth() + fromMm(10)
        segments = []
        for cut in self.hVCuts:
            segment = pcbnew.DRAWSEGMENT()
            segment.SetShape(STROKE_T.S_SEGMENT)
            segment.SetLayer(layer)
            segment.SetStart(pcbnew.wxPoint(minX, cut))
            segment.SetEnd(pcbnew.wxPoint(maxX, cut))
            segments.append(segment)

            label = pcbnew.TEXTE_PCB(segment)
            label.SetText("V-CUT")
            label.SetLayer(layer)
            label.SetThickness(fromMm(0.3))
            label.SetPosition(wxPoint(maxX + fromMm(3), cut))
            label.SetTextSize(pcbnew.wxSizeMM(3, 3))
            label.SetHorizJustify(EDA_TEXT_HJUSTIFY_T.GR_TEXT_HJUSTIFY_LEFT)
            segments.append(label)
        return segments

    def _makeNetNamesUnique(self, board):
        prefix = self._uniquePrefix()
        originalNetNames = collectNetNames(board)
        netinfo = board.GetNetInfo()

        newNetMapping = { "": netinfo.GetNetItem("") }
        for name in originalNetNames:
            newNet = pcbnew.NETINFO_ITEM(board, prefix + name)
            newNetMapping[name] = newNet
            board.Add(newNet)

        remapNets(board.GetPads(), newNetMapping)
        remapNets(board.GetTracks(), newNetMapping)
        remapNets(board.Zones(), newNetMapping)

        for name in originalNetNames:
            if name != "":
                board.RemoveNative(netinfo.GetNetItem(name))

    def _boardGridPos(self, destination, i, j, boardSize, horSpace, verSpace):
        # Remove 0.001 mm to compensate for numerical imprecision when
        # merging coincident edges of boards
        return wxPoint(destination[0] + j * (boardSize.GetWidth() + horSpace - FromMM(0.001)),
                       destination[1] + i * (boardSize.GetHeight() + verSpace - FromMM(0.001)))

    def _placeBoardsInGrid(self, boardfile, rows, cols, destination, sourceArea, tolerance,
                  verSpace, horSpace):
        """
        Create a grid of boards, return source board size
        """
        boardSize = wxRect(0, 0, 0, 0)
        for i, j in product(range(rows), range(cols)):
            dest = self._boardGridPos(destination, i, j, boardSize, horSpace, verSpace)
            boardSize = self.appendBoard(boardfile, dest, sourceArea=sourceArea,
                                         tolerance=tolerance, shrink=True, origin=Origin.TopLeft)
        return boardSize

    def _singleTabSize(self, boardSize, expectedSize, spaceSize, last):
        """ Returns offset from board edge, and tab size"""
        if expectedSize == 0: # Full tab, add tab to the spacing
            if not last:
                return 0, boardSize + spaceSize
            return 0, boardSize
        # Smaller tab than board, shrink it!
        shrinkSize = boardSize - expectedSize
        if shrinkSize < 0:
            raise RuntimeError("Tab size is larger ({}) thank board size ({})".format(
                expectedSize, boardSize))
        return shrinkSize // 2, boardSize - shrinkSize

    def _makeSingleInnerTabs(self, destination, rows, cols, boardSize, verSpace,
                             horSpace, verTabWidth, horTabWidth, radius):
        """
        Create inner tabs in board grid by placing exactly one in the middle
        """
        lastRow = lambda x: x == rows - 1
        lastCol = lambda x: x == cols - 1
        cuts = []
        for i, j in product(range(rows), range(cols)):
            dest = self._boardGridPos(destination, i, j, boardSize, horSpace, verSpace)
            if not lastRow(i):
                # Add bottom tab
                xOffset, width = self._singleTabSize(boardSize.GetWidth(),
                                            verTabWidth, horSpace, lastCol(j))
                tab = wxRect(dest[0] + xOffset, dest[1] + boardSize.GetHeight(),
                             width, verSpace)
                cuts.append((
                    (tab.GetX(), tab.GetY()),
                    (tab.GetX() + tab.GetWidth(), tab.GetY())))
                if tab.GetHeight() != 0:
                    cuts.append((
                        (tab.GetX(), tab.GetY() + tab.GetHeight()),
                        (tab.GetX() + tab.GetWidth(), tab.GetY() + tab.GetHeight())))
                    tab = expandRect(tab, FromMM(0.001))
                    self.appendSubstrate(tab, radius)
            if not lastCol(j):
                # Add right tab
                yOffset, height = self._singleTabSize(boardSize.GetHeight(),
                                            horTabWidth, verSpace, lastRow(i))
                tab = wxRect(dest[0] + boardSize.GetWidth(), dest[1] + yOffset,
                             horSpace, height)
                cuts.append((
                    (tab.GetX(), tab.GetY()),
                    (tab.GetX(), tab.GetY() + tab.GetHeight())))
                if tab.GetHeight() != 0:
                    cuts.append((
                        (tab.GetX() + tab.GetWidth(), tab.GetY()),
                        (tab.GetX() + tab.GetWidth(), tab.GetY() + tab.GetHeight())))
                    tab = expandRect(tab, FromMM(0.001))
                    self.appendSubstrate(tab, radius)
        return cuts

    def _makeSingleOuterVerTabs(self, destination, rows, cols, boardSize, verSpace,
                                horSpace, verTabWidth, horTabWidth, radius,
                                outerVerTabThickness, outerHorTabThickness):
        lastCol = lambda x: x == cols - 1
        cuts = []
        def appendVerticalTab(destination, i, outerVerTabThickness):
            dest = self._boardGridPos(destination, 0, i, boardSize, horSpace, verSpace)
            spaceSize = outerHorTabThickness if lastCol(i) else horSpace
            xOffset, width = self._singleTabSize(boardSize.GetWidth(),
                                verTabWidth, spaceSize, False)
            tab = wxRect(dest[0] + xOffset, dest[1] - outerVerTabThickness,
                         width, outerVerTabThickness)
            if i == 0 and verTabWidth == 0:
                tab.SetX(tab.GetX() - outerHorTabThickness)
                tab.SetWidth(tab.GetWidth() + outerHorTabThickness)
            cuts.append((
                (tab.GetX(), tab.GetY() + tab.GetHeight()),
                (tab.GetX() + tab.GetWidth(), tab.GetY() + tab.GetHeight())
            ))
            tab = normalizeRect(tab)
            tab = expandRect(tab, FromMM(0.001))
            self.appendSubstrate(tab, radius)
        for i in range(cols):
            appendVerticalTab(destination, i, outerVerTabThickness)
            dest = self._boardGridPos(destination, rows - 1, 0, boardSize, horSpace, verSpace)
            appendVerticalTab(dest + wxPoint(0, boardSize.GetHeight()), i, -outerVerTabThickness)
        return cuts

    def _makeSingleOuterHorTabs(self, destination, rows, cols, boardSize, verSpace,
                                horSpace, verTabWidth, horTabWidth, radius,
                                outerVerTabThickness, outerHorTabThickness):
        lastRow = lambda x: x == rows - 1
        cuts = []
        def appendHorizontalTab(destination, i, outerHorTabThickness):
            dest = self._boardGridPos(destination, i, 0, boardSize, horSpace, verSpace)
            spaceSize = outerVerTabThickness if lastRow(i) else verSpace
            yOffset, height = self._singleTabSize(boardSize.GetHeight(),
                                horTabWidth, spaceSize, False)
            tab = wxRect(dest[0] - outerHorTabThickness, dest[1] + yOffset,
                         outerHorTabThickness, height)
            if i == 0 and horTabWidth == 0:
                tab.SetY(tab.GetY() - outerVerTabThickness)
                tab.SetHeight(tab.GetHeight() + outerVerTabThickness)
            cuts.append((
                (tab.GetX() + tab.GetWidth(), tab.GetY()),
                (tab.GetX() + tab.GetWidth(), tab.GetY() + tab.GetHeight())
            ))
            tab = normalizeRect(tab)
            tab = expandRect(tab, FromMM(0.001))
            self.appendSubstrate(tab, radius)
        for i in range(rows):
            appendHorizontalTab(destination, i, outerHorTabThickness)
            dest = self._boardGridPos(destination, 0, cols - 1, boardSize, horSpace, verSpace)
            appendHorizontalTab(dest + wxPoint(boardSize.GetWidth(), 0), i, -outerHorTabThickness)
        return cuts

    def makeGrid(self, boardfile, rows, cols, destination, sourceArea=None,
                 tolerance=0, radius=0, verSpace=0, horSpace=0,
                 verTabWidth=0, horTabWidth=0, outerVerTabThickness=0,
                 outerHorTabThickness=0):
        """
        Creates a grid of boards (row x col) as a panel at given destination
        separated by V-CUTS. The source can be either extract automatically of
        from given sourceArea. There can be a spacing between the individual
        board (verSpacing, horSpacing) and the tab width can be adjusted
        (verTabWidth, horTabWidth). Also the user can control whether append the
        outer tabs (e.g. to connect it to a frame) by setting outerVerTabsWidth
        and outerHorTabsWidth.

        Returns a tuple - wxRect with the panel bounding box (excluding
        outerTabs) and a list of cuts (list of lines) to make. You can use the
        list to either create a V-CUTS via makeVCuts or mouse bites via
        makeMouseBites.
        """
        boardSize = self._placeBoardsInGrid(boardfile, rows, cols, destination,
                                    sourceArea, tolerance, verSpace, horSpace)
        cuts = self._makeSingleInnerTabs(destination, rows, cols, boardSize,
                        verSpace, horSpace, verTabWidth, horTabWidth, radius)

        if outerVerTabThickness > 0:
            cuts += self._makeSingleOuterVerTabs(destination, rows, cols, boardSize, verSpace,
                                    horSpace, verTabWidth, horTabWidth, radius,
                                    outerVerTabThickness, outerHorTabThickness)

        if outerHorTabThickness > 0:
            cuts += self._makeSingleOuterHorTabs(destination, rows, cols, boardSize, verSpace,
                                    horSpace, verTabWidth, horTabWidth, radius,
                                    outerVerTabThickness, outerHorTabThickness)

        return (wxRect(destination[0], destination[1],
                       cols * boardSize.GetWidth() + (cols - 1) * horSpace,
                       rows * boardSize.GetHeight() + (rows - 1) * verSpace),
                cuts)

    def makeTightGrid(self, boardfile, rows, cols, destination, verSpace,
                      horSpace, slotWidth, width, height, sourceArea=None,
                      tolerance=0, radius=0, verTabWidth=0, horTabWidth=0):
        """
        Creates a grid of boards just like `makeGrid`, however, it creates a
        milled slot around perimeter of each board and 4 tabs.
        """
        boardSize = self._placeBoardsInGrid(boardfile, rows, cols, destination,
                                    sourceArea, tolerance, verSpace, horSpace)
        panelSize = wxRect(destination[0], destination[1],
                       cols * boardSize.GetWidth() + (cols - 1) * horSpace,
                       rows * boardSize.GetHeight() + (rows - 1) * verSpace)

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

        cuts = self._makeSingleInnerTabs(destination, rows, cols, boardSize,
                        verSpace, horSpace, verTabWidth, horTabWidth, radius)
        cuts += self._makeSingleOuterVerTabs(destination, rows, cols, boardSize, verSpace,
                                    horSpace, verTabWidth, horTabWidth, radius,
                                    slotWidth, slotWidth)
        cuts += self._makeSingleOuterHorTabs(destination, rows, cols, boardSize, verSpace,
                                    horSpace, verTabWidth, horTabWidth, radius,
                                    slotWidth, slotWidth)
        return (outerRect, cuts)


    def makeFrame(self, innerArea, width, height, offset, radius=0):
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
        self.appendSubstrate(polygon, radius)
        for x, y in innerRing:
            self.boardSubstrate.fillet(Point(x, y), radius)
        return outerRect

    def makeVCuts(self, cuts):
        """
        Take a list of lines to cut and performs V-CUTS
        """
        for start, end in cuts:
            if start[0] == end[0]:
                self.addVCutV(start[0])
            elif start[1] == end[1]:
                self.addVCutH(start[1])
            else:
                raise RuntimeError("Cannot perform V-Cut which is not horizontal or vertical")

    def makeMouseBites(self, cuts, diameter, spacing):
        """
        Take a list of cuts and perform mouse bites.
        """
        for start, end in cuts:
            start, end = np.array(start), np.array(end)
            dir = end - start
            count = int(np.linalg.norm(dir) / spacing) + 1
            for i in range(count):
                hole = start + i * dir / (count - 1)
                self.addNPTHole(wxPoint(hole[0], hole[1]), diameter)

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