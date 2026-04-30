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

# Verify the signing identity exists and is not expired before doing any work.
# `codesign` reports an expired identity as "no identity found", which is
# misleading and wastes a lot of debugging time. The keychain may also hold
# multiple certificates with the same common name (e.g. an old expired one
# alongside a fresh replacement); accept the install if any of them is still
# valid, since codesign will pick one of those.
SCRATCH=$(mktemp -d)
trap 'rm -rf "$SCRATCH"' EXIT
security find-certificate -a -c "$CERTIFICATE" -p > "$SCRATCH/certs.pem" 2>/dev/null || true
if [ ! -s "$SCRATCH/certs.pem" ]; then
    echo "Error: code-signing certificate '$CERTIFICATE' not found in the keychain." 1>&2
    echo "Create one via Keychain Access -> Certificate Assistant -> Create a Certificate" 1>&2
    echo "(Identity Type: Self Signed Root, Certificate Type: Code Signing)," 1>&2
    echo "or pass an existing identity with -c <name>." 1>&2
    exit 1
fi
awk -v dir="$SCRATCH" '
    /-----BEGIN CERTIFICATE-----/ {n++; out=sprintf("%s/cert_%d.pem", dir, n)}
    {print > out}
' "$SCRATCH/certs.pem"
NOW_TS=$(date +%s)
LATEST_END_TS=0
LATEST_END=""
for f in "$SCRATCH"/cert_*.pem; do
    end=$(openssl x509 -in "$f" -noout -enddate 2>/dev/null | sed 's/^notAfter=//')
    [ -z "$end" ] && continue
    ts=$(date -j -f "%b %d %H:%M:%S %Y %Z" "$end" +%s 2>/dev/null || echo 0)
    if [ "$ts" -gt "$LATEST_END_TS" ]; then
        LATEST_END_TS=$ts
        LATEST_END=$end
    fi
done
if [ "$LATEST_END_TS" -lt "$NOW_TS" ]; then
    echo "Error: code-signing certificate '$CERTIFICATE' expired on $LATEST_END." 1>&2
    echo "Recreate it (Keychain Access -> Certificate Assistant -> Create a Certificate)" 1>&2
    echo "and consider a long validity period (e.g. 3650 days) to avoid recurrence." 1>&2
    exit 1
fi

# Older pip versions (e.g. the 22.0.4 still bundled with KiCad's framework
# Python) plus legacy setuptools register source-tree files in the install
# RECORD when running `pip install -e .`. A subsequent reinstall then
# uninstalls the previous version using that RECORD and deletes the source
# tree before the new install runs. Uninstall any pre-existing kikit from a
# scratch directory so any stale relative paths in the RECORD resolve to
# nothing and cannot harm the source checkout.
if $KICAD_PYTHON/bin/python3 -m pip show kikit >/dev/null 2>&1; then
    echo "Removing previous kikit install (from scratch dir to avoid pip 22 RECORD bug)" 1>&2
    (cd "$SCRATCH" && $KICAD_PYTHON/bin/python3 -m pip uninstall -y kikit)
fi

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
