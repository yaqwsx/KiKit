import re
import math

class UnitError(RuntimeError):
    pass

# Define unit conversion constants
mm = 1000000
cm = 10 * mm
dm = 100 * mm
m  = 1000 * mm
mil = 25400
inch = 1000 * mil

deg = 10
rad = 180 / math.pi * deg

UNIT_SPLIT = re.compile(r"\s*(-?\s*\d+(\.\d*)?)\s*(\w+)$")

def readUnit(unitDir, unitStr):
    match = UNIT_SPLIT.match(unitStr)
    if not match:
        raise UnitError(f"Cannot read quantity '{unitStr}'")
    try:
        amount = float(match.group(1))
        return amount * unitDir[match.group(3)]
    except KeyError:
        raise UnitError(f"Unknown unit in '{unitStr}'")

def readLength(unitStr):
    unitDir = {
        "mm": mm,
        "cm": cm,
        "dm": dm,
        "m": m,
        "mil": mil,
        "inch": inch,
        "in": inch
    }
    return int(readUnit(unitDir, unitStr))

def readAngle(unitStr):
    unitDir = {
        "deg": deg,
        "°": deg,
        "rad": rad
    }
    return readUnit(unitDir, unitStr)
