from kikit.panelize_ui import Section, PresetError
from kikit.panelize import *
from kikit.defs import Layer
from shapely.geometry import box
from kikit.units import readLength, readAngle
from kikit.substrate import SubstrateNeighbors
from kikit.common import resolveAnchor
import commentjson
import csv
import io

# This package exists as it is not needed for showing help and running other
# commands, however, it has heavy dependencies (pcbnew) that take a second
# to load. Splitting it speeds up KiKit's startup.

PKG_BASE = os.path.dirname(__file__)
PRESET_LIB = os.path.join(PKG_BASE, "resources/panelizePresets")

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

def readBool(s):
    sl = str(s).lower()
    if sl in ["1", "true", "yes"]:
        return True
    if sl in ["0", "false", "no"]:
        return False
    raise PresetError(f"Uknown boolean value '{s}'")

def readHJustify(s):
    choices = {
        "left": EDA_TEXT_HJUSTIFY_T.GR_TEXT_HJUSTIFY_LEFT,
        "right": EDA_TEXT_HJUSTIFY_T.GR_TEXT_HJUSTIFY_RIGHT,
        "center": EDA_TEXT_HJUSTIFY_T.GR_TEXT_HJUSTIFY_CENTER
    }
    if s in choices:
        return choices[s]
    raise PresetError(f"'{s}' is not valid justification value")

def readVJustify(s):
    choices = {
        "top": EDA_TEXT_VJUSTIFY_T.GR_TEXT_VJUSTIFY_TOP,
        "center": EDA_TEXT_VJUSTIFY_T.GR_TEXT_VJUSTIFY_CENTER,
        "bottom": EDA_TEXT_VJUSTIFY_T.GR_TEXT_VJUSTIFY_BOTTOM
    }
    if s in choices:
        return choices[s]
    raise PresetError(f"'{s}' is not valid justification value")

ANCHORS = ["tl", "tr", "bl", "br", "mt", "mb", "ml", "mr", "c"]

def ppLayout(section):
    validateChoice("layout", section, "type", ["grid"])
    validateChoice("layout", section, "alternation",
        ["none", "rows", "cols", "rowsCols"])
    readParameters(section, readLength,
        ["hspace", "vspace", "space", "hbackbone", "vbackbone"])
    readParameters(section, readAngle, ["rotation"])
    readParameters(section, int, ["rows", "cols"])
    readParameters(section, readBool, ["vbonecut, hbonecut"])
    # The space parameter overrides hspace and vspace
    if "space" in section:
        section["hspace"] = section["vspace"] = section["space"]

def ppSource(section):
    validateChoice("source", section, "type", ["auto", "rectangle", "annotation"])
    readParameters(section, readLength,
        ["tolerance", "tlx", "tly", "brx", "bry"])
    readParameters(section, str, "ref")

def ppTabs(section):
    validateChoice("tabs", section, "type", ["none", "fixed", "spacing", "full",
        "corner", "annotation"])
    readParameters(section, readLength, ["vwidth", "hwidth", "width",
        "mindistance", "spacing"])
    readParameters(section, int, ["vcount", "hcount"])
    if "width" in section:
        section["vwidth"] = section["hwidth"] = section["width"]

def ppCuts(section):
    validateChoice("cuts", section, "type", ["none", "mousebites", "vcuts"])
    readParameters(section, readLength, ["drill", "spacing", "offset",
        "prolong", "clearance", "threshold"])
    readParameters(section, readBool, ["cutcurves"])
    readParameters(section, readLayer, ["layer"])

def ppFraming(section):
    validateChoice("framing", section, "type",
        ["none", "railstb", "railslr", "frame", "tightframe"])
    readParameters(section, readLength,
        ["hspace", "vspace", "space", "width", "slotwidth"])
    readParameters(section, readBool, ["cuts"])
    # The space parameter overrides hspace and vspace
    if "space" in section:
        section["hspace"] = section["vspace"] = section["space"]

def ppTooling(section):
    validateChoice("tooling", section, "type", ["none", "3hole", "4hole"])
    readParameters(section, readLength, ["hoffset", "voffset", "size"])
    readParameters(section, readBool, ["paste"])

def ppFiducials(section):
    validateChoice("fiducials", section, "type", ["none", "3fid", "4fid"])
    readParameters(section, readLength,
        ["hoffset", "voffset", "coppersize", "opening"])

def ppText(section):
    validateChoice("text", section, "type", ["none", "simple"])
    readParameters(section, readLength,
        ["hoffset", "voffset", "width", "height", "thickness"])
    readParameters(section, readHJustify, ["hjustify"])
    readParameters(section, readVJustify, ["vjustify"])
    readParameters(section, readLayer, ["layer"])
    readParameters(section, readAngle, ["orientation"])
    validateChoice("text", section, "anchor", ANCHORS)

def ppPost(section):
    validateChoice("type", section, "type", ["auto"])
    readParameters(section, readBool, ["copperfill"])
    readParameters(section, readLength, ["millradius"])
    readParameters(section, str, ["script", "scriptarg"])
    validateChoice("text", section, "origin", ANCHORS + [""])

def ppDebug(section):
    readParameters(section, readBool, ["drawPartitionLines",
        "drawBackboneLines", "drawboxes", "trace"])

def postProcessPreset(preset):
    process = {
        "layout": ppLayout,
        "source": ppSource,
        "tabs": ppTabs,
        "cuts": ppCuts,
        "framing": ppFraming,
        "tooling": ppTooling,
        "fiducials": ppFiducials,
        "text": ppText,
        "post": ppPost,
        "debug": ppDebug
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
    VALID_SECTIONS = ["layout", "source", "tabs", "cuts", "framing", "tooling",
        "fiducials", "text", "post", "debug"]
    extraSections = set(preset.keys()).difference(VALID_SECTIONS)
    if len(extraSections) != 0:
        raise PresetError(f"Extra sections {', '.join(extraSections)} in preset")
    missingSections = set(VALID_SECTIONS).difference(preset.keys())
    if len(missingSections) != 0:
        raise PresetError(f"Missing sections {', '.join(missingSections)} in preset")

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
    try:
        type = specification["type"]
        tolerance = specification["tolerance"]
        if type == "auto":
            return expandRect(findBoardBoundingBox(board), tolerance)
        if type == "annotation":
            ref = specification["ref"]
            return expandRect(extractSourceAreaByAnnotation(board, ref), tolerance)
        if type == "rectangle":
            tl = wxPoint(specification["tlx"], specification["tly"])
            br = wxPoint(specification["brx"], specification["bry"])
            return expandRect(wxRect(tl, br), tolerance)
        raise PresetError(f"Unknown type '{type}' of source specification.")
    except KeyError as e:
        raise PresetError(f"Missing parameter '{e}' in section 'source'")

def obtainPreset(presetPaths, validate=True, **kwargs):
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
    if validate:
        validateSections(preset)
    postProcessPreset(preset)
    return preset

def buildLayout(layout, panel, sourceBoard, sourceArea):
    """
    Build layout for the boards - e.g., make a grid out of them.

    Return the list of created substrates.
    """
    try:
        type = layout["type"]
        if type in ["grid"]:
            placementClass = getPlacementClass(layout["alternation"])
            return panel.makeGrid(
                boardfile=sourceBoard, sourceArea=sourceArea,
                rows=layout["rows"], cols=layout["cols"], destination=wxPointMM(50, 50),
                rotation=layout["rotation"],
                verSpace=layout["vspace"], horSpace=layout["hspace"],
                placementClass=placementClass,
                netRenamePattern=layout["renamenet"], refRenamePattern=layout["renameref"])
        raise PresetError(f"Unknown type '{type}' of layout specification.")
    except KeyError as e:
        raise PresetError(f"Missing parameter '{e}' in section 'layout'")

def buildTabs(properties, panel, substrates, boundarySubstrates):
    """
    Build tabs for the substrates in between the boards. Return a list of cuts.
    """
    try:
        type = properties["type"]
        if type == "none":
            return []
        if type == "fixed":
            panel.clearTabsAnnotations()
            panel.buildTabAnnotationsFixed(properties["hcount"],
                properties["vcount"], properties["hwidth"], properties["vwidth"],
                properties["mindistance"], boundarySubstrates)
            return panel.buildTabsFromAnnotations()
        if type == "spacing":
            panel.clearTabsAnnotations()
            panel.buildTabAnnotationsSpacing(properties["spacing"],
                properties["hwidth"], properties["vwidth"], boundarySubstrates)
            return panel.buildTabsFromAnnotations()
        if type == "corner":
            panel.clearTabsAnnotations()
            panel.buildTabAnnotationsCorners(properties["width"])
            return panel.buildTabsFromAnnotations()
        if type == "full":
            return panel.buildFullTabs()
        if type == "annotation":
            return panel.buildTabsFromAnnotations()
        raise PresetError(f"Unknown type '{type}' of tabs specification.")
    except KeyError as e:
        raise PresetError(f"Missing parameter '{e}' in section 'tabs'")

def buildBackBone(layout, panel, substrates, frameSpace):
    """
    Append backbones to the panel. Return backbone cuts.
    """
    try:
        return panel.renderBackbone(layout["vbackbone"], layout["hbackbone"],
                                    layout["vbonecut"], layout["hbonecut"])
    except KeyError as e:
        raise PresetError(f"Missing parameter '{e}' in section 'layout'")

def frameOffset(framing):
    try:
        type = framing["type"]
        if type == "none":
            return None, None
        if type == "railstb":
            return framing["vspace"], None
        if type == "railslr":
            return None, framing["hspace"]
        return framing["vspace"], framing["hspace"]
    except KeyError as e:
        raise PresetError(f"Missing parameter '{e}' in section 'framing'")

def makeTabCuts(properties, panel, cuts):
    """
    Perform cuts on tab (does not ignore offset)
    """
    makeCuts(properties, panel, cuts, False)

def makeOtherCuts(properties, panel, cuts):
    """
    Perform non-tab cuts (ignore offset)
    """
    makeCuts(properties, panel, cuts, True)

def makeCuts(properties, panel, cuts, ignoreOffset):
    """
    Perform cuts
    """
    try:
        type = properties["type"]
        if type == "none":
            return
        if type == "vcuts":
            panel.makeVCuts(cuts, properties["cutcurves"])
            panel.setVCutLayer(properties["layer"])
            panel.setVCutClearance(properties["clearance"])
        elif type == "mousebites":
            offset = 0 if ignoreOffset else properties["offset"]
            panel.makeMouseBites(cuts, properties["drill"],
                properties["spacing"], offset, properties["prolong"])
        else:
            raise PresetError(f"Unknown type '{type}' of cuts specification.")
    except KeyError as e:
        raise PresetError(f"Missing parameter '{e}' in section 'cuts'")


def polygonToSubstrate(polygon):
    s = Substrate([])
    s.union(polygon)
    return s

def dummyFramingSubstrate(substrates, frameOffset):
    """
    Generate dummy substrates that pretend to be the frame (to appear)
    """
    vSpace, hSpace = frameOffset
    dummy = []
    minx, miny, maxx, maxy = substrates[0].bounds()
    for s in substrates:
        minx2, miny2, maxx2, maxy2 = s.bounds()
        minx = min(minx, minx2)
        miny = min(miny, miny2)
        maxx = max(maxx, maxx2)
        maxy = max(maxy, maxy2)
    width = fromMm(0)
    if vSpace is not None:
        top = box(minx, miny - 2 * vSpace - width, maxx, miny - 2 * vSpace)
        bottom = box(minx, maxy + 2 * vSpace, maxx, maxy + 2 * vSpace + width)
        dummy.append(polygonToSubstrate(top))
        dummy.append(polygonToSubstrate(bottom))
    if hSpace is not None:
        left = box(minx - 2 * hSpace - width, miny, minx - 2 * hSpace, maxy)
        right = box(maxx + 2 * hSpace, miny, maxx + 2 * hSpace + width, maxy)
        dummy.append(polygonToSubstrate(left))
        dummy.append(polygonToSubstrate(right))
    return dummy

def buildFraming(preset, panel):
    """
    Build frame according to the preset and return cuts
    """
    try:
        type = preset["type"]
        if type == "none":
            return []
        if type == "railstb":
            panel.makeRailsTb(preset["width"])
            return []
        if type == "railslr":
            panel.makeRailsLr(preset["width"])
            return []
        if type == "frame":
            cuts = panel.makeFrame(preset["width"])
            return cuts if preset["cuts"] else []
        if type == "tightframe":
            panel.makeTightFrame(preset["width"], preset["slotwidth"])
            panel.boardSubstrate.removeIslands()
            return []
        raise PresetError(f"Unknown type '{type}' of frame specification.")
    except KeyError as e:
        raise PresetError(f"Missing parameter '{e}' in section 'framing'")

def buildTooling(preset, panel):
    """
    Build tooling holes according to the preset
    """
    try:
        type = preset["type"]
        if type == "none":
            return
        hoffset, voffset = preset["hoffset"], preset["voffset"]
        diameter = preset["size"]
        paste = preset["paste"]
        if type == "3hole":
            panel.addCornerTooling(3, hoffset, voffset, diameter, paste)
            return
        if type == "4hole":
            panel.addCornerTooling(4, hoffset, voffset, diameter, paste)
            return
        raise PresetError(f"Unknown type '{type}' of tooling specification.")
    except KeyError as e:
        raise PresetError(f"Missing parameter '{e}' in section 'tooling'")

def buildFiducials(preset, panel):
    """
    Build tooling holes according to the preset
    """
    try:
        type = preset["type"]
        if type == "none":
            return
        hoffset, voffset = preset["hoffset"], preset["voffset"]
        coppersize, opening = preset["coppersize"], preset["opening"]
        if type == "3fid":
            panel.addCornerFiducials(3, hoffset, voffset, coppersize, opening)
            return
        if type == "4fid":
            panel.addCornerFiducials(4, hoffset, voffset, coppersize, opening)
            return
        raise PresetError(f"Unknown type '{type}' of fiducial specification.")
    except KeyError as e:
        raise PresetError(f"Missing parameter '{e}' in section 'fiducials'")

def buildText(preset, panel):
    """
    Build text according to the preset
    """
    try:
        type = preset["type"]
        if type == "none":
            return
        if type == "simple":
            origin = resolveAnchor(preset["anchor"])(panel.boardSubstrate.boundingBox())
            origin += wxPoint(preset["hoffset"], preset["voffset"])

            panel.addText(
                text=preset["text"],
                position=origin,
                orientation=preset["orientation"],
                width=preset["width"],
                height=preset["height"],
                thickness=preset["thickness"],
                hJustify=preset["hjustify"],
                vJustify=preset["vjustify"],
                layer=preset["layer"])
            return
        raise PresetError(f"Unknown type '{type}' of text specification.")
    except KeyError as e:
        raise PresetError(f"Missing parameter '{e}' in section 'text'")

def buildPostprocessing(preset, panel):
    """
    Perform postprocessing operations
    """
    try:
        type = preset["type"]
        if type != "auto":
            raise PresetError(f"Unknown type '{type}' of postprocessing specification.")
        if preset["millradius"] > 0:
            panel.addMillFillets(preset["millradius"])
        if preset["copperfill"]:
            panel.copperFillNonBoardAreas()
        if preset["origin"]:
            origin = resolveAnchor(preset["origin"])(panel.boardSubstrate.boundingBox())
            panel.setAuxiliaryOrigin(origin)
            panel.setGridOrigin(origin)
    except KeyError as e:
        raise PresetError(f"Missing parameter '{e}' in section 'postprocessing'")

def runUserScript(preset, panel):
    """
    Run post processing script
    """
    if preset["script"] == "":
        return
    import importlib.util

    spec = importlib.util.spec_from_file_location("kikit.user_script",
        preset["script"])
    userScriptModule = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(userScriptModule)
    userScriptModule.kikitPostprocess(panel, preset["scriptarg"])


def buildDebugAnnotation(preset, panel):
    """
    Add debug annotation to the panel
    """
    try:
        if preset["drawPartitionLines"]:
            panel.debugRenderPartitionLines()
        if preset["drawBackboneLines"]:
            panel.debugRenderBackboneLines()
        if preset["drawboxes"]:
            panel.debugRenderBoundingBoxes()
    except KeyError as e:
        raise PresetError(f"Missing parameter '{e}' in section 'debug'")