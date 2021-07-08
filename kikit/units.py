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

class BaseValue(int):
    """
    Value in base units that remembers its original string representation.
    """
    def __new__(cls, value, strRepr):
        x = super().__new__(cls, value)
        x.str = strRepr
        return x

    def __str__(self):
        return self.str

    def __repr__(self):
        return f"<BaseValue: {int(self)}, {self.str} >"


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
    if isinstance(unitStr, int):
        return BaseValue(unitStr, f"{unitStr}nm")
    if not isinstance(unitStr, str):
        raise RuntimeError(f"Got '{unitStr}', a length with units was expected")
    return BaseValue(readUnit(unitDir, unitStr), unitStr)

def readAngle(unitStr):
    unitDir = {
        "deg": deg,
        "°": deg,
        "rad": rad
    }
    if isinstance(unitStr, int):
        return BaseValue(unitStr, f"{unitStr / 10} deg")
    if not isinstance(unitStr, str):
        raise RuntimeError(f"Got '{unitStr}', an angle with units was expected")
    return BaseValue(readUnit(unitDir, unitStr), unitStr)
