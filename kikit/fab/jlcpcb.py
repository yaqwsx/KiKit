import click
from pcbnewTransition import pcbnew, isV6
import csv
import os
import sys
import shutil
from pathlib import Path
from kikit.fab.common import *
from kikit.common import *
from kikit.export import gerberImpl

def collectBom(components, lscsFields, ignore):
    bom = {}
    for c in components:
        if getUnit(c) != 1:
            continue
        reference = getReference(c)
        if reference.startswith("#PWR") or reference.startswith("#FL"):
            continue
        if reference in ignore:
            continue
        if getField(c, "JLCPCB_IGNORE") is not None and getField(c, "JLCPCB_IGNORE") != "":
            continue
        if hasattr(c, "in_bom") and not c.in_bom:
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
            # JLCPCB allows at most 200 components per line so we have to split
            # the BOM into multiple lines. Let's make the chunks by 100 just to
            # be sure.
            CHUNK_SIZE = 100
            for i in range(0, len(references), CHUNK_SIZE):
                refChunk = references[i:i+CHUNK_SIZE]
                value, footprint, lcsc = cType
                writer.writerow([value, ",".join(refChunk), footprint, lcsc])

def noFilter(footprint):
    return True

def exportJlcpcb(board, outputdir, assembly, schematic, ignore, field,
           corrections, correctionpatterns, missingerror, nametemplate, drc):
    """
    Prepare fabrication files for JLCPCB including their assembly service
    """
    ensureValidBoard(board)
    loadedBoard = pcbnew.LoadBoard(board)

    if drc:
        ensurePassingDrc(loadedBoard)

    refsToIgnore = parseReferences(ignore)
    removeComponents(loadedBoard, refsToIgnore)
    Path(outputdir).mkdir(parents=True, exist_ok=True)

    gerberdir = os.path.join(outputdir, "gerber")
    shutil.rmtree(gerberdir, ignore_errors=True)
    gerberImpl(board, gerberdir)
    archiveName = nametemplate.format("gerbers")
    shutil.make_archive(os.path.join(outputdir, archiveName), "zip", outputdir, "gerber")

    if not assembly:
        return
    if schematic is None:
        raise RuntimeError("When outputing assembly data, schematic is required")

    ensureValidSch(schematic)

    correctionFields = [x.strip() for x in corrections.split(",")]
    components = extractComponents(schematic)
    ordercodeFields = [x.strip() for x in field.split(",")]
    bom = collectBom(components, ordercodeFields, refsToIgnore)

    posData = collectPosData(loadedBoard, correctionFields,
        bom=components, posFilter=noFilter, correctionFile=correctionpatterns)
    boardReferences = set([x[0] for x in posData])
    bom = {key: [v for v in val if v in boardReferences] for key, val in bom.items()}
    bom = {key: val for key, val in bom.items() if len(val) > 0}


    missingFields = False
    for type, references in bom.items():
        _, _, lcsc = type
        if not lcsc:
            missingFields = True
            for r in references:
                print(f"WARNING: Component {r} is missing ordercode")
    if missingFields and missingerror:
        sys.exit("There are components with missing ordercode, aborting")

    posDataToFile(posData, os.path.join(outputdir, nametemplate.format("pos") + ".csv"))
    bomToCsv(bom, os.path.join(outputdir, nametemplate.format("bom") + ".csv"))
