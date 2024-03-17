# Panelization CLI

The whole panelization process of KiKit's CLI is driven by a configuration
structure. The configuration contains several categories (e.g., `layout`,
`tabs`, `framing`). Each of the categories have number of named parameters
(e.g., `tabsCount`). All categories and their parameters are described further
below.

Note that you can use the [pcbnew action plugin](gui.md) to
interactively construct the panelization configuration structure.

## Configurations

The configuration can be supplied to KiKit via a JSON file with comments and
from the command line. The example of a configuration in a JSON file is the
following

```.js
{
    // There can be C-like comments
    "layout": {
        "type": "grid",
        "rows": 1,
        "cols": 1,
        "hspace": "0mm",
        "vspace": "0mm",
        "rotation": "0deg",
        "alternation": "none",
        "renamenet": "Board_{n}-{orig}",
        "renameref": "{orig}"
    },
    "source": {
        "type": "auto",
        "tolerance": "1mm"
    },
    "tabs": {
        "type": "normal",
        "source": "none"
    },
    "cuts": {
        "type": "none"
    },
    "framing": {
        "type": "none",
        "thickness": "0mm",
    },
    "post": {
        "type": "auto",
        "millradius": "0mm",
        "copperfill": false
    }
}
```

KiKit accepts `-p <configurationFile>` option to specify one or more
configurations. When multiple configurations are specified, they are composed
into a single configuration. The later specified configurations overwrite
parameters of the former specified configurations. This allows us to start with
a basic configuration and have a number of small configurations specifying
details.

To give and example, consider the two following configurations:

```.js
// A
{
    "tabs": {
        "type": "normal",
        "width": "3mm"
    },
    "framing": {
        "type": "frame"
    }
}

// B
{
    "framing": {
        "type": "rails"
        "width": "5mm"
    }
}
```

When we merge `B` into `A`, we get:

```.js
{
    "tabs": {
        "type": "normal",
        "width": "3mm"
    },
    "framing": {
        "type": "rails"
        "width": "5mm"
    }
}
```

You can also override every parameter from CLI. There is an option for each
category, which accepts a semicolon-separated list of key-value pairs; e.g.:

```
--layout 'rows: 3; cols: 4'
```

The options from CLI have the highest priority - they override values from
specified from the files. If you need to specify the character `;`, you can
escape it via `\`.

Therefore, a full invocation of KiKit for panelization can look like this:
```
kikit panelize -p myDefault.json -p useVcuts.json -p myFrame.json
    --layout 'rows: 3; cols: 4'
    board.kicad_pcb panel.kicad_pcb.
```

Note the single quotes -- without them your shell will eat the spaces and the
command will be interpreted badly. The command will use our default
configuration, then it will override some options to use V-cuts and then it adds
a frame specified by `myFrame.json`. Last we specify the panel size from CLI.

Note that KiKit always start with a default configuration (specified in the file
[default.json](https://github.com/yaqwsx/KiKit/blob/master/kikit/resources/panelizePresets/default.json)).
There are also some configuration files shipped with KiKit. You can find them in
the directory `kikit/resources/panelizePresets`. When you want to use them via
option `-p`, just prefix their name with `:` and drop the suffix. E.g., for
`vcuts.json` use `-p :vcuts`.

If you would like to inspect which configuration was used by KiKit, you can dump
it into a file with the `-d <filename>` option.

## Units

You can specify units in the configuration files and CLI. Always specify them as
string, e.g., "2mm" or "0.5 inch" (do not forget the quotes in the JSON files).

Supported length units: mm, cm, dm, m, mil, inch, in.

Supported angle units: deg, °, rad.

## Configuration categories

There are the following categories: layout, source, tabs, cuts, framing, and
tooling.

Each category has a mandatory parameter `type` which dictates the style of that
feature. Note that you can specify the type parameter in a simplified manner in
the CLI by specifying it first and omitting the `type` word; e.g., `--cuts
'mousebites, someParameter: 10cm'`.

### Layout

**Types**: grid, plugin

**Common options**:

- `hspace`, `vspace`, `space`: Specify the gap between the boards. You can
  specify separately vertical and horizontal spacing or you can specify `space`
  to make them the same (it has higher priority).
- `rotation`: Rotate the boards before placing them in the panel
- `renamenet`, `renameref`: A pattern by which to rename the nets and
  references. You can use `{n}` and `{orig}` to get the board number and
  original name. Default values are `Board_{n}-{orig}` for nets and `{orig}` for
  references.
- `baketext`: A flag that indicates if text variables should be substituted or
  not.

#### Grid

The boars are placed in a grid pattern connected by tabs. There are no special
options.

- `rows`, `cols`: Specify the number of boards in the grid pattern
- `alternation`: Specify alternations of board rotation.
    - `none`: Do not alternate
    - `rows`: Rotate boards by 180° on every next row
    - `cols`: Rotate boards by 180° on every next column
    - `rowsCols`: Rotate boards by 180° based on a chessboard pattern
- `vbackbone`, `hbackbone`: The width of vertical and horizontal backbone (0
  means no backbone). The backbone does not increase the spacing of the boards.
- `vboneskip`, `hboneskip`: Skip every n backbones. I.e., 1 means place only
  every other backbone.
- `vbonefirst`, `hbonefirst`: Specify first backbone to render. Allows to
  specify the offset when skipping backbones. The offset is indexed from 1.
- `vbonecut`, `hbonecut`: true/false. If there are both backbones specified,
  specifies if there should be a vertical or horizontal cut (or both) where the
  backbones cross.

#### Plugin

Implements a custom layout based on a plugin.

- `code`: the plugin specification. See (plugin documentation)[plugin.md] for
  more details
- `arg`: text argument for the user plugin

### Source

This option allows you to specify the source area, e.g., when multiple boards
are present. You can read more about multi-board project [here](../multiboard.md).

**Types**: auto, rectangle, annotation

**Common options**:

- `stack`: specify the number of layers of the panel. Valid options are
  `2layer`, `4layer`, `6layer` or `inehrit` (default). The use case for this
  option is when you design a multiple boards in a single desing and you
  separate them, however, one boards is e.g., 4 layer and one 2 layer. Then you
  design both of them as 4 layer and you specify `stack: 2layer` for the 2 layer
  one when panelizing or separating.

#### Auto

Find all board edges and use them to construct source rectangle. Suitable for
most cases when there is only a single board in the design. Note that might want
to increase `tolerance` or specify the source area explicitly via `rectangle` if
you have components sticking out of your design.

- `tolerance`: KiKit extracts only board items that fit fully into the source
  area (including all drawings on all layers). Tolerance enlarges the source
  area by given amount, to e.g., not omit KiKit annotations for tabs or
  connectors sticking out of the board.

#### Rectangle

Specify the source rectangle explicitly.

- `tlx, tly, brx, bry`: specify the coordinates (via length units) of the
  rectangle via top-left and bottom-right corner.

#### Annotation

KiKit offers you to place an annotation footprint `kikit:Board` into your design
file to name the board. The area is determined by a bounding box of the lines in
the `Edge.Cuts` layer that the arrows point to. Note that the tip of the arrow
must lie on the PCB edge or slightly outside of it.

- `ref`: specify the annotation symbol reference
- `tolerance`: see above

### Tabs

**Types**: fixed, spacing, full, annotation, plugin

Place tabs. To make some of the options clear, please see the [explanation of
tab placement process](tabs.md).

#### Fixed

Place given number of tabs on the PCB edge. The tabs are spaced uniformly. If
you need a custom tab placement (e.g., to avoid critical feature), see type
*annotation*.

- `vwidth`, `hwidth`, `width`: The width of tabs in the vertical and horizontal
  direction. `width` overrides both.
- `vcount`, `hcount`: Number of tabs in a given direction.
- `mindistance`: Minimal spacing between the tabs. If there are too many tabs,
  their count is reduced.

#### Spacing

Place tabs on the PCB edges based on spacing.

- `vwidth`, `hwidth`, `width`: The width of tabs in the vertical and horizontal
  direction. `width` overrides both.
- `spacing`: The maximum spacing of the tabs.

#### Full

Create tabs that are full width of the PCB. Suitable for PCBs separated by
V-Cuts. This mode does not make much sense for mousebites in practice. Note that
in this mode the cuts do not faithfully copy the PCB outline and, instead, they
cut the bounding box of the PCB. There are no other options.

- `cutout`: When your design features open pockets on the side, this parameter
  specifies extra cutout depth in order to ensure that a sharp corner of the
  pocket can be milled. The default is 1 mm.
- `patchcorners`: The full tabs are appended to the nearest flat face of the
  PCB. If the PCB has sharp corners, you want to add patches of substrate to
  these corners. However, if the PCB has fillet or miter, you don't want to
  apply the patches.

#### Corner

Create tabs in the corners of the PCB.

- `width`: The width of tabs

#### Annotation

Add tabs based on PCB annotations. Place a footprint `kikit:Tab` at the edges of
your PCB. You can edit the text field prefixed with `KIKIT: ` to adjust the tab
parameters. If you want to specify a custom tab symbol (e.g., with predefined)
width, you can specify `tabfootprints` as a list of footprints separated by
comma. For example: `myLib:Tab2mm, myLib:Tab3mm`.

The individual tabs can have the following properties specified in the text
field of the component as `KIKIT:<propertyname>`:

- `width`: width of the tab.

#### Plugin

Tabs based on a plugin.

- `code`: the plugin specification. See (plugin documentation)[plugin.md] for
  more details
- `arg`: text argument for the user plugin


### Cuts

Specify how to perform the cuts on the tabs separating the board.

**Types**: none, mousebites, vcuts, layer, plugin

#### None

Do not perform any cuts

#### Mousebites

Use mousebites to

- `drill` - specify drill size for the bites
- `spacing` - specify the spacing of the holes
- `offset` - specify the offset, positive offset puts the cuts into the board,
  negative puts the cuts into the tabs
- `prolong` - distance for tangential prolongation of the cuts (to cut through
  the internal corner fillets caused by milling)

#### V-Cuts

- `clearance` - specify clearance for copper around V-cuts
- `cutcurves` - true/false - specify if curves should be approximated by
  straight cuts (e.g., for cutting tabs on circular boards)
- `offset` - specify the offset, positive offset puts the cuts into the board,
  negative puts the cuts into the tabs
- `layer` - specify the layer to render V-cuts on.
- `linewidth` - specify linewidth
- `endprolongation` - prolongation of the cut line from the board line on the
  side without text.
- `textprolongation` - the same as above, just on the text side
- `textoffset` - offset of the text from the cut line
- `template` - a string template for text to render. Can contain variables
  listed below, e.g., `V-CUT {pos_mm}`.
    - `pos_mm`, `pos_inch` – position of the V-cut from the panel origin
    - `pos_inv_mm`, `pos_inv_inch` – inverted position of the V-cut from the panel origin

#### Layer

When KiKit reports it cannot perform cuts, you can render the cuts into a layer
with this option to understand what's going on. Shouldn't be used for the final
design.

- `layer` - specify the layer to render the cuts on.
- `prolong` - distance for tangential prolongation of the cuts. It has the same
  meaning as mousebites.
- `linewidth` - width of line to render

#### Plugin

Cuts based on a plugin.

- `code`: the plugin specification. See (plugin documentation)[plugin.md] for
  more details
- `arg`: text argument for the user plugin


### Framing

KiKit allows you to frame the panel with a full frame, or bottom/top or
left/right rails.

**Types**: none, railstb, railslr, frame, tightframe, plugin
**Common options**:

- `hspace`, `vspace`, `space` - specify the space between PCB and the
  frame/rail. `space` overrides `hspace and vspace`.
- `width` - specify with of the rails or frame
- `fillet`, `chamfer` - fillet/chamfer frame corners. Specify radius or chamfer
  size. You can also separately specify `chamferwidth` and `chamferheight` to
  create a non 45° chamfer.
- `mintotalheight`, `mintotalwidth` – if needed, add extra material to the rail
  or frame to meet the minimal requested size. Useful for services that require
  minimal panel size.

#### Railstb/Railslr

Add rail (either on top and bottom or on left and right) to the panel.

#### Frame

Add a frame around the board.

- `cuts` - one of `none`, `both`, `v`, `h` - specify whether to add cuts to the
  corners of the frame for easy removal. Default `both`.

#### Tighframe

Add a frame around the board which fills the whole area of the panel - the
boards have just a milled slot around their perimeter.

- `slotwidth` - width of the milled slot.

#### Plugin

Frame based on a plugin.

- `code`: the plugin specification. See (plugin documentation)[plugin.md] for
  more details
- `arg`: text argument for the user plugin

### Tooling

Add tooling holes to the (rail/frame of) the panel. The holes are positioned
by

**Types**: none, 3hole, 4hole, plugin

**Common options**:

- `hoffset`, `voffset` - specify the offset from from panel edges
- `size` - diameter of the holes
- `paste` - if true, the holes are included in the paste layer (therefore they
  appear on the stencil).
- `solderMaskMargin` - diameter of solder mask (optional)

#### Plugin

Tooling based on a plugin.

- `code`: the plugin specification. See (plugin documentation)[plugin.md] for
  more details
- `arg`: text argument for the user plugin

### Fiducials

Add fiducial to the (rail/frame of) the panel.

**Types**: none, 3fid, 4fid, plugin

**Common options**:

- `hoffset`, `voffset` - specify the offset from from panel edges
- `coppersize`, `opening` - diameter of the copper spot and solder mask opening
- `paste` - if true, the fiducials are included in the paste layer (therefore they
  appear on the stencil).

#### Plugin

Fiducials based on a plugin.

- `code`: the plugin specification. See (plugin documentation)[plugin.md] for
  more details
- `arg`: text argument for the user plugin

### Text

Add text to the panel. Allows you to put a single block of text on panel. You
can use variables enclosed in `{}`. E.g. `{boardTitle} | {boardDate}`. The list
of all available variables in listed bellow. You can also use the variables
specified in the project. They are prefixed with `user-`. That is, to include
your variable `revision` in KiKit text, use formatting string `Rev:
{user-revision}`. In the case you need more independent texts on the panel, you
can use sections names `text2`, `text3` and `text3` to add at most 4 text. All
these sections behave the same and accept the same options.

If you need more texts or more sophisticated placing options, see `script`
option from `postprocess`.

**Types**: none, simple

**Common options**:

- `text` - The text to be displayed. Note that you can escape `;` via `\`
- `anchor` - Origin of the text. Can be one of `tl`, `tr`, `bl`, `br` (corners),
  `mt`, `mb`, `ml`, `mr` (middle of sides), `c` (center). The anchors refer to
  the panel outline. Default `mt`
- `hoffset`, `voffset` - specify the offset from anchor. Respects KiCAD
  coordinate system. Default `0mm`.
- `orientation` - specify the orientation (angle). Default `0deg`
- `width`, `height` - width and height of the characters (the same parameters as
  KiCAD uses). Default `1.5mm`.
- `hjustify` - justification of the text. One of `left`, `right`, `center`.
  Default `center`.
- `vjustify` - justification of the text. One of `top`, `bottom`, `center`.
  Default `center`
- `thickness` - stroke thickness. Default `0.3mm`.
- `layer` - specify text layer
- `plugin` - specify the plugin that provides extra variables for the text

#### Available variables in text

- `date` - formats current date as `<year>-<month>-<day>`
- `time24` - formats current time in 24-hour format
- `year`, `month`, `day`, `hour`, `minute`, `second` - individual variables
  for any date format
- `boardTitle` - the title from the source board
- `boardDate` - the date from the source board
- `boardRevision` - the revision from the source board
- `boardCompany` - the company from the source board
- `boardComment1`-`boardComment9` - comments from the source board

You can get extra variables by providing custom [text plugin](plugins.md) via
the `plugin` field.

### Page

Sets page size on the resulting panel and position the panel in the page. The
type of style dictates paper size. The default `inherit` option inherits paper
size from the source board. This feature is not supported on KiCAD 5

**Types**: `inherit`, `custom`, `A0`, `A1`, `A2`, `A3`, `A4`, `A5`, `A`, `B`,
`C`, `D`, `E`, `USLetter`, `USLegal`, `USLedger`, `A0-portrait`, `A1-portrait`,
`A2-portrait`, `A3-portrait`, `A4-portrait`, `A5-portrait`, `A-portrait`,
`B-portrait`, `C-portrait`, `D-portrait`, `E-portrait`, `USLetter-portrait`,
`USLegal-portrait`, `USLedger-portrait`

**Common options**:

- `anchor` - Point of the panel to be placed at given position. Can be one of
  `tl`, `tr`, `bl`, `br` (corners), `mt`, `mb`, `ml`, `mr` (middle of sides),
  `c` (center). The anchors refer to the panel outline. Default `mt`
- `posx`, `posy` - the position of the panel on the page. Default `50%` for
  `posx` and `20mm` for `posy`.

#### Custom

Instead of the pre-defined paper size you can also specify a custom paper size
via `width` and `height`.

### Copperfill

Fill non-board areas of the panel with copper.

**Types**: none, solid, hatched, hex

**Common options**:

- `clearance` - optional extra clearance from the board perimeters. Suitable
  for, e.g., not filling the tabs with copper.
- `edgeclearance` - specifies clearance between the fill and panel perimeter.
- `layers` - comma-separated list of layer to fill. Default top and bottom. You
  can specify a shortcut `all` to fill all layers.

#### Solid

Fill with solid copper.

#### Hatched

Use hatch pattern for the fill.

- `width` - the width of the strokes
- `spacing` - the space between the strokes
- `orientation` - the orientation of the strokes

#### Hex

Use hexagon pattern for the fill.

- `diameter` – diameter of the hexagons
- `spacing` – space between the hexagons
- `threshold` – a percentage value that will discard fragments smaller than
  given threshold

### Post

Finishing touches to the panel.

**Types**: auto

**Common options**:

- `copperfill` - fill tabs and frame with copper (e.g., to save etchant or to
  increase rigidity of flex-PCB panels)
- `millradius` - simulate the milling operation (add fillets to the internal
  corners). Specify mill radius (usually 1 mm). 0 radius disables the
  functionality.
- `millradiusouter` ­– same as the previous one, modifies only board outer
  counter. No internal features of the board are affected.
- `reconstructarcs` - the panelization process works on top of a polygonal
  representation of the board. This options allows to reconstruct the arcs in
  the design before saving the panel.
- `refillzones` – refill the user zones after the panel is build. This is only
  necessary when you want your zones to avoid cuts in panel.
- `script` - a path to custom Python file. The file should contain a function
  `kikitPostprocess(panel, args)` that receives the prepared panel as the
  `kikit.panelize.Panel` object and the user-supplied arguments as a string -
  see `scriptarg`. The function can make arbitrary changes to the panel - you
  can append text, footprints, alter labels, etc. The function is invoked after
  the whole panel is constructed (including all other postprocessing). **If you
  try to add a functionality for a common fabrication houses via scripting,
  consider submitting PR for KiKit**.
- `scriptarg`: An arbitrary string passed to the user post-processing script
  specified in `script`
- `origin` - specify if the auxilary origin an grid origin should be placed. Can
  be one of `tl`, `tr`, `bl`, `br` (corners), `mt`, `mb`, `ml`, `mr` (middle of
  sides), `c` (center). Empty string does not changes the origin.
- `dimensions` - `true` or `false`. Draw dimensions with the panel size.
- `edgewidth` ­– width of the line for panel edges (that is the lines in the
  `Edge.Cuts` layer).


