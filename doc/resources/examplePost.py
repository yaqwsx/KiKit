from kikit.units import mm
from pcbnew import VECTOR2I

def kikitPostprocess(panel, arg):
    minx, miny, maxx, maxy = panel.panelBBox()
    position = VECTOR2I((minx + maxx) / 2, miny + 2 * mm)
    panel.addNPTHole(position, 3 * mm)
