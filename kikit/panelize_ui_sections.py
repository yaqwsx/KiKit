from kikit.units import readLength, readAngle
from kikit.defs import Layer, EDA_TEXT_HJUSTIFY_T, EDA_TEXT_VJUSTIFY_T

class PresetError(RuntimeError):
    pass

ANCHORS = ["tl", "tr", "bl", "br", "mt", "mb", "ml", "mr", "c"]

class SLength:
    def validate(self, x):
        return readLength(x)

class SAngle:
    def validate(self, x):
        return readAngle(x)

class SNum:
    def validate(self, x):
        return int(x)

class SStr:
    def validate(self, x):
        return str(x)

class SBool:
    def validate(self, s):
        if isinstance(s, bool):
            return s
        if isinstance(s, str):
            sl = str(s).lower()
            if sl in ["1", "true", "yes"]:
                return True
            if sl in ["0", "false", "no"]:
                return False
            raise PresetError(f"Uknown boolean value '{s}'")
        raise RuntimeError(f"Got {s}, expected boolean value")

class SHJustify:
    def validate(self, s):
        choices = {
            "left": EDA_TEXT_HJUSTIFY_T.GR_TEXT_HJUSTIFY_LEFT,
            "right": EDA_TEXT_HJUSTIFY_T.GR_TEXT_HJUSTIFY_RIGHT,
            "center": EDA_TEXT_HJUSTIFY_T.GR_TEXT_HJUSTIFY_CENTER
        }
        if s in choices:
            return choices[s]
        raise PresetError(f"'{s}' is not valid justification value")

class SHVJustify:
    def validate(self, s):
        choices = {
            "top": EDA_TEXT_VJUSTIFY_T.GR_TEXT_VJUSTIFY_TOP,
            "center": EDA_TEXT_VJUSTIFY_T.GR_TEXT_VJUSTIFY_CENTER,
            "bottom": EDA_TEXT_VJUSTIFY_T.GR_TEXT_VJUSTIFY_BOTTOM
        }
        if s in choices:
            return choices[s]
        raise PresetError(f"'{s}' is not valid justification value")

class SChoice:
    def __init__(self, vals):
        self.vals = vals

    def validate(self, s):
        if s not in self.vals:
            c = ", ".join(self.vals)
            raise PresetError(f"'{s}' is not allowed Use one of {c}.")
        return s

class SLayer:
    def validate(self, s):
        if isinstance(s, int):
            if s in tuple(item.value for item in Layer):
                return Layer(s)
            raise RuntimeError(f"{s} is not a valid layer number")
        if isinstance(s, str):
            return Layer[s.replace(".", "_")]
        raise RuntimeError(f"Got {s}, expected layer name or number")

def validateSection(name, sectionDefinition, section):
    try:
        for key, validator in sectionDefinition.items():
            if key not in section:
                continue
            section[key] = validator.validate(section[key])
    except Exception as e:
        raise PresetError(f"Error in section {name}: {e}")
    return section

LAYOUT_SECTION = {
    "type": SChoice(["grid"]),
    "alternation": SChoice(["none", "rows", "cols", "rowsCols"]),
    "hspace": SLength(),
    "vspace": SLength(),
    "space": SLength(),
    "hbackbone": SLength(),
    "vbackbone": SLength(),
    "rotation": SAngle(),
    "rows": SNum(),
    "cols": SNum(),
    "vbonecut": SBool(),
    "hbonecut": SBool()
}

def ppLayout(section):
    section = validateSection("layout", LAYOUT_SECTION, section)
    # The space parameter overrides hspace and vspace
    if "space" in section:
        section["hspace"] = section["vspace"] = section["space"]

SOURCE_SECTION = {
    "type": SChoice(["auto", "rectangle", "annotation"]),
    "tolerance": SLength(),
    "tlx": SLength(),
    "tly": SLength(),
    "brx": SLength(),
    "bry": SLength(),
    "ref": SStr(),
    "stack": SChoice(["inherit", "2layer", "4layer", "6layer"])
}

def ppSource(section):
    section = validateSection("source", SOURCE_SECTION, section)

TABS_SECTION = {
    "type": SChoice(["none", "fixed", "spacing", "full", "corner", "annotation"]),
    "vwidth": SLength(),
    "hwidth": SLength(),
    "width": SLength(),
    "mindistance": SLength(),
    "spacing": SLength(),
    "vcount": SNum(),
    "hcount": SNum()
}

def ppTabs(section):
    section = validateSection("tabs", TABS_SECTION, section)
    if "width" in section:
        section["vwidth"] = section["hwidth"] = section["width"]

CUTS_SECTION = {
    "type": SChoice(["none", "mousebites", "vcuts"]),
    "drill": SLength(),
    "spacing": SLength(),
    "offset": SLength(),
    "prolong": SLength(),
    "clearance": SLength(),
    "threshold": SLength(),
    "cutcurves": SBool(),
    "layer": SLayer()
}

def ppCuts(section):
    section = validateSection("cuts", CUTS_SECTION, section)

FRAMING_SECTION = {
    "type": SChoice(["none", "railstb", "railslr", "frame", "tightframe"]),
    "hspace": SLength(),
    "vspace": SLength(),
    "space": SLength(),
    "width": SLength(),
    "slotwidth": SLength(),
    "cuts": SChoice(["none", "both", "v", "h"]),
    "cutcurves": SBool(),
    "layer": SLayer()
}

def ppFraming(section):
    section = validateSection("framing", FRAMING_SECTION, section)
    # The space parameter overrides hspace and vspace
    if "space" in section:
        section["hspace"] = section["vspace"] = section["space"]

TOOLING_SECTION = {
    "type": SChoice(["none", "3hole", "4hole"]),
    "hoffset": SLength(),
    "voffset": SLength(),
    "size": SLength(),
    "paste": SBool()
}

def ppTooling(section):
    section = validateSection("tooling", TOOLING_SECTION, section)

FIDUCIALS_SECTION = {
    "type": SChoice(["none", "3fid", "4fid"]),
    "hoffset": SLength(),
    "voffset": SLength(),
    "coppersize": SLength(),
    "opening": SLength()
}

def ppFiducials(section):
    section = validateSection("fiducials", FIDUCIALS_SECTION, section)

TEXT_SECTION = {
    "type": SChoice(["none", "simple"]),
    "hoffset": SLength(),
    "voffset": SLength(),
    "width": SLength(),
    "height": SLength(),
    "thickness": SLength(),
    "hjustify": SHJustify(),
    "vjustify": SHJustify(),
    "layer": SLayer(),
    "orientation": SAngle(),
    "text": SStr(),
    "anchor": SChoice(ANCHORS)
}

def ppText(section):
    section = validateSection("text", TEXT_SECTION, section)

POST_SECTION = {
    "type": SChoice(["auto"]),
    "copperfill": SBool(),
    "millradius": SLength(),
    "script": SStr(),
    "scriptarg": SStr(),
    "origin": SChoice(ANCHORS + [""])
}

def ppPost(section):
    section = validateSection("post", POST_SECTION, section)

DEBUG_SECTION = {
    "type": SChoice(["none"]),
    "drawPartitionLines": SBool(),
    "drawBackboneLines": SBool(),
    "drawboxes": SBool(),
    "trace": SBool()
}

def ppDebug(section):
    section = validateSection("debug", DEBUG_SECTION, section)