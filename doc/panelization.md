
# Panelization

When you want to panelize a board, you are expected to load the `kikit.panelize`
module and create an instance of the `Panel` class.

All units are in the internal KiCAD units (1 nm). You can use functions `fromMm(mm)` and
`toMm(kiUnits)` to convert to/from them (synopsis below). You are also encouraged to use
the functions and objects the native KiCAD Python API offers, e.g.: `wxPoint(args)`, `wxPointMM(mmx, mmy)`, `wxRect(args)`, `wxRectMM(x, y, wx, wy)`.



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

## Source Area And Tolerance

When placing a board, you might specify source area -- a rectangle from which
the components are extracted. If no source area is specified, the smallest
bounding box of all Edge.Cuts is taken.

Only components that fully fit inside source area are copied to the panel. To
include components sticking out of the board outline, you can specify tolerance
-- a distance by which the source area is expanded when copying components.


## Panel class

Basic interface for panel building. Instance of this class represents a
single panel. You can append boards, add substrate pieces, make cuts or add
holes to the panel. Once you finish, you have to save the panel to a file.
```
appendBoard(self, filename, destination, sourceArea=None, origin=Origin.Center, 
            rotationAngle=0, shrink=False, tolerance=0, bufferOutline=1000, 
            netRenamer=None, refRenamer=None)
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
filled zones which can reach out of the board edges.

You can also specify functions which will rename the net and ref names.
By default, nets are renamed to "Board_{n}-{orig}", refs are unchanged.
The renamers are given board seq number and original name

Returns bounding box (wxRect) of the extracted area placed at the
destination.
```
save(self, filename)
```
Saves the panel to a file.
```
appendSubstrate(self, substrate)
```
Append a piece of substrate or a list of pieces to the panel. Substrate
can be either wxRect or Shapely polygon. Newly appended corners can be
rounded by specifying non-zero filletRadius.
```
makeGrid(self, boardfile, rows, cols, destination, sourceArea=None, tolerance=0, 
         verSpace=0, horSpace=0, verTabCount=1, horTabCount=1, verTabWidth=0, 
         horTabWidth=0, outerVerTabThickness=0, outerHorTabThickness=0, 
         rotation=0, netRenamePattern=Board_{n}-{orig}, 
         refRenamePattern=Board_{n}-{orig})
```
Creates a grid of boards (row x col) as a panel at given destination
separated by V-CUTS. The source can be either extracted automatically or
from given sourceArea. There can be a spacing between the individual
board (verSpacing, horSpacing) and the tab width can be adjusted
(verTabWidth, horTabWidth). Also, the user can control whether to append
the outer tabs (e.g. to connect it to a frame) by setting
outerVerTabsWidth and outerHorTabsWidth.

Returns a tuple - wxRect with the panel bounding box (excluding
outerTabs) and a list of cuts (list of lines) to make. You can use the
list to either create a V-CUTS via makeVCuts or mouse bites via
makeMouseBites.
```
makeTightGrid(self, boardfile, rows, cols, destination, verSpace, horSpace, 
              slotWidth, width, height, sourceArea=None, tolerance=0, 
              verTabWidth=0, horTabWidth=0, verTabCount=1, horTabCount=1, 
              rotation=0, netRenamePattern=Board_{n}-{orig}, 
              refRenamePattern=Board_{n}-{orig})
```
Creates a grid of boards just like `makeGrid`, however, it creates a
milled slot around perimeter of each board and 4 tabs.
```
makeFrame(self, innerArea, width, height, offset)
```
Adds a frame around given `innerArea` (`wxRect`), which can be obtained,
e.g., by `makeGrid`, with given `width` and `height`. Space with width
`offset` is added around the `innerArea`.
```
makeVCuts(self, cuts, boundCurves=False)
```
Take a list of lines to cut and performs V-CUTS. When boundCurves is
set, approximate curved cuts by a line from the first and last point.
Otherwise, raise an exception.
```
makeMouseBites(self, cuts, diameter, spacing, offset=250000)
```
Take a list of cuts and perform mouse bites.
```
addNPTHole(self, position, diameter)
```
Add a drilled non-plated hole to the position (`wxPoint`) with given
diameter.
```
addFiducial(self, position, copperDiameter, openingDiameter, bottom=False)
```
Add fiducial, i.e round copper pad with solder mask opening to the position (`wxPoint`),
with given copperDiameter and openingDiameter. By setting bottom to True, the fiducial
is placed on bottom side.

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

