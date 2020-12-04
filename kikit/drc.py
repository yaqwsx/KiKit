from kikit.pcbnew_compatibility import pcbnew, isV6, getVersion
import sys
import tempfile

def runImpl(boardfile, useMm, strict):
    try:
        if not isV6(getVersion()):
            raise RuntimeError("This feature is available only with KiCAD 6.")
        units = pcbnew.EDA_UNITS_MILLIMETRES if useMm else EDA_UNITS_INCHES
        b = pcbnew.LoadBoard(boardfile)
        with tempfile.NamedTemporaryFile(mode="w+") as tmpFile:
            result = pcbnew.WriteDRCReport(b, tmpFile.name, units, strict)
            tmpFile.seek(0)
            print(tmpFile.read())
            sys.exit(result)
    except Exception as e:
        sys.stderr.write("An error occurred: " + str(e) + "\n")
        sys.exit(1)
