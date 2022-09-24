#!/bin/bash
set -e -u

if [ "$EUID" -ne 0 ]
  then echo "Please run as root"
  exit
fi

V=3.8
KICAD_PYTHON="/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/$V"
CERTIFICATE="kikit"

echo "Kicad Python dir: $KICAD_PYTHON" 1>&2
echo "Python version: $V" 1>&2
echo "Signinf certificate: $CERTIFICATE" 1>&2

echo "KiKit will be installed" 1>&2
$KICAD_PYTHON/bin/python3 -m pip install kikit

echo "KiCAD will be resigned" 1>&2
codesign -fs "kikit" "$KICAD_PYTHON/Resources/Python.app"
codesign -fs "kikit" "/Applications/KiCad/KiCad.app"
codesign -fs "kikit" "/Applications/KiCad/KiCad.app/Contents/Applications/pcbnew.app"

cat << EOF  > /usr/local/bin/kikit
#!/bin/bash
$KICAD_PYTHON/bin/python3 -m kikit.ui "\$@"
EOF

chmod +x /usr/local/bin/kikit
