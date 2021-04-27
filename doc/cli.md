# KiKit CLI interface

KiKit offers a simple CLI interface to perform common tasks easily. You can
obtain help of the interface by calling `kikit --help`.

The interface is structured into nested commands. On the top level, there are
the following commands available:

- ***drc***: Validate design rules of the board
- ***export***: Export KiCAD boards
- ***fab***: Export complete manufacturing data for given fabrication houses
- ***modify***: Modify board items
- ***panelize***: Panelize boards
- ***present***: Prepare board presentation
- ***separate***: Separate a single board out of a multi-board design.
- ***stencil***: Create solder paste stencils


## Export commands

- `kikit export gerber <boardFile> [<outputDir>]` - export gerber files of
  `boardFile` to `outputDir`. If no dir is specified, a new one
  `<boardFile>-gerbers` is created.
- `kikit export dxf <boardFile> [<outputDir>]` - export board outline and paste
  layers to DXF. The main use case for this command is making [3D printed solder
  paste
  stencils](https://blog.honzamrazek.cz/2020/01/printing-solder-paste-stencils-on-an-sla-printer/).

## Panelize commands

Read more in a separate [documentation section](panelizeCli.md) or see a
[walkthrough](examples.md).

## Separate commands

Read more in a separate [documentation section](multiboard.md).

## Stencil commands

Read more in a separate [documentation section](stencil.md).

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