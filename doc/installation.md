# Installation

KiKit is distributed as a Python package. If you installed it via KiCAD's Plugin
and Content Manager (PCM), you still have to install it via the procedures below
as the PCM only distributes the graphical interface (note that as of KiCAD 6 it
is impossible to distribute KiKit completely via PCM).

The installation steps differ slightly based on the operating system you use, but
consists of three steps:

- perform the basic installation:
  - [Linux/MacOS](#installation-on-linux-and-macos)
  - [Windows](#installation-on-windows)
  - Or you can run KiKit inside [Docker](#running-kikit-via-docker) - which
    might be useful e.g., for continuous integration.
  - If you would like to install special version of KiKit (e.g., nightly or a
    specific feature under development), please follow
    [Installing a special version of KiKit](#installing-a-special-version-of-kikit).
- register the GUI plugins and library:
  - either install KiKit from PCM,
  - or download KiKit packages and install them manually:
    - [KiKit](https://nightly.link/yaqwsx/KiKit/workflows/test-kikit/master/kikit-pcm.zip)
    - [KiKit Libraries](https://nightly.link/yaqwsx/KiKit/workflows/test-kikit/master/kikit-lib-pcm.zip)
  - or [register the plugins](#enabling-plugins) and [libraries
    manually](#enabling-kikit-annotation-footprint-library).
- Optionally, you can install the [optional
  dependencies](#optional-dependencies) required for certain functions.

## Installation on Linux and MacOS

Simply invoke in terminal:

```
> pip install kikit
# or  (based on your distribution)
> pip3 install kikit
```

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

Now you are done with the basic installation. Don't forget to get the GUI
frontend and libraries via PCM.

This is the basic installation for CLI usage. If you would like to use the
graphical interface inside KiCAD, you have to install the graphical interface
via Plugin and Content Manager or [register the plugins](#enabling-plugins) and
[libraries manually](#enabling-kikit-annotation-footprint-library). You might
also want to consider installing the [optional
dependencies](#optional-dependencies).

## Installation on Windows

To install KiKit on Windows, you have to open "KiCAD Command Prompt". You can
find it in the start menu:

![KiCAD Command Prompt in Start menu](resources/windowsCommandPrompt1.jpg)

Once you have it open like this:

![KiCAD Command Prompt in Start menu](resources/windowsCommandPrompt2.jpg)

you can put command in there and confirm them by pressing
enter. This is also the prompt from which you will invoke all KiKit's CLI
commands. They, unfortunatelly, does not work in an ordinary Command prompt due
to the way KiCAD is packaged on Windows.

Then you have to enter two commands:

- `pip install git+https://github.com/SolidCode/SolidPython.git@master` (the
  older version of this library is currently incomptible with Windows, hence this extra step)
- `pip install kikit` (install KiKit itself)

Now you can test that it works:

```.bash
kikit --help
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

Now you are done with the basic installation. Don't forget to get the GUI
frontend and libraries via PCM.

## Installing a special version of KiKit

If you would like to install a specific version of KiKit, you can install it
directly from git. The command for that is:

```.bash
# The master branch - the most up-to-date KiKit there is (but might me unstable)
pip install git+https://github.com/yaqwsx/KiKit@master
# A concrete branch, e.g., from a pull request
pip3 install git+https://github.com/yaqwsx/KiKit@someBranchName
```

## Optional dependencies

- [PcbDraw](https://github.com/yaqwsx/PcbDraw) - to be able to export
  presentation pages
- [OpenSCAD](https://openscad.org/) - to be able to export 3D models of stencil.
  Install it via your system package manage.

## Enabling KiKit annotation footprint library

KiKit distributes a footprint library called `kikit`. This library contains
footprints that can be used for annotation of the PCB (e.g., mark tab
locations). To use it, you have to add it into KiCAD.

You can:
- register the library automatically via invoking `kikit-plugin registerlib` of
- add the library manually in KiCAD. You get the library location via
  `kikit-info lib`. Note that the library has to be named `kikit`

## Enabling plugins

KiKit comes with GUI plugins for KiCAD. These plugins are not enable by default
and you have to enable them. There is an utility `kikit-plugin` which allows you
to select which plugins you want to enable.

First, use `kikit-plugin list` to see all available plugins.

Then you can enable, e.g., all plugins by: `kikit-plugin enable --all` or
selected plugins by their identifier, e.g., `kikit-plugin enable
hideReferences`. Note that if you want to enable multiple plugins, you have to
specify them all at once. Also, the changes will take effect after restarting
PcbNew.

## Running KiKit via Docker

This method is applicable to Windows, Linux and MacOS. This method is suitable if
you plan to use KiKit inside a continuous integration.

First, install [Docker](https://www.docker.com/). The installation procedure
varies by the platform, so Google up a recent guide for your platform.

Then, pull the KiKit container via issuing one of the following commands:

```
docker pull yaqwsx/kikit:latest  # Pull latest stable version
docker pull yaqwsx/kikit:v0.7    # Pull image with a concrete release
docker pull yaqwsx/kikit:nightly # Pull upstream version of KiKit - content of the master branch
```

To run KiKit commands for files in the current working directory issue the
following command:

```
docker run -it -w /kikit -v $(pwd):/kikit yaqwsx/kikit /bin/bash
```

Note that for Windows, the docker command differs slightly:

```
docker run -it -w /kikit -v %cd%:/kikit yaqwsx/kikit /bin/bash
```

This will run a new terminal inside the docker container. You can issue any
kikit commands here. Note that on Windows you might have to explicitly allow for
mounting directories outside you user account (see [the following
topis](https://forums.docker.com/t/volume-mounts-in-windows-does-not-work/10693/5)).

If you would like to run a particular version of KiKit, simply append a tag to
the image name (e.g., `:nightly`).

If you want to use Makefile for your projects, the preferable way is to invoke
`make` inside the container. The Docker image contains several often used tools
and you can even run KiCAD from it (if you supply it with X-server).

# Choosing KiCAD version

When you have multiple versions of KiCAD installed, it might be desirable to run
KiKit with one or another (e.g., to not convert your designs into new format).

KiKit loads the Python API directly via a module, so which module is loaded
(which KiCAD version is used) follows standard Python conversion. Therefore, to
choose a particular KiCAD version, just specify the environmental variable
`PYTHONPATH`. The path have to point to a folder containing the module
(`pcbnew.py` file).

The most common on linux are:

```
stable: /usr/lib/python3/dist-packages/pcbn
nightly: /usr/lib/kicad-nightly/lib/python3/dist-packages/
```

E.g., to run KiKit with nightly, run:

```
PYTHONPATH=/usr/lib/kicad-nightly/lib/python3/dist-packages/ kikit
```

To run KiKit with a KiCAD you compiled (and not installed):

```
PYTHONPATH=path-to-sources/build/pcbnew kikit
```

This also works when you invoke `make` as environmental variables are
propagated:

```
PYTHONPATH=/usr/lib/kicad-nightly/lib/python3/dist-packages/ make
```
