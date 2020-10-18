# Installation

KiKit is distributed as a Python package. On most of the Linux distributions you
just have to install KiCAD and then install KiKit via Pip:

```
pip install KiKit # Use pip or pip3 based on your distribution
```

Then you are ready to use it. There are two optional dependencies:

- PcbDraw - to be able to export presentation pages (install it via `pip install
  PcbDraw`)
- OpenSCAD - to be able to export 3D models of stencil. Install it via your
  system package manage.

**Note that, the procedure above works on Linux and does not work on Windows or
MacOS.** Please, follow the alternative installation and usage guides below.

The reason for that is packaging of KiCAD on these platforms. There are some
plans for overcoming this issue, but they cannot be applied until KiCAD 6 is
released.

## Running KiKit in Windows Subsystem for Linux

This method is applicable only on Windows.

First, install WSL according to the [official
guide](https://docs.microsoft.com/en-us/windows/wsl/install-win10). Use the
distribution of your choice (if you are unsure, choose Ubuntu). Once you have a
terminal inside WSL, you can follow the installation guide from the beginning of
this document. Note that you have to install KiCAD inside WSL, the installation
on Windows will not work for KiKit.

For Ubuntu, the procedure might look like this:
```
sudo apt update
sudo apt install kicad python3 python3-pip \
    python3-wheel python3-setuptools openscad

pip3 install Pcbdraw KiKit
```

Then you can verify the installation by running `kikit --help`.

## Running KiKit via Docker

This method is applicable to Windows, Linux and MacOS.

First, install [Docker](https://www.docker.com/). The installation procedure
varies by the platform, so Google up a recent guide for your platform.

Then, pull the KiKit container via issuing the following command:

```
docker pull yaqwsx/kikit
```

To run KiKit commands for files in the current working directory issue the
following command:

```
docker run -it -w /kikit -v $(pwd):/kikit yaqwsx/kikit /bin/bash
```

This will run a new terminal inside the docker container. You can issue any
kikit commands here. Note that on Windows you might have to explicitly allow for
mounting directories outside you user account (see [the following
topis](https://forums.docker.com/t/volume-mounts-in-windows-does-not-work/10693/5)).

If you want to use Makefile for your projects, the preferable way is to invoke
`make` inside the container and to invoke docker from make.
