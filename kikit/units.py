import re
import math
from pcbnewTransition import pcbnew
from copy import deepcopy

class UnitError(RuntimeError):
    pass

# Define unit conversion constants
mm = 1000000
cm = 10 * mm
dm = 100 * mm
m  = 1000 * mm
mil = 25400
inch = 1000 * mil

deg = pcbnew.EDA_ANGLE(1, pcbnew.DEGREES_T)
rad = pcbnew.EDA_ANGLE(1, pcbnew.RADIANS_T)

UNIT_SPLIT = re.compile(r"\s*(-?\s*\d+(\.\d*)?)\s*(\w+|\%)$")

class BaseValue(int):
    """
    Value in base units that remembers its original string representation.
    """
    def __deepcopy__(self, memo):
        cls = self.__class__
        value = self
        strRepr = self.str
        result = cls.__new__(cls, value, strRepr)
        memo[id(self)] = result
        for k, v in self.__dict__.items():
            setattr(result, k, deepcopy(v, memo))
        return result

    def __new__(cls, value, strRepr):
        x = super().__new__(cls, value)
        x.str = strRepr
        return x

    def __str__(self):
        return self.str

    def __repr__(self):
        return f"<BaseValue: {int(self)}, {self.str} >"

class BaseAngle(pcbnew.EDA_ANGLE):
    """
    Angle value that remembers its original string representation.
    """
    def __init__(self, value: pcbnew.EDA_ANGLE, strRepr: str) -> None:
        super().__init__(value.AsDegrees(), pcbnew.DEGREES_T)
        self.str = strRepr

    def __str__(self):
        return self.str

    def __repr__(self):
        return f"<BaseAngle: {int(self)}, {self.str} >"


class PercentageValue(float):
    """
    Value in percents that remembers its original string representation.

    Value is stored as floating point number where 1 corresponds to 100 %.
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

def readAngle(unitStr: str) -> BaseAngle:
    unitDir = {
        "deg": deg,
        "°": deg,
        "rad": rad
    }
    if isinstance(unitStr, int):
        return BaseAngle(pcbnew.EDA_ANGLE(unitStr, pcbnew.TENTHS_OF_A_DEGREE_T), f"{unitStr / 10} deg")
    if not isinstance(unitStr, str):
        raise RuntimeError(f"Got '{unitStr}', an angle with units was expected")
    return BaseAngle(readUnit(unitDir, unitStr), unitStr)

def readPercents(unitStr):
    unitDir = { "%": 0.01 }
    return PercentageValue(readUnit(unitDir, unitStr), unitStr)
