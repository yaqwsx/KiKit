FROM ubuntu:19.10

LABEL maintainer="Jan \"yaqwsx\" Mrázek" \
      description="Container for running KiKit applications"

ENV DISPLAY=unix:0.0

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      kicad kicad-libraries zip inkscape make git librsvg2-bin librsvg2-dev \
      python3 python3-pip python3-cairo python3-wheel python3-setuptools python3-gi python3-gi-cairo

RUN pip3 install Pcbdraw KiKit

CMD ["bash"]