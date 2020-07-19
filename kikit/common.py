import pcbnew
from pcbnew import wxPoint, wxRect
import os
from itertools import product, chain
import numpy as np

PKG_BASE = os.path.dirname(__file__)
KIKIT_LIB = os.path.join(PKG_BASE, "resources/kikit.pretty")

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
    for module in board.GetModules():
        if module.GetReference() in references:
            board.Remove(module)

def parseReferences(dStr):
    """
    Parse comma separated list of component references to a list
    """
    return [x.strip() for x in dStr.split(",") if len(x.strip()) > 0]