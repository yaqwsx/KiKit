#!/usr/bin/env bash

set -e

case $1 in
  'v5')
    sudo add-apt-repository --yes ppa:kicad/kicad-5.1-releases
    sudo apt-get update
    sudo apt-get install --yes --no-install-recommends kicad
    ;;

  'v6')
    sudo add-apt-repository --yes ppa:kicad/kicad-6.0-releases
    sudo apt-get update
    sudo apt-get install --yes --no-install-recommends kicad
    ;;

  'v7')
    sudo add-apt-repository --yes ppa:kicad/kicad-7.0-releases
    sudo apt-get update
    sudo apt-get install --yes --no-install-recommends kicad
    # The Pcbnew module is located in
    # - /usr/lib/kicad/lib/python3/dist-packages
    # - instead of /usr/lib/python3/dist-packages/pcbnew.py
    # Let's add it to PYTHONPATH and also set LD_LIBRARY_PATH
    echo "PYTHONPATH=/usr/lib/kicad/lib/python3/dist-packages:${PYTHONPATH}" >> $GITHUB_ENV
    echo "LD_LIBRARY_PATH=/usr/lib/kicad/lib/x86_64-linux-gnu/:${LD_LIBRARY_PATH}" >> $GITHUB_ENV
    ;;
  'v7-testing')
    sudo add-apt-repository --yes ppa:kicad/kicad-7.0-nightly
    sudo apt-get update
    sudo apt-get install --yes --no-install-recommends kicad
    # The Pcbnew module is located in
    # - /usr/lib/kicad/lib/python3/dist-packages
    # - instead of /usr/lib/python3/dist-packages/pcbnew.py
    # Let's add it to PYTHONPATH and also set LD_LIBRARY_PATH
    echo "PYTHONPATH=/usr/lib/kicad/lib/python3/dist-packages:${PYTHONPATH}" >> $GITHUB_ENV
    echo "LD_LIBRARY_PATH=/usr/lib/kicad/lib/x86_64-linux-gnu/:${LD_LIBRARY_PATH}" >> $GITHUB_ENV
    ;;
  'v8')
    sudo add-apt-repository --yes ppa:kicad/kicad-8.0-releases
    sudo apt-get update
    sudo apt-get install --yes --no-install-recommends kicad
    # The Pcbnew module is located in
    # - /usr/lib/kicad/lib/python3/dist-packages
    # - instead of /usr/lib/python3/dist-packages/pcbnew.py
    # Let's add it to PYTHONPATH and also set LD_LIBRARY_PATH
    echo "PYTHONPATH=/usr/lib/kicad/lib/python3/dist-packages:${PYTHONPATH}" >> $GITHUB_ENV
    echo "LD_LIBRARY_PATH=/usr/lib/kicad/lib/x86_64-linux-gnu/:${LD_LIBRARY_PATH}" >> $GITHUB_ENV
    echo "PYTHONPATH=/usr/lib/kicad/lib/python3/dist-packages/:/usr/lib/kicad/local/lib/python3.10/dist-packages:/usr/lib/kicad/local/lib/python3.11/dist-packages:/usr/lib/kicad/local/lib/python3.12/dist-packages" >> $GITHUB_ENV
    echo "LD_LIBRARY_PATH=/usr/lib/kicad/lib/x86_64-linux-gnu:/usr/lib/kicad/lib/" >> $GITHUB_ENV
    ;;
  'v8-testing')
    sudo add-apt-repository --yes ppa:kicad/kicad-8.0-nightly
    sudo apt-get update
    sudo apt-get install --yes --no-install-recommends kicad
    # The Pcbnew module is located in
    # - /usr/lib/kicad/lib/python3/dist-packages
    # - instead of /usr/lib/python3/dist-packages/pcbnew.py
    # Let's add it to PYTHONPATH and also set LD_LIBRARY_PATH
    echo "PYTHONPATH=/usr/lib/kicad/lib/python3/dist-packages:${PYTHONPATH}" >> $GITHUB_ENV
    echo "LD_LIBRARY_PATH=/usr/lib/kicad/lib/x86_64-linux-gnu/:${LD_LIBRARY_PATH}" >> $GITHUB_ENV
    echo "PYTHONPATH=/usr/lib/kicad/lib/python3/dist-packages/:/usr/lib/kicad/local/lib/python3.10/dist-packages:/usr/lib/kicad/local/lib/python3.11/dist-packages:/usr/lib/kicad/local/lib/python3.12/dist-packages" >> $GITHUB_ENV
    echo "LD_LIBRARY_PATH=/usr/lib/kicad/lib/x86_64-linux-gnu:/usr/lib/kicad/lib/" >> $GITHUB_ENV
    ;;
  'nightly')
    sudo add-apt-repository --yes ppa:kicad/kicad-dev-nightly
    sudo apt-get update
    sudo apt-get install --yes --no-install-recommends kicad-nightly
    echo "PYTHONPATH=/usr/lib/kicad-nightly/lib/python3/dist-packages/:/usr/lib/kicad-nightly/local/lib/python3.10/dist-packages:/usr/lib/kicad-nightly/local/lib/python3.11/dist-packages:/usr/lib/kicad-nightly/local/lib/python3.12/dist-packages" >> $GITHUB_ENV
    echo "LD_LIBRARY_PATH=/usr/lib/kicad-nightly/lib/x86_64-linux-gnu:/usr/lib/kicad-nightly/lib/" >> $GITHUB_ENV
    for bin in kicad pcbnew eeschema kicad-cli; do
        sudo ln -s /usr/bin/${bin}-nightly /usr/bin/${bin}
    done
    ;;

  *)
    echo "Invalid version '$1' passed. Only 'v5', 'v6', 'v7', 'v7-testing', 'v8', 'v8-testing' and 'nightly' supported" >&2
    exit 1
    ;;
esac
