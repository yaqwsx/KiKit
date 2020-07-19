from enum import Enum, IntEnum

# These classes miss in the exported interface

class Layer(IntEnum):
    F_Cu = 0
    B_Cu = 31
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

