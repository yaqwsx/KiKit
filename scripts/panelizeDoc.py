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

The following example creates 3 x 3 grid of boards in a frame separated by V-CUTS.

```
panel = Panel()
size, cuts = panel.makeGrid("test.kicad_pcb", 4, 3, wxPointMM(100, 40),
            tolerance=fromMm(5), verSpace=fromMm(5), horSpace=fromMm(5),
            outerHorTabThickness=fromMm(3), outerVerTabThickness=fromMm(3),
            verTabWidth=fromMm(15), horTabWidth=fromMm(8),
            radius=fromMm(1))
panel.makeVCuts(cuts)
# alternative: panel.makeMouseBites(cuts, diameter=fromMm(0.5), spacing=fromMm(1))
panel.makeFrame(size, fromMm(100), fromMm(100), fromMm(3), radius=fromMm(1))
panel.save("out.kicad_pcb")
```
""")

