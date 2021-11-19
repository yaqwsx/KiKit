import csv
from pcbnewTransition import pcbnew
from math import sin, cos, radians
from kikit.common import *
from kikit.defs import MODULE_ATTR_T
from kikit.eeshema import getField


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
        bom = { comp["reference"]: comp for comp in bom }
    footprints = []
    placeOffset = board.GetDesignSettings().m_AuxOrigin
    for footprint in board.GetFootprints():
        if footprint.GetAttributes() & MODULE_ATTR_T.MOD_VIRTUAL:
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
