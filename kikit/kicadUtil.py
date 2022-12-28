from typing import Tuple
from .common import KiLength
from .units import mm
from .sexpr import SExpr, findNode
from .defs import PAPER_DIMENSIONS

def getPageDimensionsFromAst(ast: SExpr) -> Tuple[KiLength, KiLength]:
    paperNode = findNode(ast, "paper")
    if paperNode is None:
        # KiCAD 5 board use "page" instead of "paper"
        paperNode = findNode(ast, "page")
    if paperNode is None:
        raise RuntimeError("Source document doesn't contain paper size information")
    value = paperNode.items[1].value
    if value == "User":
        size = (paperNode[2].value, paperNode[3].value)
        return tuple(int(float(x) * mm) for x in size)
    try:
        size = PAPER_DIMENSIONS[value]
        if len(paperNode.items) >= 3 and paperNode.items[2] == "portrait":
            size = (size[1], size[0])
        return tuple(int(x) for x in size)
    except KeyError:
        raise RuntimeError(f"Uknown paper size {value}") from None

