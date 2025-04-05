import csv
from dataclasses import dataclass
from enum import Enum
import re
from typing import OrderedDict
from kikit.project import KiCADProject
from pcbnewTransition import pcbnew, kicad_major
from math import sin, cos, radians
from kikit.common import *
from kikit.defs import MODULE_ATTR_T
from kikit.drc_ui import ReportLevel
from kikit import drc
from kikit import eeschema, eeschema_v6
from kikit.text import kikitTextVars
import sys

if kicad_major() >= 6:
    from kikit import eeschema_v6 # import getField, getUnit, getReference
from kikit import eeschema #import getField, getUnit, getReference

def filterComponents(components, refsToIgnore, ignoreField):
    filtered = []
    for c in components:
        if getUnit(c) != 1:
            continue
        reference = getReference(c)
        if reference.startswith("#PWR") or reference.startswith("#FL"):
            continue
        if reference in refsToIgnore:
            continue
        if getField(c, ignoreField) is not None and getField(c, ignoreField) != "":
            continue
        if hasattr(c, "in_bom") and not c.in_bom:
            continue
        if hasattr(c, "on_board") and not c.on_board:
            continue
        if hasattr(c, "dnp") and c.dnp:
            continue
        filtered.append(c)
    return filtered

# A user can still supply v5 schematics even when we run v6, therefore,
# we have to load the correct schematics and provide the right getters
def extractComponents(filename, refsToIgnore, ignoreField):
    if isinstance(filename, (list, tuple)):
        mergedComponents = []
        seenRefs = dict()

        for f in filename:
            components = extractComponents(f, refsToIgnore, ignoreField)
            for c in components:
                ref = getReference(c)

                seen = seenRefs.get(ref)
                if seen == f:
                    raise RuntimeError(
                        f"Duplicate reference designator: '{f}' defines reference '{ref}' more than once."
                    )
                elif seen:
                    raise RuntimeError(
                        f"Duplicate reference designator: both '{f}' and '{seen}' define reference '{ref}'. "
                        + "When using multiple schematics, component references must be unique across all schematics."
                    )

                seenRefs[ref] = f
                mergedComponents.append(c)

        return mergedComponents

    if filename.endswith(".kicad_sch"):
        return filterComponents(eeschema_v6.extractComponents(filename), refsToIgnore, ignoreField)
    if filename.endswith(".sch"):
        return filterComponents(eeschema.extractComponents(filename), refsToIgnore, ignoreField)
    raise RuntimeError(f"Unknown schematic file type specified: {filename}")

def getUnit(component):
    if isinstance(component, eeschema_v6.Symbol):
        return eeschema_v6.getUnit(component)
    return eeschema.getUnit(component)

def getField(component, field):
    if isinstance(component, eeschema_v6.Symbol):
        return eeschema_v6.getField(component, field)
    return eeschema.getField(component, field)

def getReference(component):
    if isinstance(component, eeschema_v6.Symbol):
        return eeschema_v6.getReference(component)
    return eeschema.getReference(component)

def ensurePassingDrc(board):
    failed = drc.runImpl(board,
        useMm=True,
        ignoreExcluded=True,
        strict=False,
        level=ReportLevel.error,
        yieldViolation=lambda x: print(x))
    if failed:
        print("DRC failed. See report above. No files produced")
        sys.exit(1)

def hasNonSMDPins(footprint):
    for pad in footprint.Pads():
        if pad.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
            return True
    return False

class FormatError(Exception):
    pass

class FootprintOrientationHandling(Enum):
    KiCad = 0
    MirrorBottom = 1

@dataclass
class CorrectionPattern:
    """Single correction pattern to match a component against."""
    footprint: re.Pattern
    part_id: re.Pattern
    x_correction: float
    y_correction: float
    rotation: float

def layerToSide(layer):
    if layer == pcbnew.F_Cu:
        return "T"
    if layer == pcbnew.B_Cu:
        return "B"
    raise RuntimeError(f"Got component with invalid layer {layer}")

def footprintPosition(footprint, placeOffset, compensation):
    pos = footprint.GetPosition() - placeOffset
    angle = -footprint.GetOrientation().AsRadians()
    x = compensation[0] * cos(angle) - compensation[1] * sin(angle)
    y = compensation[0] * sin(angle) + compensation[1] * cos(angle)
    pos += VECTOR2I(fromMm(x), fromMm(y))
    return pos

def footprintOrientation(footprint, compensation, orientation: FootprintOrientationHandling = FootprintOrientationHandling.KiCad):
    if orientation == FootprintOrientationHandling.KiCad:
        return (footprint.GetOrientation().AsDegrees() + compensation[2]) % 360
    if orientation == FootprintOrientationHandling.MirrorBottom:
        if layerToSide(footprint.GetLayer()) == "B":
            return (180 - footprint.GetOrientation().AsDegrees() + compensation[2]) % 360
        else:
            return (footprint.GetOrientation().AsDegrees() + compensation[2]) % 360

    raise AssertionError("Invalid orientation handling")

def parseCompensation(compensation):
    compParts = compensation.split(";")
    if len(compParts) != 3:
        raise FormatError(f"Invalid format of compensation '{compensation}' – there should be 3 parts, got {len(compParts)}")
    try:
        comps = [float(x) for x in compParts]
        return comps
    except Exception:
        raise FormatError(f"Invalid format of compensation '{compensation}' – items are not numbers") from None

def defaultFootprintX(footprint, placeOffset, compensation):
    # Overwrite when footprint requires mirrored X when components are on the bottom side
    return toMm(footprintPosition(footprint, placeOffset, compensation)[0])

def defaultFootprintY(footprint, placeOffset, compensation):
    return -toMm(footprintPosition(footprint, placeOffset, compensation)[1])

def excludeFromPos(footprint):
    return footprint.GetAttributes() & pcbnew.FP_EXCLUDE_FROM_POS_FILES

def readCorrectionPatterns(filename):
    """
    Read footprint correction pattern file.

    The file should be a CSV file with the following fields:
    - Regexp to match to the footprint
    - Regexp to match to the part id (ignored at the moment)
    - X correction
    - Y correction
    - Rotation
    """
    corrections = OrderedDict()
    correctionPatterns = []
    with open(filename, encoding="utf-8") as csvfile:
        sample = csvfile.read(1024)
        dialect = csv.Sniffer().sniff(sample)
        has_header = csv.Sniffer().has_header(sample)
        csvfile.seek(0)
        reader = csv.reader(csvfile, dialect)
        first = True
        for row in reader:
            if has_header and first:
                first = False
                continue
            correctionPatterns.append(
                CorrectionPattern(
                    re.compile(row[0]),
                    re.compile(row[1]),
                    float(row[2]),
                    float(row[3]),
                    float(row[4]),
                )
            )
    return correctionPatterns

def applyCorrectionPattern(correctionPatterns, footprint):
    # FIXME: part ID is currently ignored
    # GetUniStringLibId returns the full footprint name including the
    # library in the form of "Resistor_SMD:R_0402_1005Metric"
    footprintName = str(footprint.GetFPID().GetUniStringLibId())
    for corpat in correctionPatterns:
        if corpat.footprint.match(footprintName):
            return (corpat.x_correction, corpat.y_correction, corpat.rotation)
    return (0, 0, 0)

def noFilter(footprint):
    return True

def collectPosData(board, correctionFields, posFilter=lambda x : True,
                   footprintX=defaultFootprintX, footprintY=defaultFootprintY, bom=None,
                   correctionFile=None, orientationHandling: FootprintOrientationHandling = FootprintOrientationHandling.KiCad):
    """
    Extract position data of the footprints.

    If the optional BOM contains fields "<FABNAME>_CORRECTION" in format
    '<X>;<Y>;<ROTATION>' these corrections of component origin and rotation are
    added to the position (in millimeters and degrees). Read the XY corrections
    by hovering cursor over the intended origin in footprint editor and mark the
    coordinates.
    """
    if bom is None:
        bom = {}
    else:
        bom = { getReference(comp): comp for comp in bom }

    correctionPatterns = []
    if correctionFile is not None:
        correctionPatterns = readCorrectionPatterns(correctionFile)

    footprints = []
    placeOffset = board.GetDesignSettings().GetAuxOrigin()
    for footprint in board.GetFootprints():
        if excludeFromPos(footprint):
            continue
        if posFilter(footprint) and footprint.GetReference() in bom:
            footprints.append(footprint)
    def getCompensation(footprint):
        if footprint.GetReference() not in bom:
            return 0, 0, 0
        field = None
        for fieldName in correctionFields:
            field = getField(bom[footprint.GetReference()], fieldName)
            if field is not None:
                break
        if field is None or field == "":
            return applyCorrectionPattern(
                correctionPatterns,
                footprint)
        try:
            return parseCompensation(field)
        except FormatError as e:
            raise FormatError(f"{footprint.GetReference()}: {e}")
    return [(footprint.GetReference(),
             footprintX(footprint, placeOffset, getCompensation(footprint)),
             footprintY(footprint, placeOffset, getCompensation(footprint)),
             layerToSide(footprint.GetLayer()),
             footprintOrientation(footprint, getCompensation(footprint), orientationHandling)) for footprint in footprints]

def posDataToFile(posData, filename):
    with open(filename, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for line in sorted(posData, key=lambda x: naturalComponentKey(x[0])):
            line = list(line)
            for i in [1, 2, 4]:
                line[i] = f"{line[i]:.2f}" # Most Fab houses expect only 2 decimal digits
            writer.writerow(line)

def isValidSchPath(filename):
    return os.path.splitext(filename)[1] in [".sch", ".kicad_sch"]

def isValidBoardPath(filename):
    return os.path.splitext(filename)[1] in [".kicad_pcb"]

def ensureValidSch(filename):
    if isinstance(filename, (list, tuple)):
        for f in filename:
            ensureValidSch(f)
    else:
        if not isValidSchPath(filename):
            raise RuntimeError(f"The path {filename} is not a valid KiCAD schema file")

def ensureValidBoard(filename):
    if not isValidBoardPath(filename):
        raise RuntimeError(f"The path {filename} is not a valid KiCAD PCB file")

def expandNameTemplate(template: str, filetype: str, board: pcbnew.BOARD) -> str:
    if re.findall(r"\{.*\}", template) == []:
        raise RuntimeError(f"The filename template '{template} must contain at least one variable name")
    textVars = kikitTextVars(board, KiCADProject(board.GetFileName()).textVars)
    try:
        return template.format(filetype, **textVars)
    except KeyError as e:
        raise RuntimeError(f"Unknown variable {e} in --nametemplate: {template}")

def naturalComponentKey(reference: str) -> Tuple[str, int]:
    text, num = splitOnReverse(reference, lambda x: x.isdigit())
    return str(text), int(num)
