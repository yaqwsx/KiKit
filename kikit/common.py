from pcbnewTransition import pcbnew
from kikit.intervals import Interval, AxialLine
from pcbnew import wxPoint, wxRect
import os
from itertools import product, chain, islice
import numpy as np
from shapely.geometry import LinearRing
import shapely.geometry

PKG_BASE = os.path.dirname(__file__)
KIKIT_LIB = os.path.join(PKG_BASE, "resources/kikit.pretty")
SHP_EPSILON = pcbnew.FromMM(0.001) # Common factor of enlarging substrates to
                                  # cover up numerical imprecisions of Shapely

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
    """ Collect edges in sourceArea on given layer including footprints """
    edges = []
    for edge in chain(board.GetDrawings(), *[m.GraphicalItems() for m in board.GetFootprints()]):
        if edge.GetLayerName() != layerName:
            continue
        if not sourceArea or fitsIn(edge.GetBoundingBox(), sourceArea):
            edges.append(edge)
    return edges

def collectItems(boardCollection, sourceArea):
    """ Returns a list of board items fully contained in the source area """
    return list([x for x in boardCollection if fitsIn(x.GetBoundingBox(), sourceArea)])

def collectFootprints(boardCollection, sourceArea):
    """ Returns a list of board footprints fully contained in the source area ignoring reference a value label"""
    return list([x for x in boardCollection if fitsIn(x.GetBoundingBox(False, False), sourceArea)])

def getBBoxWithoutContours(edge):
    width = edge.GetWidth()
    edge.SetWidth(0)
    bBox = edge.GetBoundingBox()
    edge.SetWidth(width)
    return bBox

def listGeometries(shapelyObject):
    """
    Given a shapely object, return an iterable of all geometries. I.e., for
    single items, return an iterable containing only the original item. For
    collections, return iterable of all the geometries in it.
    """
    if hasattr(shapelyObject, 'geoms'):
        return shapelyObject.geoms
    return [shapelyObject]

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

def rectCenter(rect):
    """
    Given a wxRect return its center
    """
    return wxPoint(rect[0] + rect.GetWidth() // 2, rect[1] + rect.GetHeight() // 2)

def rectByCenter(center, width, height):
    """
    Given a center point and size, return wxRect
    """
    return wxRect(center[0] - width // 2, center[1] - height // 2, width, height)

def normalize(vector):
    """ Return a vector with unit length """
    vec = np.array([vector[0], vector[1]])
    return vec / np.linalg.norm(vector)

def makePerpendicular(vector):
    """
    Given a 2D vector, return a vector which is perpendicular to the input one
    """
    return np.array([vector[1], -vector[0]])

def linestringToSegments(linestring):
    """
    Given a Shapely linestring, return a list of tuples with start and endpoint
    of the segment
    """
    return [x for x in zip(linestring.coords, islice(linestring.coords, 1, None))]

def tl(rect):
    """ Return top left corner of rect """
    return wxPoint(rect.GetX(), rect.GetY())

def tr(rect):
    """ Return top right corner of rect """
    return wxPoint(rect.GetX() + rect.GetWidth(), rect.GetY())

def br(rect):
    """ Return bottom right corner of rect """
    return wxPoint(rect.GetX() + rect.GetWidth(), rect.GetY() + rect.GetHeight())

def bl(rect):
    """ Return bottom left corner of rect """
    return wxPoint(rect.GetX(), rect.GetY() + rect.GetHeight())

def removeComponents(board, references):
    """
    Remove components with references from the board. References is a list of
    strings
    """
    for footprint in board.GetFootprints():
        if footprint.GetReference() in references:
            board.Remove(footprint)

def parseReferences(dStr):
    """
    Parse comma separated list of component references to a list
    """
    return [x.strip() for x in dStr.split(",") if len(x.strip()) > 0]


def shpBBoxLeft(bbox):
    """
    Given a shapely bounding box, return left edge as (pos, interval)
    """
    return AxialLine(bbox[0], bbox[1], bbox[3])

def shpBBoxRight(bbox):
    """
    Given a shapely bounding box, return right edge as (pos, interval)
    """
    return AxialLine(bbox[2], bbox[1], bbox[3])

def shpBBoxTop(bbox):
    """
    Given a shapely bounding box, return top edge as (pos, interval)
    """
    return AxialLine(bbox[1], bbox[0], bbox[2])

def shpBBoxBottom(bbox):
    """
    Given a shapely bounding box, return bottom edge as (pos, interval)
    """
    return AxialLine(bbox[3], bbox[0], bbox[2])

def shpBBoxMerge(a, b):
    """
    Given two shapely bounding boxes, return smallest bounding box where both
    can fit.
    """
    return (
        min(a[0], b[0]),
        min(a[1], b[1]),
        max(a[2], b[2]),
        max(a[3], b[3])
    )

def shpBBoxExpand(box, x, y=None):
    """
    Given a shapely bounding box, return new one expanded by given amount. If y
    is not supplied, it the same as x.
    """
    if y is None:
        y = x
    return (box[0] - x, box[1] - y, box[2] + x, box[3] + y)

def shpBoxToRect(box):
    box = list([int(x) for x in box])
    return wxRect(box[0], box[1], box[2] - box[0], box[3] - box[1])

def rectToShpBox(rect):
    return shapely.geometry.box(rect.GetX(), rect.GetY(),
        rect.GetX() + rect.GetWidth(), rect.GetY() + rect.GetHeight())

def isLinestringCyclic(line):
    c = line.coords
    return c[0] == c[-1] or isinstance(line, LinearRing)

def fromOpt(object, default):
    """
    Given an object, return it if not None. Otherwise return default
    """
    return object if object is not None else default

def isBottomLayer(layer):
    """
    Decide if layer is a bottom layer
    """
    return str(layer).startswith("Layer.B_")

def commonPoints(lines):
    """
    Given a list of lines, return dictionary - vertice -> count. Where count
    specifies how many lines share the vertex.
    """
    count = {}
    for l in lines:
        for c in l.coords:
            count[c] = count.get(c, 0) + 1
    return count

def isHorizontal(start, end):
    """
    Given a line decide if it is horizontal
    """
    return start[1] == end[1]

def isVertical(start, end):
    """
    Given a line decide if it is vertical
    """
    return start[0] == end[0]

def resolveAnchor(anchor):
    """
    Given a string anchor name, return a function that transforms wxRect into
    a wxPoint
    """
    choices = {
        "tl": lambda x: x.GetPosition(),
        "tr": lambda x: x.GetPosition() + wxPoint(x.GetWidth(), 0),
        "bl": lambda x: x.GetPosition() + wxPoint(0, x.GetHeight()),
        "br": lambda x: x.GetPosition() + wxPoint(x.GetWidth(), x.GetHeight()),
        "mt": lambda x: x.GetPosition() + wxPoint(x.GetWidth() / 2, 0),
        "mb": lambda x: x.GetPosition() + wxPoint(x.GetWidth() / 2, x.GetHeight()),
        "ml": lambda x: x.GetPosition() + wxPoint(0, x.GetHeight() / 2),
        "mr": lambda x: x.GetPosition() + wxPoint(x.GetWidth(), x.GetHeight() / 2),
        "c":  lambda x: x.GetPosition() + wxPoint(x.GetWidth() / 2, x.GetHeight() / 2)
    }
    return choices[anchor]

def indexOf(list, predicate):
    """
    Return the index of the first element that satisfies predicate. If no
    element is found, return -1
    """
    for i, x in enumerate(list):
        if predicate(x):
            return i
    return -1

def readParameterList(inputStr):
    """
    Given a string, read semicolon separated parameter list in the form of
    `key: value; key: value`. You can escape via `\\`
    """
    from kikit.panelize_ui import splitStr

    if len(inputStr.strip()) == 0:
        return {}
    try:
        values = {}
        for i, pair in enumerate(splitStr(";", "\\", inputStr)):
            if len(pair.strip()) == 0:
                continue
            s = pair.split(":")
            if i == 0 and len(s) == 1:
                values["type"] = s[0].strip()
                continue
            key, value = s[0].strip(), s[1].strip()
            values[key] = value
        return values
    except (TypeError, IndexError):
        raise RuntimeError(f"'{pair}' is not a valid key: value pair")
