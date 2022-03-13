
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

You can also use functions `fromMm(mm)` and
`toMm(kiUnits)` to convert to/from them if you like them more. You are
also encouraged to use the functions and objects the native KiCAD Python API
offers, e.g.: wxPoint(args)`, `wxPointMM(mmx, mmy)`, `wxRect(args)`, `wxRectMM(x, y, wx, wy).


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


#### `appendBoard`
```
appendBoard(self, filename, destination, sourceArea=None, origin=Origin.Center, 
            rotationAngle=0, shrink=False, tolerance=0, bufferOutline=1000, 
            netRenamer=None, refRenamer=None, inheritDrc=True, 
            interpretAnnotations=True)
```

## Panel class

This class has the following relevant members:
- `board` - `pcbnew.BOARD` of the panel. Does not contain any edges.
- `substrates` - `kikit.substrate.Substrate` - individual substrates appended
  via `None`. You can use them to get the
  original outline (and e.g., generate tabs accroding to it).
- `boardSubstrate` - `kikit.substrate.Substrate` of the whole panel.
- `backboneLines` - a list of lines representing backbone candidates. Read more
  about it in [understanding tabs](understandingTabs.md).


#### `addCornerChamfers`
```
addCornerChamfers(self, size)
```
None

#### `addCornerFiducials`
```
addCornerFiducials(self, fidCount, horizontalOffset, verticalOffset, 
                   copperDiameter, openingDiameter)
```
Add up to 4 fiducials to the top-left, top-right, bottom-left and
bottom-right corner of the board (in this order). This function expects
there is enough space on the board/frame/rail to place the feature.

The offsets are measured from the outer edges of the substrate.

#### `addCornerFillets`
```
addCornerFillets(self, radius)
```
None

#### `addCornerTooling`
```
addCornerTooling(self, holeCount, horizontalOffset, verticalOffset, diameter, 
                 paste=False)
```
Add up to 4 tooling holes to the top-left, top-right, bottom-left and
bottom-right corner of the board (in this order). This function expects
there is enough space on the board/frame/rail to place the feature.

The offsets are measured from the outer edges of the substrate.

#### `addFiducial`
```
addFiducial(self, position, copperDiameter, openingDiameter, bottom=False)
```
Add fiducial, i.e round copper pad with solder mask opening to the position (`wxPoint`),
with given copperDiameter and openingDiameter. By setting bottom to True, the fiducial
is placed on bottom side.

#### `addKeepout`
```
addKeepout(self, area, noTracks=True, noVias=True, noCopper=True)
```
Add a keepout area from top and bottom layers. Area is a shapely
polygon. Return the keepout area.

#### `addLine`
```
addLine(self, start, end, thickness, layer)
```
Add a line to the panel based on starting and ending point

#### `addMillFillets`
```
addMillFillets(self, millRadius)
```
Add fillets to inner conernes which will be produced a by mill with
given radius.

#### `addNPTHole`
```
addNPTHole(self, position, diameter, paste=False)
```
Add a drilled non-plated hole to the position (`wxPoint`) with given
diameter. The paste option allows to place the hole on the paste layers.

#### `addText`
```
addText(self, text, position, orientation=0, width=1500000, height=1500000, 
        thickness=300000, hJustify=EDA_TEXT_HJUSTIFY_T.GR_TEXT_HJUSTIFY_CENTER, 
        vJustify=EDA_TEXT_VJUSTIFY_T.GR_TEXT_VJUSTIFY_CENTER, 
        layer=Layer.F_SilkS)
```
Add text at given position to the panel. If appending to the bottom
side, text is automatically mirrored.

#### `addVCutH`
```
addVCutH(self, pos)
```
Adds a horizontal V-CUT at pos (integer in KiCAD units).

#### `addVCutV`
```
addVCutV(self, pos)
```
Adds a horizontal V-CUT at pos (integer in KiCAD units).

#### `appendBoard`
```
appendBoard(self, filename, destination, sourceArea=None, origin=Origin.Center, 
            rotationAngle=0, shrink=False, tolerance=0, bufferOutline=1000, 
            netRenamer=None, refRenamer=None, inheritDrc=True, 
            interpretAnnotations=True)
```
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
filled zones which can reach out of the board edges or footprints that
extend outside the board outline, like connectors.

You can also specify functions which will rename the net and ref names.
By default, nets are renamed to "Board_{n}-{orig}", refs are unchanged.
The renamers are given board seq number and original name.

You can also decide whether you would like to inherit design rules from
this boards or not.

Returns bounding box (wxRect) of the extracted area placed at the
destination and the extracted substrate of the board.

#### `appendSubstrate`
```
appendSubstrate(self, substrate)
```
Append a piece of substrate or a list of pieces to the panel. Substrate
can be either wxRect or Shapely polygon. Newly appended corners can be
rounded by specifying non-zero filletRadius.

#### `boardsBBox`
```
boardsBBox(self)
```
Return common bounding box for all boards in the design (ignores the
individual pieces of substrate) as a shapely box.

#### `buildFullTabs`
```
buildFullTabs(self, framingOffsets)
```
Make full tabs. This strategy basically cuts the bounding boxes of the
PCBs. Not suitable for mousebites. Expects there is a valid partition
line.

Return a list of cuts.

#### `buildPartitionLineFromBB`
```
buildPartitionLineFromBB(self, boundarySubstrates=[], safeMargin=0)
```
Builds partition & backbone line from bounding boxes of the substrates.
You can optionally pass extra substrates (e.g., for frame). Without
these extra substrates no partition line would be generated on the side
where the boundary is, therefore, there won't be any tabs.

#### `buildTabAnnotationsCorners`
```
buildTabAnnotationsCorners(self, width)
```
Add tab annotations to the corners of the individual substrates.

#### `buildTabAnnotationsFixed`
```
buildTabAnnotationsFixed(self, hcount, vcount, hwidth, vwidth, minDistance, 
                         ghostSubstrates)
```
Add tab annotations for the individual substrates based on number of
tabs in horizontal and vertical direction. You can specify individual
width in each direction.

If the edge is short for the specified number of tabs with given minimal
spacing, the count is reduced.

You can also specify ghost substrates (for the future framing).

#### `buildTabAnnotationsSpacing`
```
buildTabAnnotationsSpacing(self, spacing, hwidth, vwidth, ghostSubstrates)
```
Add tab annotations for the individual substrates based on their spacing.

You can also specify ghost substrates (for the future framing).

#### `buildTabsFromAnnotations`
```
buildTabsFromAnnotations(self)
```
Given annotations for the individual substrates, create tabs for them.
Tabs are appended to the panel, cuts are returned.

Expects that a valid partition line is assigned to the the panel.

#### `clearTabsAnnotations`
```
clearTabsAnnotations(self)
```
Remove all existing tab annotations from the panel.

#### `copperFillNonBoardAreas`
```
copperFillNonBoardAreas(self, layers=[<Layer.F_Cu: 0>, <Layer.B_Cu: 31>])
```
Fill given layers with copper on unused areas of the panel
(frame, rails and tabs)

takes a list of layer ids (Default [kikit.defs.Layer.F_Cu, kikit.defs.Layer.B_Cu])

#### `debugRenderBackboneLines`
```
debugRenderBackboneLines(self)
```
Render partition line to the panel to be easily able to inspect them via
Pcbnew.

#### `debugRenderBoundingBoxes`
```
debugRenderBoundingBoxes(self)
```
None

#### `debugRenderPartitionLines`
```
debugRenderPartitionLines(self)
```
Render partition line to the panel to be easily able to inspect them via
Pcbnew.

#### `getAuxiliaryOrigin`
```
getAuxiliaryOrigin(self)
```
None

#### `getGridOrigin`
```
getGridOrigin(self)
```
None

#### `getPrlFilepath`
```
getPrlFilepath(self, path=None)
```
None

#### `getProFilepath`
```
getProFilepath(self, path=None)
```
None

#### `inheritCopperLayers`
```
inheritCopperLayers(self, board)
```
Update the panel's layer count to match the design being panelized.
Raise an error if this is attempted twice with inconsistent layer count
boards.

#### `inheritDesignSettings`
```
inheritDesignSettings(self, board)
```
Inherit design settings from the given board specified by a filename or
a board

#### `inheritPageSize`
```
inheritPageSize(self, board)
```
Inherit page size from a board specified by a filename or a board

#### `inheritProperties`
```
inheritProperties(self, board)
```
Inherit text properties from a board specified by a filename or a board

#### `inheritTitleBlock`
```
inheritTitleBlock(self, board)
```
Inherit title block from a board specified by a filename or a board

#### `locateBoard`
```
locateBoard(inputFilename, expandDist=None)
```
Given a board filename, find its source area and optionally expand it by the given distance.

Parameters:

inputFilename - the path to the board file

expandDist - the distance by which to expand the board outline in each direction to ensure elements that are outside the board are included

#### `makeFrame`
```
makeFrame(self, width, hspace, vspace)
```
Build a frame around the boards. Specify width and spacing between the
boards substrates and the frame. Return a tuple of vertical and
horizontal cuts.

Parameters:

width - width of substrate around board outlines

slotwidth - width of milled-out perimeter around board outline

hspace - horizontal space between board outline and substrate

vspace - vertical space between board outline and substrate

#### `makeFrameCutsH`
```
makeFrameCutsH(self, innerArea, frameInnerArea, outerArea)
```
Generate horizontal cuts for the frame corners and return them

#### `makeFrameCutsV`
```
makeFrameCutsV(self, innerArea, frameInnerArea, outerArea)
```
Generate vertical cuts for the frame corners and return them

#### `makeGrid`
```
makeGrid(self, boardfile, sourceArea, rows, cols, destination, verSpace, 
         horSpace, rotation, 
         placementClass=<class 'kikit.panelize.BasicGridPosition'>, 
         netRenamePattern=Board_{n}-{orig}, refRenamePattern=Board_{n}-{orig}, 
         tolerance=0)
```
Place the given board in a regular grid pattern with given spacing
(verSpace, horSpace). The board position can be fine-tuned via
placementClass. The nets and references are renamed according to the
patterns.

Parameters:

boardfile - the path to the filename of the board to be added

sourceArea - the region within the file specified to be selected (see also tolerance, below)
    set to None to automatically calculate the board area from the board file with the given tolerance

rows - the number of boards to place in the vertical direction

cols - the number of boards to place in the horizontal direction

destination - the center coordinates of the first board in the grid (for example, wxPointMM(100,50))

verSpace - the vertical spacing (distance, not pitch) between boards

horSpace - the horizontal spacing (distance, not pitch) between boards

rotation - the rotation angle to be applied to the source board before placing it

placementClass - the placement rules for boards. The builtin classes are:
    BasicGridPosition - places each board in its original orientation
    OddEvenColumnPosition - every second column has the boards rotated by 180 degrees
    OddEvenRowPosition - every second row has the boards rotated by 180 degrees
    OddEvenRowsColumnsPosition - every second row and column has the boards rotated by 180 degrees

netRenamePattern - the pattern according to which the net names are transformed
    The default pattern is "Board_{n}-{orig}" which gives each board its own instance of its nets, 
    i.e. GND becomes Board_0-GND for the first board , and Board_1-GND for the second board etc

refRenamePattern - the pattern according to which the reference designators are transformed
    The default pattern is "Board_{n}-{orig}" which gives each board its own instance of its reference designators,
    so R1 becomes Board_0-R1 for the first board, Board_1-R1 for the recond board etc. To keep references the
    same as in the original, set this to "{orig}"

tolerance - if no sourceArea is specified, the distance by which the selection 
    area for the board should extend outside the board edge.
    If you have any objects that are on or outside the board edge, make sure this is big enough to include them.
    Such objects often include zone outlines and connectors.
    
Returns a list of the placed substrates. You can use these to generate
tabs, frames, backbones, etc.

#### `makeLayersVisible`
```
makeLayersVisible(self)
```
Modify corresponding *.prl files so all the layers are visible by
default

#### `makeMouseBites`
```
makeMouseBites(self, cuts, diameter, spacing, offset=250000, prolongation=500000)
```
Take a list of cuts and perform mouse bites. The cuts can be prolonged
to

#### `makeRailsLr`
```
makeRailsLr(self, thickness)
```
Adds a rail to left and right.

#### `makeRailsTb`
```
makeRailsTb(self, thickness)
```
Adds a rail to top and bottom.

#### `makeTightFrame`
```
makeTightFrame(self, width, slotwidth, hspace, vspace)
```
Build a full frame with board perimeter milled out.
Add your boards to the panel first using appendBoard or makeGrid.

Parameters:

width - width of substrate around board outlines

slotwidth - width of milled-out perimeter around board outline

hspace - horizontal space between board outline and substrate

vspace - vertical space between board outline and substrate

#### `makeVCuts`
```
makeVCuts(self, cuts, boundCurves=False)
```
Take a list of lines to cut and performs V-CUTS. When boundCurves is
set, approximate curved cuts by a line from the first and last point.
Otherwise, raise an exception.

#### `mergeDrcRules`
```
mergeDrcRules(self)
```
Examine DRC rules of the source boards, merge them into a single set of
rules and store them in *.pro file

#### `panelBBox`
```
panelBBox(self)
```
Return bounding box of the panel as a shapely box.

#### `panelCorners`
```
panelCorners(self, horizontalOffset=0, verticalOffset=0)
```
Return the list of top-left, top-right, bottom-left and bottom-right
corners of the panel. You can specify offsets.

#### `renderBackbone`
```
renderBackbone(self, vthickness, hthickness, vcut, hcut)
```
Render horizontal and vertical backbone lines. If zero thickness is
specified, no backbone is rendered.

vcut, hcut specifies if vertical or horizontal backbones should be cut.

Return a list of cuts

#### `save`
```
save(self)
```
Saves the panel to a file and makes the requested changes to the prl and
pro files.

#### `setAuxiliaryOrigin`
```
setAuxiliaryOrigin(self, point)
```
Set the auxiliary origin used e.g., for drill files

#### `setCopperLayers`
```
setCopperLayers(self, count)
```
Sets the copper layer count of the panel

#### `setDesignSettings`
```
setDesignSettings(self, designSettings)
```
Set design settings

#### `setGridOrigin`
```
setGridOrigin(self, point)
```
Set grid origin

#### `setPageSize`
```
setPageSize(self, size)
```
Set page size - either a string name (e.g., A4) or size in KiCAD units

#### `setProperties`
```
setProperties(self, properties)
```
Set text properties cached in the board

#### `setTitleBlock`
```
setTitleBlock(self, titleBlock)
```
Set panel title block

#### `setVCutClearance`
```
setVCutClearance(self, clearance)
```
Set V-cut clearance

#### `setVCutLayer`
```
setVCutLayer(self, layer)
```
Set layer on which the V-Cuts will be rendered

#### `translate`
```
translate(self, vec)
```
Translates the whole panel by vec. Such a feature can be useful to
specify the panel placement in the sheet. When we translate panel as the
last operation, none of the operations have to be placement-aware.

## Substrate class

This class represents a pice of substrate (with no components). Basically it is
just a relatively thin wrapper around shapely polygons. On top of that, it keeps
a partition line for the substrate. Read more about partition lines in
[understanding tabs](understandingTabs.md).



#### `backToSource`
```
backToSource(self, point)
```
Return a point in the source form (if a reverse transformation was set)

#### `boundary`
```
boundary(self)
```
Return shapely geometry representing the outer ring

#### `boundingBox`
```
boundingBox(self)
```
Return bounding box as wxRect

#### `bounds`
```
bounds(self)
```
Return shapely bounds of substrates

#### `cut`
```
cut(self, piece)
```
Remove a piece of substrate given a shapely polygon.

#### `exterior`
```
exterior(self)
```
Return a geometry representing the substrate with no holes

#### `isSinglePiece`
```
isSinglePiece(self)
```
Decide whether the substrate consists of a single piece

#### `millFillets`
```
millFillets(self, millRadius)
```
Add fillets to inner conernes which will be produced a by mill with
given radius.

#### `orient`
```
orient(self)
```
Ensures that the substrate is oriented in a correct way.

#### `removeIslands`
```
removeIslands(self)
```
Removes all islads - pieces of substrate fully contained within outline
of another board

#### `serialize`
```
serialize(self)
```
Produces a list of PCB_SHAPE on the Edge.Cuts layer

#### `tab`
```
tab(self, origin, direction, width, partitionLine=None, maxHeight=50000000)
```
Create a tab for the substrate. The tab starts at the specified origin
(2D point) and tries to penetrate existing substrate in direction (a 2D
vector). The tab is constructed with given width. If the substrate is
not penetrated within maxHeight, exception is raised.

When partitionLine is specified, tha tab is extended to the opposite
side - limited by the partition line. Note that if tab cannot span
towards the partition line, then the the tab is not created - it returns
a tuple (None, None).

Returns a pair tab and cut outline. Add the tab it via union - batch
adding of geometry is more efficient.

#### `translate`
```
translate(self, vec)
```
Translate substrate by vec

#### `union`
```
union(self, other)
```
Appends a substrate, polygon or list of polygons. If there is a common
intersection, with existing substrate, it will be merged into a single
substrate.
