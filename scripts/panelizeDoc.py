#!/usr/bin/env python3

"""
Generate documentation in markdown format for panelization
"""

from kikit import panelize
from kikit import substrate
from kikit.doc import header, printHelp, printHeader
from pcbnewTransition import pcbnew
import inspect

def synopsis(object):
    printHeader(object)
    printHelp(object)

def classMethods(c):
    for name, o in inspect.getmembers(c, predicate=inspect.isfunction):
        if name.startswith("_"):
            continue
        synopsis(o)

print(
f"""
# Panelization

When you want to panelize a board, you are expected to load the `kikit.panelize`
module and create an instance of the `Panel` class.

All units are in the internal KiCAD units (1 nm). You can use predefined
constants to convert from/to them:

```.py
from kikit.units import *

l = 1 * mm    # 1 mm
l = 42 * inch # 42 inches
l = 15 * cm   # 15 cm
a = 90 * deg  # 90°
a = 1 * rad   # 1 radian
```

You can also use functions `{header(panelize.fromMm)}` and
`{header(panelize.toMm)}` to convert to/from them if you like them more. You are
also encouraged to use the functions and objects the native KiCAD Python API
offers, e.g.: {'`, `'.join([header(pcbnew.wxPoint), header(pcbnew.wxPointMM),
              header(pcbnew.wxRect), header(pcbnew.wxRectMM)])}.
""")

print(
"""
## Basic Concepts

The `kikit.panelize.Panel` class holds a panel under construction. Basically it
is `pcbnew.BOARD` without outlines. The outlines are held separately as
`shapely.MultiPolygon` so we can easily merge pieces of a substrate, add cuts
and export it back to `pcbnew.BOARD`. This is all handled by the class
`kikit.substrate.Substrate`.

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

You read more about the algorithms for generating tabs in a separate document
[understanding tabs](understandingTabs.md).

## Cuts

All methods constructing panels do not create cuts directly, instead, they
return them. This allows the users to decided how to perform the cuts - e.g.,
mouse bites, V-Cuts, silk-screen...

The cuts are represented by `shapely.LineString`. The string is oriented - a
positive side of the string should face the inner side of the board. This is
important when, e.g., offsetting mouse bites.

To perform the cuts, see methods of the `panelize.Panel` class below.

## Source Area And Tolerance

When placing a board, you might specify source area -- a rectangle from which
the components are extracted. If no source area is specified, the smallest
bounding box of all Edge.Cuts is taken.

Only components that fully fit inside source area are copied to the panel. To
include components sticking out of the board outline, you can specify tolerance
-- a distance by which the source area is expanded when copying components.
"""
)

print(f"""
## Panel class

This class has the following relevant members:
- `board` - `pcbnew.BOARD` of the panel. Does not contain any edges.
- `substrates` - `kikit.substrate.Substrate` - individual substrates appended
  via `{printHeader(panelize.Panel.appendBoard)}`. You can use them to get the
  original outline (and e.g., generate tabs accroding to it).
- `boardSubstrate` - `kikit.substrate.Substrate` of the whole panel.
- `backboneLines` - a list of lines representing backbone candidates. Read more
  about it in [understanding tabs](understandingTabs.md).
""")

classMethods(panelize.Panel)

print(f"""
## Substrate class

This class represents a pice of substrate (with no components). Basically it is
just a relatively thin wrapper around shapely polygons. On top of that, it keeps
a partition line for the substrate. Read more about partition lines in
[understanding tabs](understandingTabs.md).

""")

classMethods(substrate.Substrate)

