# KiKit – Automation for KiCAD

![KiKit Logo](https://github.com/yaqwsx/KiKit/raw/master/kikit/resources/graphics/kikitIcon_64x64.png)

KiKit is a Python library, KiCAD plugin and  a CLI tool to automate several
tasks in a standard KiCAD workflow like:

- panelization of both, regular and oddly shaped, boards (see
  [examples](https://yaqwsx.github.io/KiKit/latest/panelization/examples/))
- automated exporting manufacturing data based on manufacturer presets
- multi-board project in KiCAD
- building board presentation pages (see [an example presentation page generated
  by KiKit](https://roboticsbrno.github.io/RB0002-BatteryPack))

![KiKit Promo](https://github.com/yaqwsx/KiKit/blob/master/docs/resources/promo.jpg?raw=true)

## Do You Enjoy KiKit or Does It Save You Time?

Then definitely consider:

- [**supporting me on GitHub Sponsors**](https://github.com/sponsors/yaqwsx)
- or become my [Patreon](https://patreon.com/yaqwsx),
- or buy me a coffee: [![ko-fi](https://www.ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/E1E2181LU)

Your support will allow me to allocate time to properly maintain my projects
like this.

PS: Be sure to check out my other KiCAD & PCB related projects:

- [Pinion](https://github.com/yaqwsx/Pinion/)
- [PcbDraw](https://github.com/yaqwsx/PcbDraw/)
- [JlcParts](https://github.com/yaqwsx/jlcparts)

## Installation

KiKit is available as a [PyPi package](https://pypi.org/project/KiKit/).
However, due to packaging of KiCAD, installation on some platforms requires
usage of specific Python interpreter.

Please follow the detailed [installation
guide](https://yaqwsx.github.io/KiKit/latest/installation/intro/) that covers
installation based on the platform you use.

## Why Should I Use It?

Everything KiKit does, can also be done via Pcbnew in KiCAD. However, you have
to do it manually. One of the common scenarios is the creation of panels. Most
of the tutorials on the internet guide you to use the "append board"
functionality of Pcbnew. However, this approach is labour-intensive, error-prone
and whenever, you change the board, you have to do it again.

With KiKit you just call a CLI command if you have a simple layout (e.g., a
grid) or write few Python instructions like "place board here", "add bridge
here", "separate boards via mouse bites/v-cuts" and you are done. The process is
repeatable and actually much simpler than hand-drawing the panels. KiKit also
allows you to easily export all the Gerbers in a single step.

You can then write a Makefile and simply call `make` to get all your
manufacturing data and board presentation pages.

## Feature List

- create panels by appending boards and pieces of substrate (bridges)
- supports board with arbitrary shapes
- easily create mouse-bites/V-CUTS
- compared to hand-creation of panels, your panels will pass DRC (as tracks from
  different instances of the same board have distinct nets when using KiKit)
- if you have multiple boards in a single file, you can split them
- simplifying [multi-board project in KiCAD](https://yaqwsx.github.io/KiKit/latest/multiboard/)
- [automated export of gerbers and assembly data](https://yaqwsx.github.io/KiKit/latest/fabrication/intro/)
- [3D printed self-registering solder paste stencils](https://yaqwsx.github.io/KiKit/upstream/latest/stencil/#3d-printed-stencils)
- [steel stencils with alignment jig](https://yaqwsx.github.io/KiKit/latest/stencil/#steel-stencils)
- create powerfull shell scrips or Makefiles which automates your workflow...
- ...or invoke the functionality via [GUI in KiCAD](https://yaqwsx.github.io/KiKit/latest/panelization/gui/).

## How To Use It?

Start with reading the [panelization
documentation](https://yaqwsx.github.io/KiKit/latest/panelization/intro/). This
page will you guide through CLI, GUI and scripting usage. Also don't miss the
[examples](https://yaqwsx.github.io/KiKit/latest/panelization/examples/).
There is also a quick not on how to use [panelization action
plugin](https://yaqwsx.github.io/KiKit/latest/panelization/gui/). If you are
interested in generating solder paste stencils, see [Stencil
documentation](https://yaqwsx.github.io/KiKit/latest/stencil/)

## Acknowledgements

The project is supported by:

- [My GitHub sponsors](https://github.com/sponsors/yaqwsx) and
- [<img src="https://nlnet.nl/logo/banner.svg" width="150"/>](https://nlnet.nl/project/KiKit/#ack)

## KiKit Is Broken or Does Not Work as Expected

Please, first check [FAQ](https://yaqwsx.github.io/KiKit/latest/faq/). If you have not found answer for your
problem there, feel free to open an issue on GitHub.

If you would like to have a feature in KiKit that is currently not on a roadmap,
or if you need to prepare custom panelization script (e.g., multi-design panels,
panels with specific arrangement), you can consider hiring me to do the job.
Just reach out to me via e-mail and we can discuss further details.
