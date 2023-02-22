from enum import Enum, IntEnum
from .units import mm, inch

# These classes miss in the exported interface

class Layer(IntEnum):
    F_Cu = 0
    B_Cu = 31
    In1_Cu = 1
    In2_Cu = 2
    In3_Cu = 3
    In4_Cu = 4
    In5_Cu = 5
    In6_Cu = 6
    In7_Cu = 7
    In8_Cu = 8
    In9_Cu = 9
    In10_Cu = 10
    In11_Cu = 11
    In12_Cu = 12
    In13_Cu = 13
    In14_Cu = 14
    In15_Cu = 15
    In16_Cu = 16
    In17_Cu = 17
    In18_Cu = 18
    In19_Cu = 19
    In20_Cu = 20
    In21_Cu = 21
    In22_Cu = 22
    In23_Cu = 23
    In24_Cu = 24
    In25_Cu = 25
    In26_Cu = 26
    In27_Cu = 27
    In28_Cu = 28
    In29_Cu = 29
    In30_Cu = 30
    B_Adhes = 32
    F_Adhes = 33
    B_Paste = 34
    F_Paste = 35
    B_SilkS = 36
    F_SilkS = 37
    B_Mask = 38
    F_Mask = 39
    Dwgs_User = 40
    Cmts_User = 41
    Eco1_User = 42
    Eco2_User = 43
    Edge_Cuts = 44
    Margin = 45
    B_CrtYd = 46
    F_CrtYd = 47
    B_Fab = 48
    F_Fab = 49
    User_1 = 50
    User_2 = 51
    User_3 = 52
    User_4 = 53

    @staticmethod
    def allCu():
        return list(range(Layer.F_Cu, Layer.B_Cu + 1))

    @staticmethod
    def all():
        return list(range(Layer.F_Cu, Layer.User_4 + 1))

    @staticmethod
    def allTech():
        return list(x for x in range(Layer.Dwgs_User, Layer.User_4 + 1))

    @staticmethod
    def allSilk():
        return [Layer.F_SilkS, Layer.B_SilkS]

class STROKE_T(IntEnum):
    S_SEGMENT = 0
    S_RECT = 1
    S_ARC = 2
    S_CIRCLE = 3
    S_POLYGON = 4
    S_CURVE = 5

class EDA_TEXT_HJUSTIFY_T(IntEnum):
    GR_TEXT_HJUSTIFY_LEFT   = -1
    GR_TEXT_HJUSTIFY_CENTER = 0
    GR_TEXT_HJUSTIFY_RIGHT  = 1

class EDA_TEXT_VJUSTIFY_T(IntEnum):
    GR_TEXT_VJUSTIFY_TOP    = -1
    GR_TEXT_VJUSTIFY_CENTER = 0
    GR_TEXT_VJUSTIFY_BOTTOM = 1

class MODULE_ATTR_T(IntEnum):
    MOD_DEFAULT = 0,
    MOD_CMS     = 1
    MOD_VIRTUAL = 2

PAPER_SIZES = [f"A{size}" for size in range(6)] + ["A", "B", "C", "D", "E"] + \
              ["USLetter", "USLegal", "USLedger"]
PAPER_SIZES = PAPER_SIZES + [f"{paper}-portrait" for paper in PAPER_SIZES]

PAPER_DIMENSIONS = {
    "A5": (210 * mm, 148 * mm),
    "A4": (297 * mm, 210 * mm),
    "A3": (420 * mm, 297 * mm),
    "A2": (594 * mm, 420 * mm),
    "A1": (841 * mm, 594 * mm),
    "A0": (1198 * mm, 841 * mm),
    "A": (11 * inch, 8.5 * inch),
    "B": (17 * inch, 11 * inch),
    "C": (22 * inch, 17 * inch),
    "D": (34 * inch, 22 * inch),
    "E": (44 * inch, 34 * inch),
    "USLetter": (11 * inch, 8.5 * inch),
    "USLegal": (14 * inch, 8.5 * inch),
    "USLedger": (17 * inch, 11 * inch)
}
