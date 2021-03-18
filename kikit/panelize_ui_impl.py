from kikit.panelize_ui import Section, PresetError
from kikit.panelize import *
from kikit.defs import Layer
from shapely.geometry import box
from kikit.units import readLength, readAngle
from kikit.substrate import SubstrateNeighbors
import commentjson

# This package exists as it is not needed for showing help and running other
# commands, however, it has heavy dependencies (pcbnew) that take a second
# to load. Splitting it speeds up KiKit's startup.

PKG_BASE = os.path.dirname(__file__)
PRESET_LIB = os.path.join(PKG_BASE, "resources/panelizePresets")

def splitStr(splitChar, escapeChar, s):
    """
    Splits s based on splitChar that can be escaped via escapeChar
    """
    # TBA
    return s.split(splitChar)

def validatePresetLayout(preset):
    if not isinstance(preset, dict):
        raise PresetError("Preset is not a dictionary")
    for name, section in preset.items():
        if not isinstance(section, dict):
            raise PresetError(f"Section '{name}' is not a dictionary")

def validateChoice(sectionName, section, key, choices):
    if section[key] not in choices:
        c = ", ".join(choices)
        raise PresetError(f"'{section[key]}' is not allowed for {sectionName}.{key}. Use one of {c}.")

def readParameters(section, method, what):
    for x in what:
        if x in section:
            section[x] = method(section[x])

def readLayer(s):
    return Layer[s.replace(".", "_")]

def ppLayout(section):
    validateChoice("layout", section, "type", ["grid", "tightgrid"])
    validateChoice("layout", section, "alternation",
        ["none", "rows", "cols", "rowsCols"])
    readParameters(section, readLength,
        ["hspace", "vspace", "space", "slotwidth"])
    readParameters(section, readAngle, ["rotation"])
    readParameters(section, int, ["rows", "cols"])
    # The space parameter overrides hspace and vspace
    if "space" in section:
        section["hspace"] = section["vspace"] = section["space"]

def ppSource(section):
    validateChoice("source", section, "type", ["auto"])
    readParameters(section, readLength,
        ["tolerance", "x", "y", "w", "h"])

def ppTabs(section):
    validateChoice("tabs", section, "type", ["auto", "full", "attribute"])
    readParameters(section, readLength, ["vwidth", "hwidth", "width"])
    readParameters(section, int, ["vcount", "hcount"])
    if "width" in section:
        section["vwidth"] = section["hwidth"] = section["width"]

def ppCuts(section):
    validateChoice("cuts", section, "type", ["none", "mousebites", "vcuts"])
    readParameters(section, readLength, ["drill", "spacing", "offset",
        "prolong", "clearance", "threshold"])
    readParameters(section, bool, ["cutcurves"])
    readParameters(section, readLayer, ["layer"])

def ppFraming(section):
    pass

def ppTooling(section):
    pass

def postProcessPreset(preset):
    process = {
        "layout": ppLayout,
        "source": ppSource,
        "tabs": ppTabs,
        "cuts": ppCuts,
        "framing": ppFraming,
        "tooling": ppTooling
    }
    for name, section in preset.items():
        process[name](section)

def loadPreset(path):
    """
    Load a preset from path and perform simple validation on its structure.
    Automatically resolves built-in styles (prefixed with :, omitting suffix).
    """
    if path.startswith(":"):
        presetName = path
        path = os.path.join(PRESET_LIB, path[1:] + ".json")
        if not os.path.exists(path):
            raise RuntimeError(f"Uknown built-in preset '{presetName}'")
    try:
        with open(path, "r") as f:
            preset = commentjson.load(f)
            validatePresetLayout(preset)
            return preset
    except OSError as e:
        raise RuntimeError(f"Cannot open preset '{path}'")
    except PresetError as e:
        raise PresetError(f"{path}: {e}")

def mergePresets(a, b):
    """
    Merge b into a. Values from b overwrite values from a.
    """
    for category in b:
        if category not in a:
            a[category] = {}
        for key, value in b[category].items():
            a[category][key] = value

def loadPresetChain(chain):
    """
    Given a list of preset names (or paths), load the whole chain.
    """
    assert len(chain) > 0

    preset = loadPreset(chain[0])
    for p in chain[1:]:
        newPreset = loadPreset(p)
        mergePresets(preset, newPreset)
    return preset

def validateSections(preset):
    """
    Perform a logic validation of the given preset - e.g., if a style is applied,
    validate all required keys are present. Ignores excessive keys.
    """
    VALID_SECTIONS = ["layout", "source", "tabs", "cuts", "framing", "tooling"]
    extraSections = set(preset.keys()).difference(VALID_SECTIONS)
    if len(extraSections) != 0:
        raise PresetError(f"Extra sections {', '.join(extraSections)} in preset")
    missingSections = set(VALID_SECTIONS).difference(preset.keys())
    if len(missingSections) != 0:
        raise PresetError(f"Missing sections {', '.join(extraSections)} in preset")

def getPlacementClass(name):
    from kikit.panelize import (BasicGridPosition, OddEvenColumnPosition,
        OddEvenRowsPosition, OddEvenRowsColumnsPosition)
    mapping = {
        "none": BasicGridPosition,
        "rows": OddEvenRowsPosition,
        "cols": OddEvenColumnPosition,
        "rowsCols": OddEvenRowsColumnsPosition
    }
    try:
        return mapping[name]
    except KeyError:
        raise RuntimeError(f"Invalid alternation option '{name}' passed. " +
            "Valid options are: " + ", ".join(mapping.keys()))

def readSourceArea(specification, board):
    """
    Extract source area based on preset and a board.
    """
    type = specification["type"]
    if type == "auto":
        tolerance = specification.get("tolerance", 0)
        return expandRect(findBoardBoundingBox(board), tolerance)
    raise PresetError(f"Unknown type '{type}' of source specification.")

def obtainPreset(presetPaths, **kwargs):
    """
    Given a preset paths from the user and the overrides in the form of named
    arguments, construt the preset.

    Ensures a valid preset is always found
    """
    presetChain = [":default"] + list(presetPaths)
    preset = loadPresetChain(presetChain)
    for name, section in kwargs.items():
        if section is not None:
            mergePresets(preset, {name: section})
    validateSections(preset)
    postProcessPreset(preset)
    return preset

def buildLayout(layout, panel, sourceBoard, sourceArea):
    """
    Build layout for the boards - e.g., make a grid out of them.

    Return the list of created substrates.
    """
    type = layout["type"]
    if type in ["grid", "tightgrid"]:
        placementClass = getPlacementClass(layout["alternation"])
        return panel.makeGridNew(
            boardfile=sourceBoard, sourceArea=sourceArea,
            rows=layout["rows"], cols=layout["cols"], destination=wxPointMM(50, 50),
            rotation=layout["rotation"],
            verSpace=layout["vspace"], horSpace=layout["hspace"],
            placementClass=placementClass,
            netRenamePattern=layout["renamenet"], refRenamePattern=layout["renameref"])
    raise PresetError(f"Unknown type '{type}' of layout specification.")

def buildInnerTabs(properties, panel, substrates):
    """
    Build tabs for the substrates in between the boards. Return a list of cuts.
    """
    type = properties["type"]
    if type == "auto":
        return buildInnerTabsAuto(properties, panel, substrates)
    if type == "full":
        return buildInnerTabsFull(properties, panel, substrates)
    if type == "annotation":
        return buildInnerTabsAnnotation(properties, panel, substrates)
    raise PresetError(f"Unknown type '{type}' of tabs specification.")

def buildSideTabs(substrate, dir, side1, side2, count, width, tabs, cuts):
    """
    Builds a tab on a side. Just specify the reference substrate (specifies the
    cut shape), direction, two sides of the neighboring substrates (the result
    of shpBBox* functions). The direction should be either [±1, 0] or [0, ±1]

    The cuts and tabs are placed into the corresponding lists.
    """
    x1, e1 = side1
    x2, e2 = side2
    x = (x1 + x2) // 2
    e = e1.intersect(e2)
    coeff = [abs(n) for n in dir]
    for y in tabSpacing(e.length, count):
        # Multiplication with absolute value of direction distinguishes
        # vertical and horizontal tab
        origin = wxPoint(x * coeff[0] + coeff[1] * (e.min + y), x * coeff[1] + coeff[0] * (e.min + y))
        t, c = substrate.tab(origin, dir, width)
        tabs.append(t)
        # Append a cut only if the boards are sufficiently apart. Otherwise, use
        # e as a cut...
        if (abs(x1 - x2) < fromMm(0.01)):
            if x1 - x2 < 0: # ... but only when the direction is bottom or left
                cuts.append(LineString([
                    (x * coeff[0] + coeff[1] * e.min, x * coeff[1] + coeff[0] * e.min),
                    (x * coeff[0] + coeff[1] * e.max, x * coeff[1] + coeff[0] * e.max)
                ]))
        else:
            cuts.append(c)

def buildInnerTabsAuto(properties, panel, substrates):
    """
    Build the "auto" type of inner tabs
    """
    tabs = []
    cuts = []
    neighbors = SubstrateNeighbors(substrates)
    for s in substrates:
        for n in neighbors.left(s):
            buildSideTabs(s, [1, 0], shpBBoxLeft(s.bounds()), shpBBoxRight(n.bounds()),
                properties["hcount"], properties["hwidth"], tabs, cuts)
        for n in neighbors.right(s):
            buildSideTabs(s, [-1, 0], shpBBoxRight(s.bounds()), shpBBoxLeft(n.bounds()),
                properties["hcount"], properties["hwidth"], tabs, cuts)
        for n in neighbors.top(s):
            buildSideTabs(s, [0, 1], shpBBoxTop(s.bounds()), shpBBoxBottom(n.bounds()),
                properties["vcount"], properties["vwidth"], tabs, cuts)
        for n in neighbors.bottom(s):
            buildSideTabs(s, [0, -1], shpBBoxBottom(s.bounds()), shpBBoxTop(n.bounds()),
                properties["vcount"], properties["vwidth"], tabs, cuts)
    tabs = list([t.buffer(fromMm(0.01), join_style=2) for t in tabs])
    panel.appendSubstrate(tabs)
    return cuts

def buildInnerTabsFull(properties, panel, substrates):
    """
    Build the "full" type of inner tabs
    """
    tabs = []
    cuts = []
    neighbors = SubstrateNeighbors(substrates)
    for s in substrates:
        for n in neighbors.left(s):
            l = shpBBoxLeft(s.bounds())
            buildSideTabs(s, [1, 0], l, shpBBoxRight(n.bounds()),
                1, l[1].length - fromMm(0.01), tabs, cuts)
        for n in neighbors.right(s):
            l = shpBBoxRight(s.bounds())
            buildSideTabs(s, [-1, 0], l, shpBBoxLeft(n.bounds()),
                1, l[1].length - fromMm(0.01), tabs, cuts)
        for n in neighbors.top(s):
            l = shpBBoxTop(s.bounds())
            buildSideTabs(s, [0, 1], l, shpBBoxBottom(n.bounds()),
                1, l[1].length - fromMm(0.01), tabs, cuts)
        for n in neighbors.bottom(s):
            l = shpBBoxBottom(s.bounds())
            buildSideTabs(s, [0, -1], l, shpBBoxTop(n.bounds()),
                1, l[1].length - fromMm(0.01), tabs, cuts)
    # Compute the bounding box gap polygon
    bBoxes = box(*substrates[0].bounds())
    for s in substrates:
        bBoxes = bBoxes.union(box(*s.bounds()))
    outerBox = box(*bBoxes.bounds)
    fill = outerBox.difference(bBoxes)
    tabs.append(fill)

    # Append tabs
    tabs = list([t.buffer(fromMm(0.01), join_style=2) for t in tabs])
    panel.appendSubstrate(tabs)
    return cuts

def buildInnerTabsAnnotation(properties, panel, substrates):
    """
    Build the "annotation" type of inner tabs
    """
    pass
    # TBA


def buildBackBone(layout, panel, substrates):
    """
    Append backbones to the panel
    """
    pass
    # TBA

def makeCuts(properties, panel, cuts):
    """
    Perform cuts
    """
    type = properties["type"]
    if type == "none":
        return
    if type == "vcuts":
        panel.makeVCuts(cuts, properties["cutcurves"])
        panel.setVCutLayer(properties["layer"])
        panel.setVCutClearance(properties["clearance"])
    elif type == "mousebites":
        panel.makeMouseBites(cuts, properties["drill"],
            properties["spacing"], properties["offset"], properties["prolong"])
    else:
        raise PresetError(f"Unknown type '{type}' of cuts specification.")
