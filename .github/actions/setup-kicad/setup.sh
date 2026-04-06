#!/usr/bin/env bash

set -e

case $1 in
  'v9')
    sudo add-apt-repository --yes ppa:kicad/kicad-9.0-releases
    sudo apt-get update
    sudo apt-get install --yes --no-install-recommends kicad
    echo "PYTHONPATH=/usr/lib/kicad/lib/python3/dist-packages/:/usr/lib/kicad/local/lib/python3.10/dist-packages:/usr/lib/kicad/local/lib/python3.11/dist-packages:/usr/lib/kicad/local/lib/python3.12/dist-packages" >> $GITHUB_ENV
    echo "LD_LIBRARY_PATH=/usr/lib/kicad/lib/x86_64-linux-gnu:/usr/lib/kicad/lib/" >> $GITHUB_ENV
    ;;
  'v9-testing')
    sudo add-apt-repository --yes ppa:kicad/kicad-9.0-nightly
    sudo apt-get update
    sudo apt-get install --yes --no-install-recommends kicad
    echo "PYTHONPATH=/usr/lib/kicad/lib/python3/dist-packages/:/usr/lib/kicad/local/lib/python3.10/dist-packages:/usr/lib/kicad/local/lib/python3.11/dist-packages:/usr/lib/kicad/local/lib/python3.12/dist-packages" >> $GITHUB_ENV
    echo "LD_LIBRARY_PATH=/usr/lib/kicad/lib/x86_64-linux-gnu:/usr/lib/kicad/lib/" >> $GITHUB_ENV
    ;;
  'v10')
    sudo add-apt-repository --yes ppa:kicad/kicad-10.0-releases
    sudo apt-get update
    sudo apt-get install --yes --no-install-recommends kicad
    echo "PYTHONPATH=/usr/lib/kicad/lib/python3/dist-packages/:/usr/lib/kicad/local/lib/python3.10/dist-packages:/usr/lib/kicad/local/lib/python3.11/dist-packages:/usr/lib/kicad/local/lib/python3.12/dist-packages" >> $GITHUB_ENV
    echo "LD_LIBRARY_PATH=/usr/lib/kicad/lib/x86_64-linux-gnu:/usr/lib/kicad/lib/" >> $GITHUB_ENV
    ;;
  'v10-testing')
    sudo add-apt-repository --yes ppa:kicad/kicad-10.0-nightly
    sudo apt-get update
    sudo apt-get install --yes --no-install-recommends kicad
    echo "PYTHONPATH=/usr/lib/kicad/lib/python3/dist-packages/:/usr/lib/kicad/local/lib/python3.10/dist-packages:/usr/lib/kicad/local/lib/python3.11/dist-packages:/usr/lib/kicad/local/lib/python3.12/dist-packages" >> $GITHUB_ENV
    echo "LD_LIBRARY_PATH=/usr/lib/kicad/lib/x86_64-linux-gnu:/usr/lib/kicad/lib/" >> $GITHUB_ENV
    ;;

  *)
    echo "Invalid version '$1' passed. Only 'v9', 'v9-testing', 'v10' and 'v10-testing' supported" >&2
    exit 1
    ;;
esac
