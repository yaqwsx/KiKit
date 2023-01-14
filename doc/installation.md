# Installation

KiKit is distributed as a Python package. If you installed it via KiCAD's Plugin
and Content Manager (PCM), you still have to install it via the procedures below
as the PCM only distributes the graphical interface (note that as of KiCAD 6 it
is impossible to distribute KiKit completely via PCM).

The installation steps differ slightly based on the operating system you use, but
consists of three steps:

- perform the basic installation:
  - [Linux](#installation-on-linux)
  - [Windows](#installation-on-windows)
  - [MacOS](macosInstallation.md) (**Extra steps are required, please, read the guide**)
  - Or you can run KiKit inside [Docker](#running-kikit-via-docker) - which
    might be useful e.g., for continuous integration.
  - If you would like to install special version of KiKit (e.g., nightly or a
    specific feature under development), please follow
    [Installing a special version of KiKit](#installing-a-special-version-of-kikit).
- register the GUI plugins and library:
  - either [install KiKit from PCM](#kikit-symbol-and-footprint-libraries),
  - or download KiKit packages and install them manually:
    - [KiKit](https://nightly.link/yaqwsx/KiKit/workflows/test-kikit/master/kikit-pcm.zip)
    - [KiKit Libraries](https://nightly.link/yaqwsx/KiKit/workflows/test-kikit/master/kikit-lib-pcm.zip)
- Optionally, you can install the [optional
  dependencies](#optional-dependencies) required for certain functions.

## Upgrading KiKit

If you want to upgrade KiKit, you have to perform two steps:
- you upgrade the backend by running `pip install -U kikit` in the command line
  (depending on the platform, see the installation instructions below).
- then you can upgrade the PCM packages within KiCAD. Note that this step is
  often not needed. If it will be needed, the release notes will say so.

## Installation on Linux

The installation consists of a single command you have to enter into the
terminal. If you installed KiCAD via package manager (apt, yum, etc.) you can
use a regular terminal and enter `pip3 install kikit`. Now you are ready to use
KiKit.

However, if you installed KiCAD via Flatpak, you have to open a special terminal
as Flatpak sandboxes the applications. Open terminal and invoke `flatpak run
--command=sh org.kicad.KiCad`, this will open a terminal session inside the
KiCAD’s sandbox. Now you can install pip via `python3 -m ensurepip` and then,
inside the same terminal you can install KiKit: `python3 -m pip install kikit`.
If you would like to use CLI interface, all commands have to be invoked inside
the shell `flatpak run --command=sh org.kicad.KiCad`, and, instead of `kikit
something` you have to use `python -m kikit.ui something`.

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
and libraries via Plugin and Content Manager. You might also want to consider
installing the [optional dependencies](#optional-dependencies).

## Installation on Windows

To install KiKit on Windows, you have to open "KiCAD Command Prompt". You can
find it in the start menu:

![KiCAD Command Prompt in Start menu](resources/windowsCommandPrompt1.jpg)

Once you have it open like this:

![KiCAD Command Prompt in Start menu](resources/windowsCommandPrompt2.jpg)

you can put command in there and confirm them by pressing
enter. This is also the prompt from which you will invoke all KiKit's CLI
commands. They, unfortunately, does not work in an ordinary Command prompt due
to the way KiCAD is packaged on Windows.

Then you have to enter the following command to install it:

```.bash
pip install kikit
```

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

## KiKit Symbol and Footprint Libraries

From v6 onwards KiCad comes with a "Plugin and Content Manager" (PCM) which can be used to 
add the KiKit symbol and footprint libraries used in multi-board workflows.  The PCM is new 
functionality for KiCad though, and only does part of the installation in v6.  To install 
the libraries using the PCM:

1. Open KiCad
2. Open the `Tools` menu and select `Plugin and Content Manager`
3. Select the `Libraries` tab and scroll down to `KiKit Library`
4. Press `Install` and then `Apply Changes`
5. Close the Plugin and Content Manager

*The following steps are only required in KiCad 6, they are automated in KiCad 7*:

7. Back in the main KiCad window, open the `Preferences` menu and select `Manage Symbol Libraries`
8. Select the `Global Libraries` tab, and click the `+` icon towards the bottom of the window then 
enter `kikit` (all lowercase) as the nickname, and 
`${KICAD6_3RD_PARTY}/symbols/com_github_yaqwsx_kikit-library/kikit.kicad_sym` as the Library Path.
8. Press `OK`
9. Back in the main KiCad window, open the `Preferences` menu and select `Manage Footprint Libraries`
10. As before, add a row to the table in the `Global Libraries` tab, with a nickname `kikit` (all 
lowercase again), and this time enter 
`${KICAD6_3RD_PARTY}/footprints/com_github_yaqwsx_kikit-library/kikit.pretty` for the Library Path.
11. Press `OK`
12. From now on, you can find the KiKit symbols and footprints under `kikit` alongside all the 
others.

## Optional dependencies

- [PcbDraw](https://github.com/yaqwsx/PcbDraw) - to be able to export
  presentation pages
- [OpenSCAD](https://openscad.org/) - to be able to export 3D models of stencil.
  Install it via your system package manage.


## Running KiKit via Docker

This method is applicable to Windows, Linux and MacOS. This method is suitable if
you plan to use KiKit inside a continuous integration.

First, install [Docker](https://www.docker.com/). The installation procedure
varies by the platform, so Google up a recent guide for your platform.

Then, pull the KiKit container via issuing one of the following commands:

```
docker pull yaqwsx/kikit:latest  # Pull latest stable version
docker pull yaqwsx/kikit:v1.0.2  # Pull image with a concrete release
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

There are also nightly containers of Mac M1 available with tag `nightly-m1`.

If you want to use Makefile for your projects, the preferable way is to invoke
`make` inside the container. The Docker image contains several often used tools
and you can even run KiCAD from it (if you supply it with X-server).

# Choosing KiCAD version

When you have multiple versions of KiCAD installed, it might be desirable to run
KiKit with one or another (e.g., to not convert your designs into new format).

KiKit loads the Python API directly via a module, so which module is loaded
(which KiCAD version is used) follows standard Python conventions. Therefore, to
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
