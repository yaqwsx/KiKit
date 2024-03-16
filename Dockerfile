ARG REPO=ubuntu
FROM $REPO:22.04 AS base

ARG KICAD_VERSION="8.0"
ARG ADDITIONAL_PACKAGES
ARG ADDITIONAL_PYTHON_PACKAGES

LABEL maintainer="Jan \"yaqwsx\" Mrázek" \
      description="Container for running KiKit applications"

RUN apt-get update && \
    apt-get install -y software-properties-common $ADDITIONAL_PACKAGES && \
    rm -rf /var/lib/apt/lists/*

RUN add-apt-repository --yes ppa:kicad/kicad-$KICAD_VERSION-releases

# Setup ENV variables for KiCAD 7 & 8
# See https://gitlab.com/kicad/packaging/kicad-ubuntu-builder/kicad-daily-package/-/issues/43
ENV PYTHONPATH=/usr/lib/kicad/lib/python3/dist-packages:${PYTHONPATH} \
    LD_LIBRARY_PATH=/usr/lib/kicad/lib/x86_64-linux-gnu/:${LD_LIBRARY_PATH}

RUN export DEBIAN_FRONTEND="noninteractive" && apt-get -qq update && \
    apt-get -qq install -y --no-install-recommends \
      kicad kicad-libraries zip inkscape make git libmagickwand-dev \
      python3 $ADDITIONAL_PYTHON_PACKAGES python3-pip python3-wheel python3-setuptools inkscape \
      libgraphicsmagick1-dev libmagickcore-dev openscad && \
      rm -rf /var/lib/apt/lists/*

# hack: manually install Python dependencies to speed up the build process
# for repetitive builds

RUN pip3 install \
    "Pcbdraw ~= 1.0" \
    "numpy ~= 1.21.5" \
    "shapely ~= 1.7" \
    "click ~= 7.1" \
    "markdown2 ~= 2.4" \
    "pybars3 ~= 0.9" \
    "solidpython ~= 1.1"

# create a new stage for building and installing KiKit
FROM base AS build

COPY . /src/kikit
WORKDIR /src/kikit
RUN python3 setup.py install

# the final stage only takes the installed packages from dist-packages
# and ignores the src directories
FROM base
COPY --from=build \
    /usr/local/lib/python3.10/dist-packages \
    /usr/local/lib/python3.10/dist-packages
COPY --from=build \
    /usr/local/bin \
    /usr/local/bin

ENTRYPOINT [ "/usr/local/bin/kikit" ]
WORKDIR "/kikit"
