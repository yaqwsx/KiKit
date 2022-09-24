import click
from pcbnewTransition import pcbnew, isV6
import csv
import os
import re
import sys
import shutil
from pathlib import Path
from kikit.fab.common import *
from kikit.common import *
from kikit.export import gerberImpl, exportSettingsPcbway

def collectSolderTypes(board):
    result = {}
    for footprint in board.GetFootprints():
        if excludeFromPos(footprint):
            continue
        if hasNonSMDPins(footprint):
            result[footprint.GetReference()] = "thru-hole"
        else:
            result[footprint.GetReference()] = "SMD"

    return result

def addVirtualToRefsToIgnore(refsToIgnore, board):
    for footprint in board.GetFootprints():
        if excludeFromPos(footprint):
            refsToIgnore.append(footprint.GetReference())

def collectBom(components, manufacturerFields, partNumberFields,
               descriptionFields, notesFields, typeFields, footprintFields,
               ignore):
    bom = {}

    # Use KiCad footprint as fallback for footprint
    footprintFields.append("Footprint")
    # Use value as fallback for description
    descriptionFields.append("Value")

    for c in components:
        if getUnit(c) != 1:
            continue
        reference = getReference(c)
        if reference.startswith("#PWR") or reference.startswith("#FL") or reference in ignore:
            continue
        if hasattr(c, "in_bom") and not c.in_bom:
            continue
        manufacturer = None
        for manufacturerName in manufacturerFields:
            manufacturer = getField(c, manufacturerName)
            if manufacturer is not None:
                break
        partNumber = None
        for partNumberName in partNumberFields:
            partNumber = getField(c, partNumberName)
            if partNumber is not None:
                break
        description = None
        for descriptionName in descriptionFields:
            description = getField(c, descriptionName)
            if description is not None:
                break
        notes = None
        for notesName in notesFields:
            notes = getField(c, notesName)
            if notes is not None:
                break
        solderType = None
        for typeName in typeFields:
            solderType = getField(c, typeName)
            if solderType is not None:
                break
        footprint = None
        for footprintName in footprintFields:
            footprint = getField(c, footprintName)
            if footprint is not None:
                break

        cType = (
            description,
            footprint,
            manufacturer,
            partNumber,
            notes,
            solderType
        )
        bom[cType] = bom.get(cType, []) + [reference]
    return bom

def natural_sort(l):
    #https://stackoverflow.com/questions/4836710/is-there-a-built-in-function-for-string-natural-sort
    convert = lambda text: int(text) if text.isdigit() else text.lower()
    alphanum_key = lambda key: [ convert(c) for c in re.split('([0-9]+)', key) ]
    return sorted(l, key = alphanum_key)

def bomToCsv(bomData, filename, nBoards, types):
    with open(filename, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Item #", "Designator", "Qty", "Manufacturer",
                         "Mfg Part #", "Description / Value", "Footprint",
                         "Type", "Your Instructions / Notes"])
        item_no = 1

        tmp = {}
        for cType, references in bomData.items():
            tmp[references[0]] = (references, cType)

        for i in natural_sort(tmp):
            references, cType = tmp[i]
            references = natural_sort(references)
            description, footprint, manufacturer, partNumber, notes, solderType = cType
            if solderType is None:
                solderType = types[references[0]]
            writer.writerow([item_no, ",".join(references),
                             len(references) * nBoards, manufacturer,
                             partNumber, description, footprint,
                             solderType, notes])
            item_no += 1


def exportPcbway(board, outputdir, assembly, schematic, ignore,
                 manufacturer, partnumber, description, notes, soldertype,
                 footprint, corrections, correctionpatterns, missingerror, nboards, nametemplate, drc):
    """
    Prepare fabrication files for PCBWay including their assembly service
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
    gerberImpl(board, gerberdir, settings=exportSettingsPcbway)
    archiveName = nametemplate.format("gerbers")
    shutil.make_archive(os.path.join(outputdir, archiveName), "zip", outputdir, "gerber")

    if not assembly:
        return
    if schematic is None:
        raise RuntimeError("When outputing assembly data, schematic is required")

    ensureValidSch(schematic)


    components = extractComponents(schematic)
    correctionFields    = [x.strip() for x in corrections.split(",")]
    manufacturerFields  = [x.strip() for x in manufacturer.split(",")]
    partNumberFields    = [x.strip() for x in partnumber.split(",")]
    descriptionFields   = [x.strip() for x in description.split(",")]
    notesFields         = [x.strip() for x in notes.split(",")]
    typeFields          = [x.strip() for x in soldertype.split(",")]
    footprintFields     = [x.strip() for x in footprint.split(",")]
    addVirtualToRefsToIgnore(refsToIgnore, loadedBoard)
    bom = collectBom(components, manufacturerFields, partNumberFields,
                     descriptionFields, notesFields, typeFields,
                     footprintFields, refsToIgnore)

    missingFields = False
    for type, references in bom.items():
        _, _, manu, partno, _, _ = type
        if not manu or not partno:
            missingFields = True
            for r in references:
                print(f"WARNING: Component {r} is missing manufacturer and/or part number")
    if missingFields and missingerror:
        sys.exit("There are components with missing ordercode, aborting")

    posData = collectPosData(loadedBoard, correctionFields, bom=components, correctionFile=correctionpatterns)
    posDataToFile(posData, os.path.join(outputdir, nametemplate.format("pos") + ".csv"))
    types = collectSolderTypes(loadedBoard)
    bomToCsv(bom, os.path.join(outputdir, nametemplate.format("bom") + ".csv"), nboards, types)
