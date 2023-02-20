import pytest
from pcbnewTransition.pcbnew import FromMM, FromMils
from kikit.units import readLength, readAngle, UnitError

def test_readLength():
    assert readLength("4.24mm") == FromMM(4.24)
    assert readLength("4.24 mm") == FromMM(4.24)
    assert readLength("4mm") == FromMM(4)

    assert readLength("1m") == FromMM(1000)
    assert readLength("1cm") == FromMM(10)

    assert readLength("1mil") == FromMils(1)
    assert readLength("1inch") == FromMils(1000)

