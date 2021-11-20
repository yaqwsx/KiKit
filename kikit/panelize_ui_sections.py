from kikit.units import readLength, readAngle
from kikit.defs import Layer, EDA_TEXT_HJUSTIFY_T, EDA_TEXT_VJUSTIFY_T

class PresetError(RuntimeError):
    pass

ANCHORS = ["tl", "tr", "bl", "br", "mt", "mb", "ml", "mr", "c"]

class SectionBase:
    def __init__(self, isGuiRelevant, description):
        self.description = description
        self.isGuiRelevant = isGuiRelevant

class SLength(SectionBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def validate(self, x):
        return readLength(x)

class SAngle(SectionBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def validate(self, x):
        return readAngle(x)

class SNum(SectionBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def validate(self, x):
        return int(x)

class SStr(SectionBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def validate(self, x):
        return str(x)

class SChoiceBase(SectionBase):
    def __init__(self, vals, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.vals = vals

    def validate(self, s):
        if s not in self.vals:
            c = ", ".join(self.vals)
            raise PresetError(f"'{s}' is not allowed Use one of {c}.")
        return s

class SChoice(SChoiceBase):
    def __init__(self, vals, *args, **kwargs):
        super().__init__(vals, *args, **kwargs)

class SBool(SChoiceBase):
    def __init__(self, *args, **kwargs):
        super().__init__(["True", "False"], *args, **kwargs)

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

class SHJustify(SChoiceBase):
    def __init__(self, *args, **kwargs):
        super().__init__(["left", "right", "center"], *args, **kwargs)

    def validate(self, s):
        choices = {
            "left": EDA_TEXT_HJUSTIFY_T.GR_TEXT_HJUSTIFY_LEFT,
            "right": EDA_TEXT_HJUSTIFY_T.GR_TEXT_HJUSTIFY_RIGHT,
            "center": EDA_TEXT_HJUSTIFY_T.GR_TEXT_HJUSTIFY_CENTER
        }
        if s in choices:
            return choices[s]
        raise PresetError(f"'{s}' is not valid justification value")

class SHVJustify(SChoiceBase):
    def __init__(self, *args, **kwargs):
        super().__init__(["top", "bottom", "center"], *args, **kwargs)

    def validate(self, s):
        choices = {
            "top": EDA_TEXT_VJUSTIFY_T.GR_TEXT_VJUSTIFY_TOP,
            "center": EDA_TEXT_VJUSTIFY_T.GR_TEXT_VJUSTIFY_CENTER,
            "bottom": EDA_TEXT_VJUSTIFY_T.GR_TEXT_VJUSTIFY_BOTTOM
        }
        if s in choices:
            return choices[s]
        raise PresetError(f"'{s}' is not valid justification value")

class SLayer(SChoiceBase):
    def __init__(self, *args, **kwargs):
        super().__init__(
            [str(item).replace("Layer.", "").replace("_", ".")
                for item in Layer], *args, **kwargs)

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

def typeIn(values):
    return lambda section: section["type"] in values

def always():
    return lambda section: True

def never():
    return lambda section: False

LAYOUT_SECTION = {
    "type": SChoice(
        ["grid"],
        always(),
        "Layout type"),
    "alternation": SChoice(
        ["none", "rows", "cols", "rowsCols"],
        typeIn(["grid"]),
        "Specify alternations of board rotation"),
    "hspace": SLength(
        always(),
        "Specify horizontal gap between the boards"),
    "vspace": SLength(
        always(),
        "Specify vertical gap between the boards"),
    "space": SLength(
        never(),
        "Specify the gap between the boards in both direction"),
    "hbackbone": SLength(
        always(),
        "The width of vertical and horizontal backbone (0 means no backbone)"),
    "vbackbone": SLength(
        always(),
        "The width of vertical and horizontal backbone (0 means no backbone)"),
    "rotation": SAngle(
        always(),
        "Rotate the boards before placing them in the panel"),
    "rows": SNum(
        always(),
        "Specify the number of boards in the grid pattern"),
    "cols": SNum(
        always(),
        "Specify the number of boards in the grid pattern"),
    "vbonecut": SBool(
        always(),
        "Cut backone in vertical direction"),
    "hbonecut": SBool(
        always(),
        "Cut backone in horizontal direction"),
    "renamenet": SStr(
        always(),
        "Net renaming pattern"
    ),
    "renameref": SStr(
        always(),
        "Reference renaming pattern"
    )
}

def ppLayout(section):
    section = validateSection("layout", LAYOUT_SECTION, section)
    # The space parameter overrides hspace and vspace
    if "space" in section:
        section["hspace"] = section["vspace"] = section["space"]

SOURCE_SECTION = {
    "type": SChoice(
        ["auto", "rectangle", "annotation"],
        always(),
        "Source type"),
    "tolerance": SLength(
        typeIn(["auto", "annotation"]),
        "Tolerance enlarges the source area by given amount"),
    "tlx": SLength(
        typeIn(["rectangle"]),
        "Corner of the rectangle"),
    "tly": SLength(
        typeIn(["rectangle"]),
        "Corner of the rectangle"),
    "brx": SLength(
        typeIn(["rectangle"]),
        "Corner of the rectangle"),
    "bry": SLength(
        typeIn(["rectangle"]),
        "Corner of the rectangle"),
    "ref": SStr(
        typeIn(["annotation"]),
        "Specify reference of KiKit annotation symbol"),
    "stack": SChoice(
        ["inherit", "2layer", "4layer", "6layer"],
        always(),
        "Specify the number of layers of the panel")
}

def ppSource(section):
    section = validateSection("source", SOURCE_SECTION, section)

TABS_SECTION = {
    "type": SChoice(
        ["none", "fixed", "spacing", "full", "corner", "annotation"],
        always(),
        "Tab type"),
    "vwidth": SLength(
        typeIn(["fixed", "spacing"]),
        "Specify width of vertical tabs"),
    "hwidth": SLength(
        typeIn(["fixed", "spacing"]),
        "Specify width of vertical tabs"),
    "width": SLength(
        typeIn(["corner"]),
        "Specify tab width"),
    "mindistance": SLength(
        typeIn(["fixed"]),
        "Minimal spacing between the tabs. If there are too many tabs, their count is reduced."),
    "spacing": SLength(
        typeIn(["spacing"]),
        "The maximum spacing of the tabs."),
    "vcount": SNum(
        typeIn(["fixed"]),
        "Number of tabs in a given direction."),
    "hcount": SNum(
        typeIn(["fixed"]),
        "Number of tabs in a given direction.")
}

def ppTabs(section):
    section = validateSection("tabs", TABS_SECTION, section)
    if "width" in section:
        section["vwidth"] = section["hwidth"] = section["width"]

CUTS_SECTION = {
    "type": SChoice(
        ["none", "mousebites", "vcuts"],
        always(),
        "Cut type"),
    "drill": SLength(
        typeIn(["mousebites"]),
        "Drill diameter"),
    "spacing": SLength(
        typeIn(["mousebites"]),
        "Hole spacing"),
    "offset": SLength(
        typeIn(["mousebites", "vcuts"]),
        "Offset cuts into the board"),
    "prolong": SLength(
        typeIn(["mousebites"]),
        "Tangentiall prolong cuts (to cut mill fillets)"),
    "clearance": SLength(
        typeIn(["vcuts"]),
        "Add copper clearance around V-cuts"),
    "cutcurves": SBool(
        typeIn(["vcuts"]),
        "Approximate curves with straight cut"),
    "layer": SLayer(
        typeIn(["vcuts"]),
        "Draw V-cuts into a specified layer")
}

def ppCuts(section):
    section = validateSection("cuts", CUTS_SECTION, section)

FRAMING_SECTION = {
    "type": SChoice(
        ["none", "railstb", "railslr", "frame", "tightframe"],
        always(),
        "Framing type"),
    "hspace": SLength(
        typeIn(["frame", "railslr"]),
        "Horizontal space between PCBs and the frame"),
    "vspace": SLength(
        typeIn(["frame", "railstb"]),
        "Vertical space between PCBs and the frame"),
    "space": SLength(
        never(),
        "Space between frame/rails and PCBs"),
    "width": SLength(
        typeIn(["frame", "railstb", "railslr", "tightframe"]),
        "Width of the framing"),
    "slotwidth": SLength(
        typeIn(["tightframe"]),
        "Width of the milled slot"),
    "cuts": SChoice(
        ["none", "both", "v", "h"],
        typeIn(["frame"]),
        "Add cuts to the corners of the frame"),
    "chamfer": SLength(
        typeIn(["tightframe", "frame", "railslr", "railstb"]),
        "Add chamfer to the 4 corners of the panel. Specify chamfer width."),
    "fillet": SLength(
        typeIn(["tightframe", "frame", "railslr", "railstb"]),
        "Add fillet to the 4 corners of the panel. Specify fillet radius."),
}

def ppFraming(section):
    section = validateSection("framing", FRAMING_SECTION, section)
    # The space parameter overrides hspace and vspace
    if "space" in section:
        section["hspace"] = section["vspace"] = section["space"]

TOOLING_SECTION = {
    "type": SChoice(
        ["none", "3hole", "4hole"],
        always(),
        "Tooling type"),
    "hoffset": SLength(
        typeIn(["3hole", "4hole"]),
        "Horizontal offset for the hole"),
    "voffset": SLength(
        typeIn(["3hole", "4hole"]),
        "Vertical offset for the hole"),
    "size": SLength(
        typeIn(["3hole", "4hole"]),
        "Hole diameter"),
    "paste": SBool(
        typeIn(["3hole", "4hole"]),
        "Include holes on the paste layer")
}

def ppTooling(section):
    section = validateSection("tooling", TOOLING_SECTION, section)

FIDUCIALS_SECTION = {
    "type": SChoice(
        ["none", "3fid", "4fid"],
        always(),
        "Fiducial type"),
    "hoffset": SLength(
        typeIn(["3fid", "4fid"]),
        "Horizontal offset for the fiducial"),
    "voffset": SLength(
        typeIn(["3fid", "4fid"]),
        "Horizontal offset for the fiducial"),
    "coppersize": SLength(
        typeIn(["3fid", "4fid"]),
        "Diameter of the copper part"),
    "opening": SLength(
        typeIn(["3fid", "4fid"]),
        "Diameter of the opening")
}

def ppFiducials(section):
    section = validateSection("fiducials", FIDUCIALS_SECTION, section)

TEXT_SECTION = {
    "type": SChoice(
        ["none", "simple"],
        always(),
        "Text type"),
    "hoffset": SLength(
        typeIn(["simple"]),
        "Horizontal offset of the text from anchor"),
    "voffset": SLength(
        typeIn(["simple"]),
        "Vertical offset of the text from anchor"),
    "width": SLength(
        typeIn(["simple"]),
        "Width of a character"),
    "height": SLength(
        typeIn(["simple"]),
        "Height of a character"),
    "thickness": SLength(
        typeIn(["simple"]),
        "Thickness of a character"),
    "hjustify": SHJustify(
        typeIn(["simple"]),
        "Text alignment"),
    "vjustify": SHJustify(
        typeIn(["simple"]),
        "Text alignment"),
    "layer": SLayer(
        typeIn(["simple"]),
        "Text layer"),
    "orientation": SAngle(
        typeIn(["simple"]),
        "Orientation of the text"),
    "text": SStr(
        typeIn(["simple"]),
        "Text to render"),
    "anchor": SChoice(
        ANCHORS,
        typeIn(["simple"]),
        "Anchor for positioning the text")
}

def ppText(section):
    section = validateSection("text", TEXT_SECTION, section)

POST_SECTION = {
    "type": SChoice(
        ["auto"],
        never(),
        "Postprocessing type"),
    "copperfill": SBool(
        always(),
        "Fill unused areas of the panel with copper"),
    "millradius": SLength(
        always(),
        "Simulate milling operation"),
    "script": SStr(
        always(),
        "Specify path to a custom postprocessing script"),
    "scriptarg": SStr(
        always(),
        "String argument for the postprocessing script"),
    "origin": SChoice(
        ANCHORS + [""],
        always(),
        "Place auxiliary origin")
}

def ppPost(section):
    section = validateSection("post", POST_SECTION, section)

DEBUG_SECTION = {
    "type": SChoice(
        ["none"],
        never(),
        ""),
    "drawPartitionLines": SBool(
        always(),
        "Draw parition lines"),
    "drawBackboneLines": SBool(
        always(),
        "Draw backbone lines"),
    "drawboxes": SBool(
        always(),
        "Draw board bounding boxes"),
    "trace": SBool(
        always(),
        "Print stacktrace"),
    "deterministic": SBool(
        always(),
        "Make KiCAD IDs deterministic")
}

def ppDebug(section):
    section = validateSection("debug", DEBUG_SECTION, section)

availableSections = {
    "Layout": LAYOUT_SECTION,
    "Source": SOURCE_SECTION,
    "Tabs": TABS_SECTION,
    "Cuts": CUTS_SECTION,
    "Framing": FRAMING_SECTION,
    "Tooling": TOOLING_SECTION,
    "Fiducials": FIDUCIALS_SECTION,
    "Text": TEXT_SECTION,
    "Post": POST_SECTION,
    "Debug": DEBUG_SECTION,
}