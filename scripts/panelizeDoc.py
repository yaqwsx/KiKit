#!/usr/bin/env python3

"""
Generate documentation in markdown format for panelization
"""

from kikit import panelize
from kikit.doc import header, printHelp, printHeader

import pcbnew

print(
"""
# Panelization

When you want to panelize a board, you are expected to load the `kikit.panelize`
module and create an instance of the `Panel` class.

All units are in the internal KiCAD units (1 nm). You can use functions `{}` and
`{}` to convert to/from them (synopsis below). You are also encouraged to use
the functions and objects the native KiCAD Python API offers, e.g.: {}.

""".format(
    header(panelize.fromMm),
    header(panelize.toMm),
    "`" + "`, `".join([header(pcbnew.wxPoint), header(pcbnew.wxPointMM),
              header(pcbnew.wxRect), header(pcbnew.wxRectMM)]) + "`"))

print(
"""
## Basic Concepts

The `panelize.Panel` class holds a panel under construction. Basically it is
`pcbnew.BOARD` without outlines. The outlines are held separately as
`shapely.MultiPolygon` so we can easily merge pieces of a substrate, add cuts
and export it back to `pcbnew.BOARD`.

## Tabs

There are two ways to create tabs: generate a piece of a substrate by hand, or
use tab generator.

To generate a piece of a substrate, create a shapely.Polygon. Then add the piece
of substrate via `panelize.Panel.appendSubstrate`. This method also accepts a
`wxRect` for convenience.

The tab generator is available via `panelize.Panel.boardSubstrate.tab`. This
method takes an origin point, direction, and tab width. It tries to build a tab
by extruding a tab with the given width in the given direction and stops when it
reaches an existing substrate. It returns a tuple - the tab substrate and a
piece of the outline of the original board, which was removed by the tab. Then
add the piece of a substrate via `panelize.Panel.appendSubstrate`. This design
choice was made as batch adding of substrates is more efficient. Therefore, you
are advised to first generate all the tabs and then append them to the board.

## Cuts

All methods constructing panels do not create cuts directly, instead, they
return them. This allows the users to decided how to perform the cuts - e.g.,
mouse bites, V-Cuts, silk-screen...

The cuts are represented by `shapely.LineString`. The string is oriented - a
positive side of the string should face the inner side of the board. This is
important when, e.g., offsetting mouse bites.

To perform the cuts, see methods of the `panelize.Panel` class below.

"""
)

print("""
## Panel class
""")

printHelp(panelize.Panel)

printHeader(panelize.Panel.appendBoard)
printHelp(panelize.Panel.appendBoard)

printHeader(panelize.Panel.save)
printHelp(panelize.Panel.save)

printHeader(panelize.Panel.appendSubstrate)
printHelp(panelize.Panel.appendSubstrate)

printHeader(panelize.Panel.makeGrid)
printHelp(panelize.Panel.makeGrid)

printHeader(panelize.Panel.makeTightGrid)
printHelp(panelize.Panel.makeTightGrid)

printHeader(panelize.Panel.makeFrame)
printHelp(panelize.Panel.makeFrame)

printHeader(panelize.Panel.makeVCuts)
printHelp(panelize.Panel.makeVCuts)

printHeader(panelize.Panel.makeMouseBites)
printHelp(panelize.Panel.makeMouseBites)

printHeader(panelize.Panel.addNPTHole)
printHelp(panelize.Panel.addNPTHole)

print("""
## Examples

### Simple grid

The following example creates a 3 x 3 grid of boards in a frame separated by V-CUTS.

```
panel = Panel()
size, cuts = panel.makeGrid("test.kicad_pcb", 4, 3, wxPointMM(100, 40),
            tolerance=fromMm(5), verSpace=fromMm(5), horSpace=fromMm(5),
            outerHorTabThickness=fromMm(3), outerVerTabThickness=fromMm(3),
            verTabWidth=fromMm(15), horTabWidth=fromMm(8))
panel.makeVCuts(cuts)
# alternative: panel.makeMouseBites(cuts, diameter=fromMm(0.5), spacing=fromMm(1))
panel.makeFrame(size, fromMm(100), fromMm(100), fromMm(3), radius=fromMm(1))
panel.addMillFillets(fromMm(1))
panel.save("out.kicad_pcb")
```
""")

