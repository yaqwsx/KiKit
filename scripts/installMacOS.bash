#!/bin/bash
set -e -u

if [ "$EUID" -ne 0 ]
  then echo "Please run as root"
  exit
fi

EDITABLE=0
KICAD_PYTHON_BASE="/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions"
CERTIFICATE="kikit"


# Read command line options
while getopts ":p:c:e" opt; do
  case $opt in
    p) 
      KICAD_PYTHON_BASE="$OPTARG"
    ;;
    c) 
      CERTIFICATE="$OPTARG"
    ;;
    e) 
      EDITABLE=1
    ;;
    \?) 
      echo "Invalid option -$OPTARG" >&2
      exit 1
    ;;
  esac
done

# KiCad 7 has an updated Python version; get the Python version from the KiCad Application
# directory.

V=$(basename "$KICAD_PYTHON_BASE"/?.?)
KICAD_PYTHON="$KICAD_PYTHON_BASE/$V"


echo "Kicad Python dir: $KICAD_PYTHON" 1>&2
echo "Python version: $V" 1>&2
echo "Signing certificate: $CERTIFICATE" 1>&2

if [ $EDITABLE -eq 1 ]; then
    echo "Installing editable version of kikit" 1>&2
    $KICAD_PYTHON/bin/python3 -m pip install -e .
else
    echo "Installing kikit from PyPI" 1>&2
    $KICAD_PYTHON/bin/python3 -m pip install kikit
fi

echo "KiCAD will be re-signed" 1>&2
codesign -fs "$CERTIFICATE" "$KICAD_PYTHON/Resources/Python.app"
codesign -fs "$CERTIFICATE" "/Applications/KiCad/KiCad.app"
codesign -fs "$CERTIFICATE" "/Applications/KiCad/KiCad.app/Contents/Applications/pcbnew.app"

mkdir -p /usr/local/bin

cat << EOF  > /usr/local/bin/kikit
#!/bin/bash
$KICAD_PYTHON/bin/python3 -m kikit.ui "\$@"
EOF

chmod +x /usr/local/bin/kikit
