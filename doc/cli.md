# KiKit CLI interface

KiKit offers a simple CLI interface to perform common tasks easily. You can
obtain help of the interface by calling `kikit --help`.

The interface is structured into nested commands. On the top level, there are
the following commands available:

- **export**: Export KiCAD boards
- **panelize**: Create simple predefined panel patterns
- **present**: Create presentations - e.g. web page with auto-generated files

## Export commands

- `kikit export gerber <boardFile> [<outputDir>]` - export gerber files of
  `boardFile` to `outputDir`. If no dir is specified, a new one
  `<boardFile>-gerbers` is created.
- `kikit export dxf <boardFile> [<outputDir>]` - export board outline and paste
  layers to DXF. The main use case for this command is making [3D printed solder
  paste
  stencils](https://blog.honzamrazek.cz/2020/01/printing-solder-paste-stencils-on-an-sla-printer/).

## Panelize commands

- `kikit panelize extractboard -s <sourceArea> <input> <output>` - extract a
  board from `input` board file at a rectangle specified by `sourceArea` (a tuple
  X, Y, width, height in millimeters separated by spaces) and place it in a
  single board file named `output`. Typical use case is to separate boards
  which were designed in a single file (to share schematics or to easily make
  them fit to each other) so you can export gerber files individually.
- `kikit panelize grid [options] <input> <output>` - create a panel of a given
  board with `rows` x `cols` boards separated by tabs (just like in the [README
  example](resources/promo.jpg)). The following options are accepted:
  - `-s, --space FLOAT` Space between boards. Note that if you prefer, you can
    specify the verctical and horizontal spacing independently by the `--hspace`
    and `--vspace` options.
  - `-g, --gridsize <INTEGER INTEGER>` Panel size `<rows> <cols>`
  - `-p, --panelsize <FLOAT FLOAT>` `<width> <height>` in millimeters
  - `-a, --alternation <NAME>` allows you to specify board orientation
    alternation. There are possible options:
    - `none` - do not rotate the boards
    - `rows` - rotate boards in even rows by 180°
    - `cols` - rotate boards in even columns by 180°
    - `rowsCols` - rotate boards on the black fields of a chessboard by by 180°
  - `--tabwidth FLOAT` Size of the bottom/up tabs, leave unset for full width
  - `--tabheight FLOAT` Size of the left/right tabs, leave unset for full height
  - `--htabs INT` Number of horizontal tabs per board
  - `--vtabs INT` Number of vertical tabs per board
  - `--vcuts BOOLEAN` Use V-cuts to separate the boards
  - `--vcutlayer <layer>` Name of the layer where V-cuts should be added
  - `--mousebites <FLOAT FLOAT FLOAT>` Use mouse bites to separate the boards.
    Specify drill size, spacing and offset in millimeters. If you are unsure
    about the offset value, use 0.25 mm
  - `--radius FLOAT` Add a radius to inner corners to simulate radius of the
    mill
  - `--sourcearea <FLOAT FLOAT FLOAT FLOAT>` `x y w h` in millimeters. A
    rectangle specified by a top left corner and its width and height. If not
    specified, automatically detected.
  - `--rotation <FLOAT>` Rotate the source board in degrees.
  - `--tolerance <FLOAT>` Distance in millimeters by which the source area is
    expanded when copying board items. See more details in [panelization
    doc](panelization.md).
  - `--renamenet <string>`, `--renameref <string>` Rename pattern for nets and
    references. String can contain `{n}` for the current board sequence number
    and `{orig}` original name of net/reference. If not specified, nets are
    renamed to `Board_{n}-{orig}`, references are unchanged.
  - `--copperfill` Fill the unused areas of the panel (frame, rails, tabs) with
    copper. Reduces amount of etching and makes flex PCBs stiffer.
- `kikit panelize tightgrid [options] <input> <output>` - create a panel just
  like `grid`, but the panel is full and there is a milled slot around the
  perimeter of the boards. Takes the same arguments as `grid` with few
  exceptions:
  - `-w, --slotwidth <FLOAT>` specify the slot size
  - `-p, --panelsize <FLOAT FLOAT>` `<width> <height>` in millimeters, required.


## Present commands

- `kikit present boardpage --name <pagename> -d <descriptionFile> -b <name
  comment boadfile> -r <resource> --template <template> --repository <url>
  <outputdir>` - generate single webpage providing board preview and a
  possibility to download board files (gerbers and sources). See [an example of
  such page](https://roboticsbrno.github.io/RB0002-BatteryPack).
    - The description is a path to a markdown file with the main page content.
    - You can specify multiple resources via `-r` or `--resource`. Resources are
      files which will be copied to the output directory. Useful for images
      referred from description
    - You can specify multiple boards via `-b` or `--board`
    - Template is an optional argument which is either a path to a custom template
      or a name of built-in templates (currently, there is only one: `default`).
      See [template documentation](present.md) for more information about
      templates.

## Modify commands

- `kikit modify references --show/--hide --pattern <pattern> <board>` hide or
  show all references on the board matching a regular pattern.