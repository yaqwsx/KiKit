import click
from pcbnewTransition import pcbnew
import csv
import os
import sys
import shutil
import re
from pathlib import Path
from kikit.fab.common import *
from kikit.common import *
from kikit.units import mm

FOOTPRIINTREGEX = {
    re.compile(r'Capacitor_SMD:C_(\d+)_.*'): 'C_{}',
    re.compile(r'Diode_SMD:D_(\d+)_.*'): 'D_{}',
    re.compile(r'Inductor_SMD:L_(\d+)_.*'): 'L_{}',
    re.compile(r'Resistor_SMD:R_(\d+)_.*'): 'R_{}',
    re.compile(r'Crystal:Crystal_SMD_(.*?)_.*'): 'CRYSTAL_{}'
}

def collectBom(components, ignore):
    bom = {}
    for c in components:
        if getUnit(c) != 1:
            continue
        reference = getReference(c)
        if reference.startswith("#PWR") or reference.startswith("#FL"):
            continue
        if reference in ignore:
            continue
        if hasattr(c, "in_bom") and not c.in_bom:
            continue
        if hasattr(c, "on_board") and not c.on_board:
            continue
        if hasattr(c, "dnp") and c.dnp:
            continue
        cType = (
            getField(c, "Value"),
            getField(c, "Footprint")
        )
        bom[cType] = bom.get(cType, []) + [reference]
    return bom

def transcodeFootprint(footprint):
    for pattern, replacement in FOOTPRIINTREGEX.items():
        matchedFootprint = pattern.match(footprint)
        if matchedFootprint != None:
            return replacement.format(matchedFootprint.groups()[0])
    matchedFootprint = footprint.split(':')
    if len(matchedFootprint) > 1:
        return matchedFootprint[1].split('_')[0]
    else:
        return footprint

def posDataProcess(posData, pcbSize, bom):
    topLayer = []
    bottomLayer = []
    ref = {}
    for cType, references in bom.items():
        sortedReferences = sorted(references, key=naturalComponentKey)
        for refComponent in sortedReferences:
            ref[refComponent] = cType
    for line in posData:
        if line[0] in ref:
            value, footprint = ref[line[0]]
            if line[3] == 'T':
                topLayer.append(line + (value, footprint, line[1], line[2],))
            elif line[3] == 'B':
                # Neoden YY1 need the position on the bottom layer need position origin from bottom right corner, but KiCad only support one origin on all layer, so calculate it by using PCB BoundingBox Width
                bottomLayer.append(line + (value, footprint, pcbSize[1] - line[1], line[2], ))
        else:
            value = None
            footprint = None
            if line[3] == 'T':
                topLayer.append(line + (value, footprint, line[1], line[2],))
            elif line[3] == 'B':
                # Neoden YY1 need the position on the bottom layer need position origin from bottom right corner, but KiCad only support one origin on all layer, so calculate it by using PCB BoundingBox Width
                bottomLayer.append(line + (value, footprint, pcbSize[1] -  line[1], line[2],))
    return (topLayer, bottomLayer)

"""
    Export pos file for Neoden YY1
    Neoden YY1 file is in csv format.
"""
def posDataToCSV(layerData, prepend, filename):
    basename = os.path.basename(filename)
    basename = prepend + '_' + basename
    dirname = os.path.dirname(filename)
    with open(os.path.join(dirname, basename), "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        # First line is fixed with `NEODEN,YY1,P&P FILE,,,,,,,,,,,`
        writer.writerow(["NEODEN","YY1","P&P FILE","","","","","","","","","","",""])
        writer.writerow(["","","","","","","","","","","","","",""])
        # This line is for Panelized, make it deafult to not panelized, if anyone need panelized assembly, just change it on the machine.
        writer.writerow(["PanelizedPCB","UnitLength","0","UnitWidth","0","Rows","1","Columns","1",""])
        writer.writerow(["","","","","","","","","","","","","",""])
        # Neoden YY1 only support one Fiducial on the board, make Fiducial as 0 to disable Fiducial correction method, if anyone need it just set it on the machine.
        # OverallOffset is the global offset. This depends on the real task, just ignore it and set it on the machine when you need.
        writer.writerow(["Fiducial","1-X","0","1-Y","0","OverallOffsetX","0.00","OverallOffsetY","0.00",""])
        writer.writerow(["","","","","","","","","","","","","",""])
        # Automatic Nozzle Changer, Neoden YY1 only support 4 Nozzle Change task in one project. Nozzle Setting and Nozzle Station Setting is different for every user, so disable it by default, edit it by user when needed.
        # ["NozzleChange","(Enable Nozzle change task? ON/OFF)","BeforeComponent","1","Head1","Drop","Station2","PickUp","Station1",""]
        writer.writerow(["NozzleChange","OFF","BeforeComponent","1","Head1","Drop","Station2","PickUp","Station1",""])
        writer.writerow(["NozzleChange","OFF","BeforeComponent","2","Head2","Drop","Station3","PickUp","Station2",""])
        writer.writerow(["NozzleChange","OFF","BeforeComponent","1","Head1","Drop","Station1","PickUp","Station1",""])
        writer.writerow(["NozzleChange","OFF","BeforeComponent","1","Head1","Drop","Station1","PickUp","Station1",""])
        writer.writerow(["","","","","","","","","","","","","",""])
        # Neoden YY1 using Comment and Footprint for batch feeder selection when in edit mode. Neoden YY1 only support 2 decimal digits.
        # "Head" is for Picker, it has two picker, 0 for all picker, 1 for picker 1, 2 for picker 2.
        # "FeederNo" to define which feeder should be use, every user have different feeder setting, so just make it to use feeder 1 and left for user to edit.
        # "Mode" is how to confirm the component is picked, 0 - disable, 1 - camera, 2 - vacuum, 3 - camera and vacuum, 4 - camera for big IC
        # "Skip" should this line skipped by machine?
        writer.writerow(["Designator","Comment","Footprint","Mid X(mm)","Mid Y(mm)","Rotation","Head","FeederNo","Mount Speed(%)","Pick Height(mm)","Place Height(mm)","Mode","Skip"])
        for line in sorted(layerData, key=lambda x: naturalComponentKey(x[0])):
            line = list(line)
            skip = "0"
            if line[5] == None or line[6] == None:
                skip = "1"
                line[5] = "Unknown"
                line[6] = "Unknown"
            line = [line[0], line[5], transcodeFootprint(line[6]), line[7], line[8], line[4], "0", "1", "100", "0", "0", "1", skip]
            for i in [3, 4, 5]:
                line[i] = f"{line[i]:.2f}" # Most Fab houses expect only 2 decimal digits
            writer.writerow(line)

def posDataToFile(posData, pcbSize, bom, filename):
    topLayer, bottomLayer = posDataProcess(posData=posData,pcbSize = pcbSize, bom=bom)
    posDataToCSV(topLayer, 'top', filename)
    posDataToCSV(bottomLayer, 'bottom', filename)

def exportNeodenYY1(board, outputdir, schematic, ignore,
           corrections, correctionpatterns, nametemplate, drc):
    if schematic is None:
        raise RuntimeError("When outputing assembly data, schematic is required")
    
    ensureValidBoard(board)
    loadedBoard = pcbnew.LoadBoard(board)

    if drc:
        ensurePassingDrc(loadedBoard)

    refsToIgnore = parseReferences(ignore)
    removeComponents(loadedBoard, refsToIgnore)
    Path(outputdir).mkdir(parents=True, exist_ok=True)

    ensureValidSch(schematic)

    correctionFields = [x.strip() for x in corrections.split(",")]
    components = extractComponents(schematic)
    bom = collectBom(components, refsToIgnore)

    posData = collectPosData(loadedBoard, correctionFields,
        bom=components, posFilter=noFilter, correctionFile=correctionpatterns)
    boardReferences = set([x[0] for x in posData])
    bom = {key: [v for v in val if v in boardReferences] for key, val in bom.items()}
    bom = {key: val for key, val in bom.items() if len(val) > 0}

    boundingBox = loadedBoard.GetBoardEdgesBoundingBox()
    pcbSize = (boundingBox.GetHeight() / mm, boundingBox.GetWidth() / mm, )
    posDataToFile(posData, pcbSize, bom, os.path.join(outputdir, expandNameTemplate(nametemplate, "pos", loadedBoard) + ".csv"))
