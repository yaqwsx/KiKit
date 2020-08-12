import click
import pcbnew
import csv
import os
import sys
import shutil
from math import sin, cos, radians
from pathlib import Path
from kikit.eeshema import extractComponents, getField
from kikit.defs import MODULE_ATTR_T
from kikit.fab.common import hasNonSMDPins
from kikit.common import *
from kikit.export import gerberImpl

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

def moduleX(module, placeOffset, compensation):
    # JLC PCB does not require mirrored X when the components are on the bottom side
    return toMm(modulePosition(module, placeOffset, compensation)[0])

def moduleY(module, placeOffset, compensation):
    return -toMm(modulePosition(module, placeOffset, compensation)[1])

def moduleOrientation(module, compensation):
    return module.GetOrientation() / 10 + compensation[2]

def parseCompensation(compensation):
    comps = [float(x) for x in compensation.split(";")]
    if len(comps) != 3:
        raise FormatError(f"Invalid format of compensation '{compensation}'")
    return comps

def collectPosData(board, correctionFields=["JLCPCB_CORRECTION"], bom=None,
                   forceSmd=False):
    """
    Extract position data of the modules.

    If the optional BOM contains fields "JLCPCB_CORRECTION" in format
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
        # We can use module.HasNonSMDPins() in KiCAD 6
        if module.GetAttributes() & MODULE_ATTR_T.MOD_CMS or (forceSmd and not hasNonSMDPins(module)):
            modules.append(module)
    def getCompensation(module):
        if module.GetReference() not in bom:
            return 0, 0, 0
        field = None
        for fieldName in correctionFields:
            field = getField(bom[module.GetReference()], fieldName)
            if field is not None:
                break
        if field is None:
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

def collectBom(components, lscsField, ignore):
    bom = {}
    for c in components:
        if c["unit"] != 1:
            continue
        reference = c["reference"]
        if reference.startswith("#PWR") or reference.startswith("#FL") or reference in ignore:
            continue
        cType = (
            getField(c, "Value"),
            getField(c, "Footprint"),
            getField(c, lscsField)
        )
        bom[cType] = bom.get(cType, []) + [reference]
    return bom

def posDataToFile(posData, filename):
    with open(filename, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for line in sorted(posData, key=lambda x: x[0]):
            writer.writerow(line)

def bomToCsv(bomData, filename):
    with open(filename, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Comment", "Designator", "Footprint", "LCSC"])
        for cType, references in bomData.items():
            value, footprint, lcsc = cType
            writer.writerow([value, ",".join(references), footprint, lcsc])

@click.command()
@click.argument("board", type=click.Path(dir_okay=False))
@click.argument("outputdir", type=click.Path(file_okay=False))
@click.option("--assembly/--no-assembly", help="Generate files for SMT assembly (schematics is required)")
@click.option("--schematic", type=click.Path(dir_okay=False), help="Board schematics (required for assembly files)")
@click.option("--forceSMD", is_flag=True, help="Force include all components having only SMD pads")
@click.option("--ignore", type=str, default="", help="Comma separated list of designators to exclude from SMT assembly")
@click.option("--field", type=str, default="LCSC", help="Name of component field with LCSC order code")
@click.option("--corrections", type=str, default="JLCPCB_CORRECTION",
    help="Comma separated list of component fields with the correction value. First existing field is used")
@click.option("--missingError/--missingWarn", help="If a non-ignored component misses LCSC field, fail")
def jlcpcb(board, outputdir, assembly, schematic, forcesmd, ignore, field,
           corrections, missingerror):
    """
    Prepare fabrication files for JLCPCB including their assembly service
    """
    loadedBoard = pcbnew.LoadBoard(board)
    refsToIgnore = parseReferences(ignore)
    removeComponents(loadedBoard, refsToIgnore)
    Path(outputdir).mkdir(parents=True, exist_ok=True)

    gerberdir = os.path.join(outputdir, "gerber")
    shutil.rmtree(gerberdir, ignore_errors=True)
    gerberImpl(board, gerberdir)
    shutil.make_archive(os.path.join(outputdir, "gerbers"), "zip", outputdir, "gerber")

    if not assembly:
        return
    if schematic is None:
        raise RuntimeError("When outputing assembly data, schematic is required")
    correctionFields = [x.strip() for x in corrections.split(",")]
    components = extractComponents(schematic)
    bom = collectBom(components, field, refsToIgnore)

    missingFields = False
    for type, references in bom.items():
        _, _, lcsc = type
        if not lcsc:
            missingFields = True
            for r in references:
                print(f"WARNING: Component {r} is missing ordercode")
    if missingFields and missingerror:
        sys.exit("There are components with missing ordercode, aborting")

    posDataToFile(collectPosData(loadedBoard, correctionFields, components, forcesmd), os.path.join(outputdir, "pos.csv"))
    bomToCsv(bom, os.path.join(outputdir, "bom.csv"))
