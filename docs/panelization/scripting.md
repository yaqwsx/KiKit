# Introduction to scripting with KiKit

This document will show you how to use KiKit as a library for panelization. The
full reference for the available API is located in the [next
section](python_api.md).

## Basic concepts

Let's start with an overview of the foundational concepts in KiKit.

### Units

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

You can also use functions `fromMm(mm)` and `toMm(kiUnits)` to convert to/from
them if you like them more. You are also encouraged to use the functions and
objects that the native KiCAD Python API offers, e.g.: `pcbnew.wxPoint(args)`,
`pcbnew.wxPointMM(mmx, mmy)`, `pcbnew.wxRect(args)`, `pcbnew.wxRectMM(x, y, wx,
wy)`.

### Substrate

When KiKit loads a KiCAD board, it takes the Edge.Cuts layer and tries to
interpret it as a set of 2D polygons. If it cannot interpret them (i.e, there is
a discontinuous outline), it raises an exception.

These polygons has a notion of what is inside and what is outside. We can also
perform boolean operation on them (i.e., merge two polygons, subtract one from
the other, etc.). When we save the panel, the polygons are converted back to
outlines. All internal operations in KiKit that changes the board shape operate
on top of the polygonal representation, not the outline themselves.

The polygonal representation of board shape is called PCB *substrate* and it is
represented by the class `kikit.substrate.Substrate`. Internally, KiKit uses the
library [Shapely](https://shapely.readthedocs.io/en/stable/manual.html) to
represent the polygon. We advise you to get at least briefly familiar with it as
whenever you need to create a new piece of substrate (e.g., for a tab) you will
do so using the operations Shapely provides.

The `Substrate` class encapsulates the functionality regarding converting an
outline into a polygon and vice-versa and modification of the substrate
(add/subtract from it/construct a tab for it). For convenience, it also holds
the partition lines associated with the substrate. For more details about
partition lines, please refer to section *Tabs* below.

### Panel

The panel construction is handled via `kikit.panelize.Panel` class. This class
represents a panel under construction as `pcbnew.Board` without outlines. The
outlines are represented via a substrate and it is converted into outline only
on saving the panel to file.

The panel class provides you with a number of methods to construct the panel;
e.g., append a board at given coordinates, create a grid of boards, add piece of
substrate to it, add framing, create a cut, etc.

A typical workflow with the `Panel` class is the following:

- create an instance of the class,
- append boards to it (via `appendBoard` or `makeAGrid`),
- once all boards are appended, a partition line should be constructed via
  calling `buildPartitionLineFromBB` or manually set. Without a partition line
  the automatic tab building nor backbone do not work.
- create tabs:
    - you can append a pieces of substrate as you need (you will have to
      specify your cuts manually), and/or
    - you can place annotations where the tabs should be and render those
      automatically (including cuts).
- create a framing and place any other features of the tab (tooling holes,
  fiducials, text markings, backbone),
- render cuts from lines to features (e.g., mouse bites),
- post-process the panel (e.g, specify a copper fill, simulate milling),
- save the panel.

During the whole process you can directly access `panel.board` of the type
`pcbnew.Board` and use the KiCAD API to add or remove the features on the
boards.

### Tabs & Partition line

Every tab consists of two features: a piece of substrate that connects the
individual board on the panel and a cut that will be broken when you depanelize
the board.

In KiKit, the substrate is represented as a `Substrate`, more precisely as
`shapely.geometry.Polygon`. This substrate is appended to the resulting panel
substrate. The cut is represented as a polyline of the type
`shapely.geometry.LineString`. KiKit accepts the polyline and it can either
convert it into mouse bites or V-cuts.

You can build the tab substrate and cuts manually. In that case, just build the
tab shape as `Polygon` and append it to the board via `Panel.appendSubstrate`.
You also construct the cuts manually as `LineString` and you turn it

- into mousebites via `Panel.makeMouseBites`, or
- into V-cuts via `Panel.makeVCuts`. You can also use `Panel.addVCutV` or
  `Panel.addVCutH` in this case and avoid creating the `LineString`.

You will use this approach in the simple cases or cases when you need a
specially shaped tabs.

The second approach is to let KiKit generate the tabs and cuts automatically
based on annotations. Annotation is just a marking on the board outline that
specifies "here should be a tab of this width". You can read the annotations
from source board (there are special footprints for that), generate it manually
or use some of the strategies to place the annotations (e.g., place tabs in a
spacing or in given number along edges). Note that the strategies often need a
properly build partition line. Once you are finished, you can render the tabs
using `Panel.buildTabsFromAnnotations`. This function will merge the tab bodies
and returns a list of cuts. With the list of cuts, you can further decide
whether to ignore them or render them via mousebites or V-cuts. For more details
on the automated process of building tabs from annotations, see [understanding
tabs](tabs.md).

The document [understanding tabs](tabs.md) also explains what is a
partition line and how it is used. Let us add that partition line is represented
as shapely collection of line strings. The partition line is not a single one
for the whole panel, but it is stored separately for each appended board as the
annotations are rendered independently for each appended board.

Also note that you can use the partition line as guide when placing features
(e.g., adding a holes on backbone, etc.).

### Appending Boards

The simples approach to adding boards to a panel is using `Panel.appendBoard`.
This places a board in the panel and also, it renames the nets such that they
are panel-wise unique. This is necessary to pass DRC. You can specify the
renaming pattern if you want. The substrate of the board is added the panel
substrate, but it is also stored separately in `Panel.substrates` as the shape
of the original board can be used to generate the automatic tabs and also it is
used to copper-fill the non-board areas of the panel. You can also use these
substrates to build your custom features.

If you make single-board panels, you can use the function `Panel.makeGrid` to
quickly place the boards in a grid. The function returns the list of individual
substrates. You can use the substrates e.g., to build custom tabs or other
features.

