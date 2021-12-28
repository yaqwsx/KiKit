import csv
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
    failed = drc.runImpl(board, True, False, ReportLevel.error, lambda x: print(x))
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

def collectPosData(board, correctionFields, posFilter=lambda x : True,
                   footprintX=defaultFootprintX, footprintY=defaultFootprintY, bom=None):
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
            return 0, 0, 0
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
