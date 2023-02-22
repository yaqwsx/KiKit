# Installation

KiKit consists of three parts:

- a backend (a Python library that does all the heavy work and provides CLI)
- KiCAD PCM plugin which adds GUI for KiCAD, and
- KiCAD symbol and footprint libraries.

Unfortunately, it is not possible to install all three parts automatically in a
single step due to technical limitations of KiCAD's PCM at the moment, so you
have to install them separately.

## Backend installation

The backend installation differs slightly based on the platform:

- [Linux](linux.md) guide
- [Windows](windows.md) guide
- [macOS](macos.md) guide

## GUI and libraries installation

GUI plugins and libraries are available via KiCAD PCM. See [details about their
installation](gui_and_libs.md).

## Optional dependencies

Some KiKit features rely on external dependencies:

- [PcbDraw](https://github.com/yaqwsx/PcbDraw) – to be able to export
  presentation pages
- [OpenSCAD](https://openscad.org/) – to be able to export 3D models of stencil.
  Install it via your system package manage.

## Running KiKit in CI or isolated environment via Docker

We also distribute a Docker container for running KiKit in CI or on platform
where it is hard to meet all dependencies. This mode doesn't support GUI. Learn
[more about the docker images](docker.md).
