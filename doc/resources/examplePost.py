from kikit.units import mm
from pcbnew import wxPoint

def kikitPostprocess(panel, arg):
    minx, miny, maxx, maxy = panel.panelBBox()
    position = wxPoint((minx + maxx) / 2, miny + 2 * mm)
    panel.addNPTHole(position, 3 * mm)