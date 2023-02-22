# Installation on Linux

KiKit is distributed as [PyPi package](https://pypi.org/project/KiKit/).

## Instalation for KiCAD installed via system package manager

The installation consists of a single command you have to enter into the
terminal. If you installed KiCAD via package manager (apt, yum, etc.) you can
use a regular terminal and enter `pip3 install kikit`. Now you are ready to use
KiKit.

## Installation for Flatpak KiCAD

However, if you installed KiCAD via Flatpak, you have to open a special terminal
as Flatpak sandboxes the applications. Open terminal and invoke `flatpak run
--command=sh org.kicad.KiCad`, this will open a terminal session inside the
KiCAD’s sandbox. Now you can install pip via `python3 -m ensurepip` and then,
inside the same terminal you can install KiKit: `python3 -m pip install kikit`.
If you would like to use CLI interface, all commands have to be invoked inside
the shell `flatpak run --command=sh org.kicad.KiCad`, and, instead of `kikit
something` you have to use `python -m kikit.ui something`.

## Testing the installation

Now you can test that it works:

```
> kikit --help
```

You should get something like this:

```
Usage: kikit [OPTIONS] COMMAND [ARGS]...

Options:
  --version  Show the version and exit.
  --help     Show this message and exit.

Commands:
  drc       Validate design rules of the board
  export    Export KiCAD boards
  fab       Export complete manufacturing data for given fabrication houses
  modify    Modify board items
  panelize  Panelize boards
  present   Prepare board presentation
  separate  Separate a single board out of a multi-board design.
  stencil   Create solder paste stencils
```

Now you are done with the basic installation. If you plan to use graphical
interface, install [GUI frontend and libraries via PCM](gui_and_libs.md).
