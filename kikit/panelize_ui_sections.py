from dataclasses import dataclass
import os
from typing import Any, List
from kikit import plugin
from kikit.units import readLength, readAngle
from kikit.defs import Layer, EDA_TEXT_HJUSTIFY_T, EDA_TEXT_VJUSTIFY_T, PAPER_SIZES

class PresetError(RuntimeError):
    pass

ANCHORS = ["tl", "tr", "bl", "br", "mt", "mb", "ml", "mr", "c"]
PAPERS = ["inherit"] + PAPER_SIZES + ["user"]

@dataclass
class FootprintId:
    lib: str
    footprint: str

class SectionBase:
    def __init__(self, isGuiRelevant, description):
        self.description = description
        self.isGuiRelevant = isGuiRelevant

    def validate(self, x: str) -> Any:
        raise NotImplementedError("Validate was not overridden for SectionBase")

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

class SPlugin(SectionBase):
    seq: int = 0

    def __init__(self, pluginType, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pluginType = pluginType

    def validate(self, x):
        if x == "none":
            return None
        self.seq += 1

        pieces = str(x).rsplit(".", maxsplit=1)
        if len(pieces) != 2:
            raise RuntimeError(f"Invalid plugin specification '{x}'")
        moduleName, pluginName = pieces[0], pieces[1]
        plugin = self.loadFromFile(moduleName, pluginName) if moduleName.endswith(".py") \
                 else self.loadFromModule(moduleName, pluginName)
        if not issubclass(plugin, self.pluginType):
            raise RuntimeError(f"Invalid plugin type specified, {self.pluginType.__name__} expected")
        setattr(plugin, "__kikit_preset_repr", x)
        return plugin

    def loadFromFile(self, file, name):
        import importlib.util

        if not os.path.exists(file):
            raise RuntimeError(f"File {file} doesn't exist")
        spec = importlib.util.spec_from_file_location(
                f"kikit.user.SPlugin_{self.seq}",
                file)
        if spec is None:
            raise RuntimeError(f"Plugin module '{file}' doesn't exist")
        pluginModule = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(pluginModule)
        return getattr(pluginModule, name)

    def loadFromModule(self, module, name):
        import importlib
        pluginModule = importlib.import_module(module)
        return getattr(pluginModule, name)

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
        raise PresetError(f"Got {s}, expected boolean value")

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
            raise PresetError(f"{s} is not a valid layer number")
        if isinstance(s, str):
            return Layer[s.replace(".", "_")]
        raise PresetError(f"Got {s}, expected layer name or number")

class SList(SectionBase):
    def validate(self, x: str) -> Any:
        return [v.strip() for v in x.split(",")]

class SLayerList(SList):
    def __init__(self, isGuiRelevant, description, shortcuts={}):
        super().__init__(isGuiRelevant, description)
        self._shortcuts = shortcuts

    def validate(self, x: str) -> Any:
        if x in self._shortcuts:
            return self._shortcuts[x]
        return [self.readLayer(x) for x in super().validate(x)]

    def readLayer(self, s: str) -> Layer:
        if isinstance(s, int):
            if s in tuple(item.value for item in Layer):
                return Layer(s)
            raise PresetError(f"{s} is not a valid layer number")
        if isinstance(s, str):
            return Layer[s.replace(".", "_")]
        raise PresetError(f"Got {s}, expected layer name or number")

class SFootprintList(SList):
    def validate(self, x: str) -> Any:
        result: List[FootprintId] = []
        for v in super().validate(x):
            s = v.split(":", 1)
            if len(s) != 2:
                PresetError(f"'{v}' is not a valid footprint name in the form '<lib>:<footprint>'")
            result.append(FootprintId(s[0], s[1]))
        return result


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
        ["grid", "plugin"],
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
        typeIn(["grid"]),
        "The width of horizontal backbone (0 means no backbone)"),
    "vbackbone": SLength(
        typeIn(["grid"]),
        "The width of vertical backbone (0 means no backbone)"),
    "hboneskip": SNum(
        typeIn(["grid"]),
        "Skip every given number of horizontal backbones"),
    "vboneskip": SNum(
        typeIn(["grid"]),
        "Skip every given number of vertical backbones"),
    "rotation": SAngle(
        always(),
        "Rotate the boards before placing them in the panel"),
    "rows": SNum(
        typeIn(["grid"]),
        "Specify the number of boards in the grid pattern"),
    "cols": SNum(
        typeIn(["grid"]),
        "Specify the number of boards in the grid pattern"),
    "vbonecut": SBool(
        typeIn(["grid"]),
        "Cut backone in vertical direction"),
    "hbonecut": SBool(
        typeIn(["grid"]),
        "Cut backone in horizontal direction"),
    "renamenet": SStr(
        always(),
        "Net renaming pattern"),
    "renameref": SStr(
        always(),
        "Reference renaming pattern"),
    "baketext": SBool(
        always(),
        "Substitute variables in text elements"
    ),
    "code": SPlugin(
        plugin.LayoutPlugin,
        typeIn(["plugin"]),
        "Plugin specification as moduleName.pluginName"),
    "arg": SStr(
        typeIn(["plugin"]),
        "String argument for the layout plugin")
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
        ["none", "fixed", "spacing", "full", "corner", "annotation", "plugin"],
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
        "Number of tabs in a given direction."),
    "cutout": SLength(
        typeIn(["fixed"]),
        "Depth of cutouts into the frame"),
    "tabfootprints": SFootprintList(
        typeIn(["annotation"]),
        "Specify custom footprints that will be used for tab annotations."),
    "code": SPlugin(
        plugin.TabsPlugin,
        typeIn(["plugin"]),
        "Plugin specification as moduleName.pluginName"),
    "arg": SStr(
        typeIn(["plugin"]),
        "String argument for the layout plugin")
}

def ppTabs(section):
    section = validateSection("tabs", TABS_SECTION, section)
    if "width" in section:
        section["vwidth"] = section["hwidth"] = section["width"]

CUTS_SECTION = {
    "type": SChoice(
        ["none", "mousebites", "vcuts", "layer", "plugin"],
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
        typeIn(["mousebites", "layer"]),
        "Tangentiall prolong cuts (to cut mill fillets)"),
    "clearance": SLength(
        typeIn(["vcuts"]),
        "Add copper clearance around V-cuts"),
    "cutcurves": SBool(
        typeIn(["vcuts"]),
        "Approximate curves with straight cut"),
    "layer": SLayer(
        typeIn(["vcuts", "layer"]),
        "Specify layer for the drawings"),
    "code": SPlugin(
        plugin.CutsPlugin,
        typeIn(["plugin"]),
        "Plugin specification as moduleName.pluginName"),
    "arg": SStr(
        typeIn(["plugin"]),
        "String argument for the layout plugin")
}

def ppCuts(section):
    section = validateSection("cuts", CUTS_SECTION, section)

FRAMING_SECTION = {
    "type": SChoice(
        ["none", "railstb", "railslr", "frame", "tightframe", "plugin"],
        always(),
        "Framing type"),
    "hspace": SLength(
        typeIn(["frame", "railslr", "tightframe"]),
        "Horizontal space between PCBs and the frame"),
    "vspace": SLength(
        typeIn(["frame", "railstb", "tightframe"]),
        "Vertical space between PCBs and the frame"),
    "space": SLength(
        never(),
        "Space between frame/rails and PCBs"),
    "width": SLength(
        typeIn(["frame", "railstb", "railslr", "tightframe"]),
        "Width of the framing"),
    "mintotalheight": SLength(
        typeIn(["frame", "railstb", "tightframe"]),
        "Minimal height of the panel"
    ),
    "mintotalwidth": SLength(
        typeIn(["frame", "raillr", "tightframe"]),
        "Minimal width of the panel"
    ),
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
    "code": SPlugin(
        plugin.FramingPlugin,
        typeIn(["plugin"]),
        "Plugin specification as moduleName.pluginName"),
    "arg": SStr(
        typeIn(["plugin"]),
        "String argument for the layout plugin")
}

def ppFraming(section):
    section = validateSection("framing", FRAMING_SECTION, section)
    # The space parameter overrides hspace and vspace
    if "space" in section:
        section["hspace"] = section["vspace"] = section["space"]

TOOLING_SECTION = {
    "type": SChoice(
        ["none", "3hole", "4hole", "plugin"],
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
        "Include holes on the paste layer"),
    "code": SPlugin(
        plugin.ToolingPlugin,
        typeIn(["plugin"]),
        "Plugin specification as moduleName.pluginName"),
    "arg": SStr(
        typeIn(["plugin"]),
        "String argument for the layout plugin")
}

def ppTooling(section):
    section = validateSection("tooling", TOOLING_SECTION, section)

FIDUCIALS_SECTION = {
    "type": SChoice(
        ["none", "3fid", "4fid", "plugin"],
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
        "Diameter of the opening"),
    "code": SPlugin(
        plugin.FiducialsPlugin,
        typeIn(["plugin"]),
        "Plugin specification as moduleName.pluginName"),
    "arg": SStr(
        typeIn(["plugin"]),
        "String argument for the layout plugin")
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
        "Anchor for positioning the text"),
    "plugin": SPlugin(
        plugin.TextVariablePlugin,
        typeIn(["simple"]),
        "Plugin for extra text variables")
}

def ppText(section):
    section = validateSection("text", TEXT_SECTION, section)

COPPERFILL_SECTION = {
    "type": SChoice(
        ["none", "solid", "hatched"],
        always(),
        "Fill non board areas with copper"),
    "clearance": SLength(
        typeIn(["solid", "hatched"]),
        "Clearance between the fill and boards"),
    "layers": SLayerList(
        typeIn(["solid", "hatched"]),
        "Specify which layer to fill with copper",
        {
            "all": Layer.allCu()
        }),
    "width": SLength(
        typeIn(["hatched"]),
        "Width of hatch strokes"),
    "spacing": SLength(
        typeIn(["hatched"]),
        "Spacing of hatch strokes"),
    "orientation": SAngle(
        typeIn(["hatched"]),
        "Orientation of the strokes"
    )
}

def ppCopper(section):
    section = validateSection("copperfill", COPPERFILL_SECTION, section)

POST_SECTION = {
    "type": SChoice(
        ["auto"],
        never(),
        "Postprocessing type"),
    "copperfill": SBool(
        always(),
        "DEPRECATED, use section copperfill instead. Fill unused areas of the panel with copper"),
    "millradius": SLength(
        always(),
        "Simulate milling operation"),
    "reconstructarcs": SBool(
        always(),
        "Try to reconstruct arcs"),
    "refillzones": SBool(
        always(),
        "Refill all zones in the panel"),
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

PAGE_SECTION = {
    "type": SChoice(
        PAPERS,
        always(),
        "Size of paper"),
    "anchor": SChoice(
        ANCHORS,
        always(),
        "Anchor for positioning the panel on the page"),
    "posx": SLength(
        always(),
        "X position of the panel"),
    "posy": SLength(
        always(),
        "Y position of the panel"),
    "width": SLength(
        typeIn(["user"]),
        "Width of custom paper"),
    "height": SLength(
        typeIn(["user"]),
        "Height of custom paper"),
}

def ppPage(section):
    section = validateSection("page", PAGE_SECTION, section)

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
    "drawtabfail": SBool(
        always(),
        "Visualize tab building failures"
    ),
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
    "Text2": TEXT_SECTION,
    "Text3": TEXT_SECTION,
    "Text4": TEXT_SECTION,
    "Copperfill": COPPERFILL_SECTION,
    "Page": PAGE_SECTION,
    "Post": POST_SECTION,
    "Debug": DEBUG_SECTION,
}
