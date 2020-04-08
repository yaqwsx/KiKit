# KiKit CLI interface

KiKit offers a simple CLI interface to perform common tasks easily. You can
obtain a help of the interface by calling `kikit --help`.

The interface is structured into nested commands. On the top level, there are
the following commands available:

- **export**: Export KiCAD boards
- **panelize**: Create a simple predefined panel patterns
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
  board from `input` board file at rectangle specified by `sourceArea` (a tuple
  X, Y, width, height in millimeters separated by spaces) and place it in a
  single board file named `output`. Typical use case is to separated boards
  which were designed in a single file (to share schematics or to easily make
  them fit to each other) so you can export gerber files individually.
- `kikit panelize grid [options] <input> <output>` - create a panel of given
  board with `rows` x `cols` boards separated by tabs (just like in the [README
  example](resources/promo.jpg)). The following options are accepted:
  - `-s, --space FLOAT` Space between boards
  - `-g, --gridsize <INTEGER INTEGER>` Panel size `<rows> <cols>`
  - `-p, --panelsize <FLOAT FLOAT>` `<width> <height>` in millimeters
  - `--tabwidth FLOAT` Size of the bottom/up tabs, leave unset for full width
  - `--tabheight FLOAT` Size of the left/right tabs, leave unset for full height
  - `--vcuts BOOLEAN` Use V-cuts to separate the boards
  - `--mousebites <FLOAT FLOAT>` Use mouse bites to separate the boards. Specify
    drill size and spacing in millimeters.
  - `--radius FLOAT` Add a radius to inner corners (warning: slow)
  - `--sourcearea <FLOAT FLOAT FLOAT FLOAT>` `x y w h` in millimeters. If not
    specified, automatically detected

## Present commands

- `kikit present boardpage --name <pagename> -d <descriptionFile> -b <name
  comment boadfile> -r <resource> --template <template> --repository <url>
  <outputdir>` - generate single webpage providing board preview and a
  possibility to download board files (gerbers and sources). See [an example of
  such page](https://roboticsbrno.github.io/RB0002-BatteryPack).
    - The description is a path to markdown file with the main page content.
    - You can specify multiple resources via `-r` or `--resource`. Resources are
      files, which will be copied to the output directory. Useful for images
      referred from description
    - You can specify multiple boards via `-b` or `--board`
    - Template is an optional argument which is either a path to custom template
      or a name of built-in templates (currently only one is one - `default`).
      See [template documentation](present.md) for more information about
      templates.