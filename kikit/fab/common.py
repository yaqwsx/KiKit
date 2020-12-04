import csv
import pcbnew
from math import sin, cos, radians
from kikit.common import *
from kikit.defs import MODULE_ATTR_T
from kikit.eeshema import getField


def hasNonSMDPins(module):
    for pad in module.Pads():
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

def modulePosition(module, placeOffset, compensation):
    pos = module.GetPosition() - placeOffset
    angle = -radians(module.GetOrientation() / 10.0)
    x = compensation[0] * cos(angle) - compensation[1] * sin(angle)
    y = compensation[0] * sin(angle) + compensation[1] * cos(angle)
    pos += wxPoint(fromMm(x), fromMm(y))
    return pos

def moduleOrientation(module, compensation):
    return module.GetOrientation() / 10 + compensation[2]

def parseCompensation(compensation):
    comps = [float(x) for x in compensation.split(";")]
    if len(comps) != 3:
        raise FormatError(f"Invalid format of compensation '{compensation}'")
    return comps

def defaultModuleX(module, placeOffset, compensation):
    # Overwrite when module requires mirrored X when components are on the bottom side
    return toMm(modulePosition(module, placeOffset, compensation)[0])

def defaultModuleY(module, placeOffset, compensation):
    return -toMm(modulePosition(module, placeOffset, compensation)[1])

def collectPosData(board, correctionFields, posFilter=lambda x : True,
                   moduleX=defaultModuleX, moduleY=defaultModuleY, bom=None):
    """
    Extract position data of the modules.

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
    modules = []
    placeOffset = board.GetDesignSettings().m_AuxOrigin
    for module in board.GetModules():
        if module.GetAttributes() & MODULE_ATTR_T.MOD_VIRTUAL:
            continue
        if (posFilter(module)):
            modules.append(module)
    def getCompensation(module):
        if module.GetReference() not in bom:
            return 0, 0, 0
        field = None
        for fieldName in correctionFields:
            field = getField(bom[module.GetReference()], fieldName)
            if field is not None:
                break
        if field is None or field == "":
            return 0, 0, 0
        try:
            return parseCompensation(field)
        except FormatError as e:
            raise FormatError(f"{module.GetReference()}: {e}")
    return [(module.GetReference(),
             moduleX(module, placeOffset, getCompensation(module)),
             moduleY(module, placeOffset, getCompensation(module)),
             layerToSide(module.GetLayer()),
             moduleOrientation(module, getCompensation(module))) for module in modules]

def posDataToFile(posData, filename):
    with open(filename, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for line in sorted(posData, key=lambda x: x[0]):
            writer.writerow(line)
