# Running KiKit via Docker

This method is applicable to Windows, Linux and MacOS. It provides access to
all of the CLI commands in a known-working container, but doesn't allow your
local install of KiCad to access KiKit via the KiKit plugin.

First, install [Docker](https://www.docker.com/). The installation procedure
varies by the platform, so Google up a recent guide for your platform.

With Docker you can skip all of the install steps and instead run KiKit
via (on Linux or Mac):

```
docker run -v $(pwd):/kikit yaqwsx/kikit --help
```
(replacing the call to display the `--help` with whatever command you want to
run.  Try `--version` or `panelize`)

or on Windows:
```
docker run -v %cd%:/kikit yaqwsx/kikit --help
```

Note that on Windows you might have to explicitly allow for
mounting directories outside your user account (see [the following
topic](https://forums.docker.com/t/volume-mounts-in-windows-does-not-work/10693/5)).

## Creating an alias to KiKit in Docker to save some typing

If you're on Linux or Mac and are going to run commands repeatedly within the same
directory you can create an alias *within the current terminal session* via:
```
alias kikit="docker run -v $(pwd):/kikit yaqwsx/kikit"
```
**Note** that `alias` is a Linux/ Unix command so won't work on Windows, you'll need
to call `docker run -v %cd%:/kikit yaqwsx/kikit` each time.
**Also note** that you must update the alias (by running the same alias command again)
if you move to a different directory.  The current working directory for the alias
is "frozen" at the directory you create the alias in.

From then on, until you close that terminal, you'll be able to just run `kikit` followed
by the relevant paramenters (e.g. `kikit --version` or `kikit panelize`).

## Running different versions of KiKit via Docker

If you would like to run a particular version of KiKit, simply append a tag to
the image name (e.g., `yaqwsx/kikit:nightly`), and Docker will pull that version
down and run that for you instead:

```
docker run -v $(pwd):/kikit yaqwsx/kikit:nightly --version
```

We provide the following containers:

- **latests**: The latest stable version of KiKit with the newest stable KiCAD.
- **vX.Y.Z-KiCADvA**: A container with particular version of KiKit backed by
  given version of KiCAD.
- **nightly**, **nightly-m1**: Daily build of KiKit from the upstream version
  with the newest KiCAD. The m1 flavour supports mac M1.

A full list is available on
[Dockerhub](https://hub.docker.com/r/yaqwsx/kikit/tags).

## Mac M1 containers

There are also nightly containers of Mac M1 available with tag `nightly-m1`.

If you want to use Makefile for your projects, the preferable way is to invoke
`make` inside the container. The Docker image contains several often used tools
and you can even run KiCAD from it (if you supply it with X-server).  To call `make`
within the container, override the container's entrypoint:

```
docker run -it -v $(pwd):/kikit --entrypoint '/usr/bin/make' --help
```
(replacing `--help` with your make command, such as `build` or `test`).
