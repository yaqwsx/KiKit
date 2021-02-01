import click
from kikit.pcbnew_compatibility import pcbnew
import csv
import os
import sys
import shutil
from pathlib import Path
from kikit.eeshema import extractComponents, getField
from kikit.fab.common import *
from kikit.common import *
from kikit.export import gerberImpl

def collectBom(components, lscsFields, ignore):
    bom = {}
    for c in components:
        if c["unit"] != 1:
            continue
        reference = c["reference"]
        if reference.startswith("#PWR") or reference.startswith("#FL"):
            continue
        if reference in ignore:
            continue
        if getField(c, "JLCPCB_IGNORE") is not None:
            continue
        orderCode = None
        for fieldName in lscsFields:
            orderCode = getField(c, fieldName)
            if orderCode is not None:
                break
        cType = (
            getField(c, "Value"),
            getField(c, "Footprint"),
            orderCode
        )
        bom[cType] = bom.get(cType, []) + [reference]
    return bom

def bomToCsv(bomData, filename):
    with open(filename, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Comment", "Designator", "Footprint", "LCSC"])
        for cType, references in bomData.items():
            value, footprint, lcsc = cType
            writer.writerow([value, ",".join(references), footprint, lcsc])

def exportJlcpcb(board, outputdir, assembly, schematic, ignore, field,
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
    ordercodeFields = [x.strip() for x in field.split(",")]
    bom = collectBom(components, ordercodeFields, refsToIgnore)

    missingFields = False
    for type, references in bom.items():
        _, _, lcsc = type
        if not lcsc:
            missingFields = True
            for r in references:
                print(f"WARNING: Component {r} is missing ordercode")
    if missingFields and missingerror:
        sys.exit("There are components with missing ordercode, aborting")

    posData = collectPosData(loadedBoard, correctionFields, bom=components)
    posDataToFile(posData, os.path.join(outputdir, "pos.csv"))
    bomToCsv(bom, os.path.join(outputdir, "bom.csv"))
