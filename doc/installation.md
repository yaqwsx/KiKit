# Installation

KiKit is distributed as a Python package. On most of the Linux distributions you
just have to install KiCAD and then install KiKit via Pip:

```
pip install KiKit # Use pip or pip3 based on your distribution
```

Then you are ready to use it. Note that if you would like to use GUI plugins in
KiCAD, you have enable them. Similarly, you can also register the KiKit
footprint library. See section "Enabling plugins" and "Enabling Kikit annotation
footprint library". Also, there are two optional dependencies:

- PcbDraw - to be able to export presentation pages (install it via `pip install
  PcbDraw`)
- OpenSCAD - to be able to export 3D models of stencil. Install it via your
  system package manage.

**Note that, the procedure above works on Linux and does not work on Windows or
MacOS.** Please, follow the alternative installation and usage guides below.

The reason for that is packaging of KiCAD on these platforms. There are some
plans for overcoming this issue, but they cannot be applied until KiCAD 6 is
released.

If you have multiple KiCAD versions installed, see the section "Choosing KiCAD
version".

If you would like to use the upstream (unstable) version of KiKit, you can
install it directly from GitHub:

```
pip3 install git+https://github.com/yaqwsx/KiKit@master
```

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

Note that KiKit currently supports only KiCAD v5.0 up to v5.1.7. This support
for nightly (v5.99) and v6 is work in progress and all the features might not
work. The final support for KiCAD 6 will be introduced after KiCAD 6 release
candidates is available.
