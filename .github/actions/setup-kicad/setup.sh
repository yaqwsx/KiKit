#!/usr/bin/env bash

set -e

case $1 in
  'v5')
    sudo add-apt-repository --yes --enable-source ppa:kicad/kicad-5.1-releases
    sudo apt-get update
    sudo apt-get install --yes --no-install-recommends kicad
    kicad_PYTHONPATH=/usr/lib/python3/dist-packages
    sudo ln -srf "${kicad_PYTHONPATH}"/_pcbnew.*.so "${kicad_PYTHONPATH}/_pcbnew.so"
    ;;

  'v6')
    sudo add-apt-repository --yes --enable-source ppa:kicad/kicad-6.0-releases
    sudo apt-get update
    sudo apt-get install --yes --no-install-recommends kicad
    kicad_PYTHONPATH=/usr/lib/python3/dist-packages
    ;;

  'v7')
    sudo add-apt-repository --yes --enable-source ppa:kicad/kicad-7.0-releases
    sudo apt-get update
    sudo apt-get install --yes --no-install-recommends kicad
    kicad_PYTHONPATH=/usr/lib/python3/dist-packages
    ;;
  'v7-testing')
    sudo add-apt-repository --yes --enable-source ppa:kicad/kicad-7.0-nightly
    sudo apt-get update
    sudo apt-get install --yes --no-install-recommends kicad
    kicad_PYTHONPATH=/usr/lib/python3/dist-packages
    ;;

  'v8')
    sudo add-apt-repository --yes --enable-source ppa:kicad/kicad-8.0-releases
    sudo apt-get update
    sudo apt-get install --yes --no-install-recommends kicad
    kicad_PYTHONPATH=/usr/lib/python3/dist-packages
    ;;
  'v8-testing')
    sudo add-apt-repository --yes --enable-source ppa:kicad/kicad-8.0-nightly
    sudo apt-get update
    sudo apt-get install --yes --no-install-recommends kicad
    kicad_PYTHONPATH=/usr/lib/python3/dist-packages
    ;;

  'v9')
    sudo add-apt-repository --yes --enable-source ppa:kicad/kicad-9.0-releases
    sudo apt-get update
    sudo apt-get install --yes --no-install-recommends kicad
    kicad_PYTHONPATH=/usr/lib/python3/dist-packages
    ;;
  'v9-testing')
    sudo add-apt-repository --yes --enable-source ppa:kicad/kicad-9.0-nightly
    sudo apt-get update
    sudo apt-get install --yes --no-install-recommends kicad
    kicad_PYTHONPATH=/usr/lib/python3/dist-packages
    ;;

  'nightly')
    sudo add-apt-repository --yes --enable-source ppa:kicad/kicad-dev-nightly
    sudo apt-get update
    sudo apt-get install --yes --no-install-recommends kicad-nightly
    kicad_PYTHONPATH=/usr/lib/kicad-nightly/lib/python3/dist-packages
    kicad_LIBRARY_PATH=/usr/lib/kicad-nightly/lib/x86_64-linux-gnu
    for bin in kicad pcbnew eeschema kicad-cli; do
        sudo ln -s /usr/bin/${bin}-nightly /usr/bin/${bin}
    done
    ;;

  *)
    echo "Invalid version '$1' passed. Only 'v5', 'v6', 'v7', 'v7-testing', 'v8', 'v8-testing', 'v9', 'v9-testing' and 'nightly' supported" >&2
    exit 1
    ;;
esac

if ! [[ -f "$kicad_PYTHONPATH/pcbnew.py" && -f "$kicad_PYTHONPATH/_pcbnew.so" ]]; then
    echo "setup-kicad/setup.sh seems to have the wrong location for where KiCad installs pcbnew.py or _pcbnew.so, and needs updated" >&2
    find /usr /opt \( -name pcbnew.py -o -name _pcbnew.so \) -print >&2
    exit 1
fi
if sudo python3 -c 'import sys; sys.exit(1 if sys.argv[1] in sys.path else 0)' "$kicad_PYTHONPATH"; then
    sys_PYTHONPATH=$(sudo python3 -c 'import sys; print(next(p for p in sys.path if "site-packages" in p))')
    sudo ln -sf "$kicad_PYTHONPATH/pcbnew.py" "$kicad_PYTHONPATH/_pcbnew.so" "$sys_PYTHONPATH"
fi
if python3 -c 'import sys; sys.exit(1 if sys.argv[1] in sys.path else 0)' "$kicad_PYTHONPATH"; then
    user_PYTHONPATH=$(python3 -c 'import sys; print(next(p for p in sys.path if "site-packages" in p))')
    ln -sf "$kicad_PYTHONPATH/pcbnew.py" "$kicad_PYTHONPATH/_pcbnew.so" "$user_PYTHONPATH"
fi
# KiCad pulled in wxPython for the APT Python, but if that's not what
# `python3` is (probably because it's from `actions/setup-python`)
# then we need to install wxPython ourselves.
if ! python3 -c 'import wx'; then
    mkdir ~/wx
    pushd ~/wx
    sudo apt-get build-dep wxpython4.0
    if python3 -c 'import sys; sys.exit(0 if sys.version_info.minor < 12 else 1)'; then
        wxPython_version=4.2.1

        curl -LO "https://files.pythonhosted.org/packages/source/w/wxPython/wxPython-${wxPython_version}.tar.gz"
        tar xaf "wxPython-${wxPython_version}.tar.gz"
        cd "wxPython-${wxPython_version}"
    else
        # 4.2.3 is the minimum version to not-segfault with Python 3.12.
        wxPython_version=4.2.3
        python3 -m pip install setuptools

        # We need to re-generate files; the generated files shipped
        # with 4.2.3 need newer wxWidgets than what the system has.
        if [[ "$(wx-config --version)" != 3.2.1 ]]; then
            echo "setup-kicad/setup.sh needs updated for a different wxWidgets version" >&2
            exit 1
        fi
        # To do this, we'll get wxPython from Git instead of from a
        # tarball, so that we can easily roll back ext/wxWidgets to
        # the version we need.  (So actually we won't be
        # "re-"generating the files, since the generated files aren't
        # checked into Git in the first place!)

        git clone --branch="wxPython-${wxPython_version}" https://github.com/wxWidgets/Phoenix wxPython
        cd wxPython
        git submodule update --init

        # Adjust which wxWidgets version we generate against.
        git show a1c9554bbf10f88cb0ca3602e3011d9977854ae5 -- etg/window.py | patch -p1 -R # 2024-05-16, needs v3.2.5
        git revert --no-commit 7a198b8cae9a81cec4d25a0c6c5cc65ad8822bb2 # 2023-11-20, needs v3.2.3
        git revert --no-commit 1236562af55be1d8064d851e58dd1db3699040de # 2023-06-27, needs v3.2.3
        git revert --no-commit 371101db7a010d679d214fde617dae9de02008d9 # 2023-07-14, needs v3.2.3
        git -C ext/wxWidgets checkout "v$(wx-config --version)"

        # NB: Currently APT's sip-tools is 6.7.5, and wxPython
        # 4.2.3 requires sip>=6.8, so it is important that we get
        # it from pip instead of from apt.
        python3 -m pip install sip requests

        # Generate the files.
        # `sip` needs the `etg` output, and `etg` needs the `dox` output.
        python3 build.py --jobs=$(nproc) --use_syswx --nodoc --release dox
        python3 build.py --jobs=$(nproc) --use_syswx --nodoc --release etg
        python3 build.py --jobs=$(nproc) --use_syswx --nodoc --release sip
    fi
    # Build.
    python3 build.py --jobs=$(nproc) --use_syswx --nodoc --release build
    # Install.
    python3 build.py --jobs=$(nproc) --use_syswx --nodoc --release install
    popd
fi

if [[ -n "$kicad_LIBRARY_PATH" ]]; then
    if [[ ! -f "$kicad_LIBRARY_PATH/libkicad_3dsg.so"  ]]; then
        echo "setup-kicad/setup.sh seems to have the wrong location for where KiCad installs libkicad_3dsg.so, and needs updated" >&2
        find /usr /opt -name 'libkicad*' -print >&2
        exit 1
    fi
    echo "LD_LIBRARY_PATH=${kicad_LIBRARY_PATH}${LD_LIBRARY_PATH+:${LD_LIBRARY_PATH}}" >> $GITHUB_ENV
fi
