import click
from pcbnewTransition import pcbnew
import csv
import os
import sys
import shutil
from pathlib import Path
from kikit.fab.common import *
from kikit.common import *
from kikit.export import gerberImpl

def collectBom(components, lscsFields):
    bom = {}
    for c in components:
        orderCode = None
        for fieldName in lscsFields:
            orderCode = getField(c, fieldName)
            if orderCode is not None and orderCode.strip() != "":
                break
        cType = (
            getField(c, "Value"),
            getField(c, "Footprint"),
            orderCode
        )
        bom[cType] = bom.get(cType, []) + [getReference(c)]
    return bom

def bomToCsv(bomData, filename):
    with open(filename, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Comment", "Designator", "Footprint", "LCSC"])
        for cType, references in bomData.items():
            # JLCPCB allows at most 200 components per line so we have to split
            # the BOM into multiple lines. Let's make the chunks by 100 just to
            # be sure.
            CHUNK_SIZE = 100
            sortedReferences = sorted(references, key=naturalComponentKey)
            for i in range(0, len(references), CHUNK_SIZE):
                refChunk = sortedReferences[i:i+CHUNK_SIZE]
                value, footprint, lcsc = cType
                writer.writerow([value, ",".join(refChunk), footprint, lcsc])

def exportJlcpcb(board, outputdir, assembly, schematic, ignore, field,
           corrections, correctionpatterns, missingerror, nametemplate, drc,
           autoname):
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

    if autoname:
        boardName = os.path.basename(board.replace(".kicad_pcb", ""))
        archiveName = expandNameTemplate(nametemplate, boardName + "-gerbers", loadedBoard)
    else:
        archiveName = expandNameTemplate(nametemplate, "gerbers", loadedBoard)
    shutil.make_archive(os.path.join(outputdir, archiveName), "zip", outputdir, "gerber")

    if not assembly:
        return
    if schematic is None:
        raise RuntimeError("When outputing assembly data, schematic is required")

    ensureValidSch(schematic)

    correctionFields = [x.strip() for x in corrections.split(",")]
    components = extractComponents(schematic, refsToIgnore, "JLCPCB_IGNORE")
    ordercodeFields = [x.strip() for x in field.split(",")]
    bom = collectBom(components, ordercodeFields)

    bom_refs = set(x for xs in bom.values() for x in xs)
    bom_components = [c for c in components if getReference(c) in bom_refs]

    posData = collectPosData(loadedBoard, correctionFields,
        bom=bom_components, posFilter=noFilter, correctionFile=correctionpatterns,
        orientationHandling=FootprintOrientationHandling.MirrorBottom)
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

    posDataToFile(posData, os.path.join(outputdir, expandNameTemplate(nametemplate, "pos", loadedBoard) + ".csv"))
    bomToCsv(bom, os.path.join(outputdir, expandNameTemplate(nametemplate, "bom", loadedBoard) + ".csv"))
