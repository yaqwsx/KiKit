import csv
from dataclasses import dataclass
import re
from typing import OrderedDict
from pcbnewTransition import pcbnew, isV6
from math import sin, cos, radians
from kikit.common import *
from kikit.defs import MODULE_ATTR_T
from kikit.drc_ui import ReportLevel
from kikit import drc
from kikit import eeschema, eeschema_v6
import sys

if isV6():
    from kikit import eeschema_v6 # import getField, getUnit, getReference
from kikit import eeschema #import getField, getUnit, getReference

# A user can still supply v5 schematics even when we run v6, therefore,
# we have to load the correct schematics and provide the right getters
def extractComponents(filename):
    if filename.endswith(".kicad_sch"):
        return eeschema_v6.extractComponents(filename)
    if filename.endswith(".sch"):
        return eeschema.extractComponents(filename)
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
    if not isV6():
        return # v5 cannot check DRC
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
    angle = -radians(footprint.GetOrientation() / 10.0)
    x = compensation[0] * cos(angle) - compensation[1] * sin(angle)
    y = compensation[0] * sin(angle) + compensation[1] * cos(angle)
    pos += wxPoint(fromMm(x), fromMm(y))
    return pos

def footprintOrientation(footprint, compensation):
    return (footprint.GetOrientation() / 10 + compensation[2]) % 360

def parseCompensation(compensation):
    comps = [float(x) for x in compensation.split(";")]
    if len(comps) != 3:
        raise FormatError(f"Invalid format of compensation '{compensation}'")
    return comps

def defaultFootprintX(footprint, placeOffset, compensation):
    # Overwrite when footprint requires mirrored X when components are on the bottom side
    return toMm(footprintPosition(footprint, placeOffset, compensation)[0])

def defaultFootprintY(footprint, placeOffset, compensation):
    return -toMm(footprintPosition(footprint, placeOffset, compensation)[1])

def excludeFromPos(footprint):
    if isV6():
        return footprint.GetAttributes() & pcbnew.FP_EXCLUDE_FROM_POS_FILES
    else:
        return footprint.GetAttributes() & MODULE_ATTR_T.MOD_VIRTUAL

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
    with open(filename) as csvfile:
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

def collectPosData(board, correctionFields, posFilter=lambda x : True,
                   footprintX=defaultFootprintX, footprintY=defaultFootprintY, bom=None,
                   correctionFile=None):
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
             footprintOrientation(footprint, getCompensation(footprint))) for footprint in footprints]

def posDataToFile(posData, filename):
    with open(filename, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for line in sorted(posData, key=lambda x: x[0]):
            writer.writerow(line)

def isValidSchPath(filename):
    return os.path.splitext(filename)[1] in [".sch", ".kicad_sch"]

def isValidBoardPath(filename):
    return os.path.splitext(filename)[1] in [".kicad_pcb"]

def ensureValidSch(filename):
    if not isValidSchPath(filename):
        raise RuntimeError(f"The path {filename} is not a valid KiCAD schema file")

def ensureValidBoard(filename):
    if not isValidBoardPath(filename):
        raise RuntimeError(f"The path {filename} is not a valid KiCAD PCB file")
