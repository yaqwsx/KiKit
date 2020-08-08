import pcbnew
from pcbnew import wxPoint
import numpy as np
from kikit.common import *
from kikit.defs import *
from kikit.substrate import Substrate
from kikit.export import gerberImpl, pasteDxfExport
import solid
import solid.utils
import subprocess
from kikit.common import removeComponents, parseReferences

from shapely.geometry import Point

import click

OUTER_BORDER = fromMm(7.5)
INNER_BORDER = fromMm(5)
MOUNTING_HOLES_COUNT = 3
MOUNTING_HOLE_R = fromMm(1)
HOLE_SPACING = fromMm(20)

def addBottomCounterpart(board, item):
    item = item.Duplicate()
    item.SetLayer(Layer.B_Paste)
    board.Add(item)

def addRoundedCorner(board, center, start, end, thickness):
    corner = pcbnew.DRAWSEGMENT()
    corner.SetShape(STROKE_T.S_ARC)
    corner.SetCenter(wxPoint(center[0], center[1]))
    corner.SetArcStart(wxPoint(start[0], start[1]))
    if np.cross(start - center, end - center) > 0:
        corner.SetAngle(fromDegrees(90))
    else:
        corner.SetAngle(fromDegrees(-90))
    corner.SetWidth(thickness)
    corner.SetLayer(Layer.F_Paste)
    board.Add(corner)
    addBottomCounterpart(board, corner)

def addLine(board, start, end, thickness):
    line = pcbnew.DRAWSEGMENT()
    line.SetShape(STROKE_T.S_SEGMENT)
    line.SetStart(wxPoint(start[0], start[1]))
    line.SetEnd(wxPoint(end[0], end[1]))
    line.SetWidth(thickness)
    line.SetLayer(Layer.F_Paste)
    board.Add(line)
    addBottomCounterpart(board, line)

def addBite(board, origin, direction, normal, thickness):
    """
    Adds a bite to the stencil, direction points to the bridge, normal points
    inside the stencil
    """
    direction = normalize(direction) * thickness
    normal = normalize(normal) * thickness
    center = wxPoint(origin[0], origin[1]) + wxPoint(normal[0], normal[1])
    start = origin
    end = center + wxPoint(direction[0], direction[1])
    # addLine(board, end, end + normal / 2, thickness)
    addRoundedCorner(board, center, start, end, thickness)

def numberOfCuts(length, bridgeWidth, bridgeSpacing):
    """
    Return number of bridges which fit inside the length and cut length
    """
    count = int(np.floor((length + bridgeWidth) / (bridgeWidth + bridgeSpacing)))
    cutLength = (length - (count - 1) * bridgeWidth) / count
    return count, cutLength

def addFrame(board, rect, bridgeWidth, bridgeSpacing, clearance):
    """
    Add rectangular frame to the board
    """
    R=fromMm(1)

    corners = [
        (tl(rect), wxPoint(R, 0), wxPoint(0, R)), # TL
        (tr(rect), wxPoint(0, R), wxPoint(-R, 0)), # TR
        (br(rect), wxPoint(-R, 0), wxPoint(0, -R)), # BR
        (bl(rect), wxPoint(0, -R), wxPoint(R, 0)) # BL
    ]
    for c, sOffset, eOffset in corners:
        addRoundedCorner(board, c + sOffset + eOffset, c + sOffset, c + eOffset, clearance)

    count, cutLength = numberOfCuts(rect.GetWidth() - 2 * R, bridgeWidth, bridgeSpacing)
    for i in range(count):
        start = rect.GetX() + R + i * bridgeWidth + i * cutLength
        end = start + cutLength

        y1, y2 = rect.GetY(), rect.GetY() + rect.GetHeight()
        addLine(board, wxPoint(start, y1), wxPoint(end, y1), clearance)
        if i != 0:
            addBite(board, wxPoint(start, y1), wxPoint(-1, 0), wxPoint(0, 1), clearance)
        if i != count - 1:
            addBite(board, wxPoint(end, y1), wxPoint(1, 0), wxPoint(0, 1), clearance)
        addLine(board, wxPoint(start, y2), wxPoint(end, y2), clearance)
        if i != 0:
            addBite(board, wxPoint(start, y2), wxPoint(-1, 0), wxPoint(0, -1), clearance)
        if i != count - 1:
            addBite(board, wxPoint(end, y2), wxPoint(1, 0), wxPoint(0, -1), clearance)

    count, cutLength = numberOfCuts(rect.GetHeight() - 2 * R, bridgeWidth, bridgeSpacing)
    for i in range(count):
        start = rect.GetY() + R + i * bridgeWidth + i * cutLength
        end = start + cutLength

        x1, x2 = rect.GetX(), rect.GetX() + rect.GetWidth()
        addLine(board, wxPoint(x1, start), wxPoint(x1, end), clearance)
        if i != 0:
            addBite(board, wxPoint(x1, start), wxPoint(0, -1), wxPoint(1, 0), clearance)
        if i != count - 1:
            addBite(board, wxPoint(x1, end), wxPoint(0, 1), wxPoint(1, 0), clearance)
        addLine(board, wxPoint(x2, start), wxPoint(x2, end), clearance)
        if i != 0:
            addBite(board, wxPoint(x2, start), wxPoint(0, -1), wxPoint(-1, 0), clearance)
        if i != count - 1:
            addBite(board, wxPoint(x2, end), wxPoint(0, 1), wxPoint(-1, 0), clearance)

def addHole(board, position, radius):
    circle = pcbnew.DRAWSEGMENT()
    circle.SetShape(STROKE_T.S_CIRCLE)
    circle.SetCenter(wxPoint(position[0], position[1]))
    circle.SetArcStart(wxPoint(position[0], position[1]) + wxPoint(radius/2, 0))
    circle.SetWidth(radius)
    circle.SetLayer(Layer.F_Paste)
    board.Add(circle)
    addBottomCounterpart(board, circle)

def addJigFrame(board, jigFrameSize, bridgeWidth=fromMm(2),
                bridgeSpacing=fromMm(10), clearance=fromMm(0.5)):
    """
    Given a Pcbnew board finds the board outline and creates a stencil for
    KiKit's stencil jig.

    Mainly, adds mounting holes and mouse bites to define the panel outline.

    jigFrameSize is a tuple (width, height).
    """
    bBox = findBoardBoundingBox(board)
    frameSize = rectByCenter(rectCenter(bBox),
        jigFrameSize[0] + 2 * (OUTER_BORDER + INNER_BORDER),
        jigFrameSize[1] + 2 * (OUTER_BORDER + INNER_BORDER))
    cutSize = rectByCenter(rectCenter(bBox),
        jigFrameSize[0] + 2 * (OUTER_BORDER + INNER_BORDER) - fromMm(1),
        jigFrameSize[1] + 2 * (OUTER_BORDER + INNER_BORDER) - fromMm(1))
    addFrame(board, cutSize, bridgeWidth, bridgeSpacing, clearance)

    for i in range(MOUNTING_HOLES_COUNT):
        x = frameSize.GetX() + OUTER_BORDER / 2 + (i + 1) * (frameSize.GetWidth() - OUTER_BORDER) / (MOUNTING_HOLES_COUNT + 1)
        addHole(board, wxPoint(x, OUTER_BORDER / 2 + frameSize.GetY()), MOUNTING_HOLE_R)
        addHole(board, wxPoint(x, - OUTER_BORDER / 2 +frameSize.GetY() + frameSize.GetHeight()), MOUNTING_HOLE_R)
    for i in range(MOUNTING_HOLES_COUNT):
        y = frameSize.GetY() + OUTER_BORDER / 2 + (i + 1) * (frameSize.GetHeight() - OUTER_BORDER) / (MOUNTING_HOLES_COUNT + 1)
        addHole(board, wxPoint(OUTER_BORDER / 2 + frameSize.GetX(), y), MOUNTING_HOLE_R)
        addHole(board, wxPoint(- OUTER_BORDER / 2 +frameSize.GetX() + frameSize.GetWidth(), y), MOUNTING_HOLE_R)

    PIN_TOLERANCE = fromMm(0.05)
    addHole(board, tl(frameSize) + wxPoint(OUTER_BORDER / 2, OUTER_BORDER / 2), MOUNTING_HOLE_R + PIN_TOLERANCE)
    addHole(board, tr(frameSize) + wxPoint(-OUTER_BORDER / 2, OUTER_BORDER / 2), MOUNTING_HOLE_R + PIN_TOLERANCE)
    addHole(board, br(frameSize) + wxPoint(-OUTER_BORDER / 2, -OUTER_BORDER / 2), MOUNTING_HOLE_R + PIN_TOLERANCE)
    addHole(board, bl(frameSize) + wxPoint(OUTER_BORDER / 2, -OUTER_BORDER / 2), MOUNTING_HOLE_R + PIN_TOLERANCE)

def jigMountingHoles(jigFrameSize, origin=wxPoint(0, 0)):
    """ Get list of all mounting holes in a jig of given size """
    w, h = jigFrameSize
    holes = [
        wxPoint(0, (w + INNER_BORDER) / 2),
        wxPoint(0, -(w + INNER_BORDER) / 2),
        wxPoint((h + INNER_BORDER) / 2, 0),
        wxPoint(-(h + INNER_BORDER) / 2, 0),
    ]
    return [x + origin for x in holes]

def createOuterPolygon(board, jigFrameSize, outerBorder):
    bBox = findBoardBoundingBox(board)
    centerpoint = rectCenter(bBox)
    holes = jigMountingHoles(jigFrameSize, centerpoint)

    outerSubstrate = Substrate(collectEdges(board, "Edge.Cuts"))
    outerSubstrate.substrates = outerSubstrate.substrates.buffer(outerBorder)
    tabs = []
    for hole in holes:
        tab, _ = outerSubstrate.tab(hole, centerpoint - hole, INNER_BORDER, fromMm(1000))
        tabs.append(tab)
    outerSubstrate.union(tabs)
    outerSubstrate.union([Point(x).buffer(INNER_BORDER / 2) for x in holes])
    outerSubstrate.millFillets(fromMm(3))
    return outerSubstrate.exterior(), holes

def createOffsetPolygon(board, offset):
    outerSubstrate = Substrate(collectEdges(board, "Edge.Cuts"))
    outerSubstrate.substrates = outerSubstrate.substrates.buffer(offset)
    return outerSubstrate.exterior()

def m2countersink():
    HEAD_DIA = fromMm(4.5)
    HOLE_LEN = fromMm(10)
    SINK_EXTRA = fromMm(0.3)
    sinkH = np.sqrt(HEAD_DIA**2 / 4)

    sink = solid.cylinder(d1=0, d2=HEAD_DIA, h=sinkH)
    sinkE = solid.cylinder(d=HEAD_DIA, h=SINK_EXTRA)
    hole = solid.cylinder(h=HOLE_LEN, d=fromMm(2))
    return sinkE + solid.utils.down(sinkH)(sink) + solid.utils.down(HOLE_LEN)(hole)

def mirrorX(linestring, origin):
    return [(2 * origin - x, y) for x, y in linestring]

def makeRegister(board, jigFrameSize, jigThickness, pcbThickness,
                 outerBorder, innerBorder, tolerance, topSide):
    bBox = findBoardBoundingBox(board)
    centerpoint = rectCenter(bBox)

    top = jigThickness - fromMm(0.15)
    pcbBottom = jigThickness - pcbThickness

    outerPolygon, holes = createOuterPolygon(board, jigFrameSize, outerBorder)
    outerRing = outerPolygon.exterior.coords
    if topSide:
        outerRing = mirrorX(outerRing, centerpoint[0])
    body = solid.linear_extrude(height=top, convexity=10)(solid.polygon(
        outerRing))

    innerRing = createOffsetPolygon(board, - innerBorder).exterior.coords
    if topSide:
        print("top")
        innerRing = mirrorX(innerRing, centerpoint[0])
    innerCutout = solid.utils.down(jigThickness)(
        solid.linear_extrude(height=3 * jigThickness, convexity=10)(solid.polygon(innerRing)))
    registerRing = createOffsetPolygon(board, tolerance).exterior.coords
    if topSide:
        print("top")
        registerRing = mirrorX(registerRing, centerpoint[0])
    registerCutout = solid.utils.up(jigThickness - pcbThickness)(
        solid.linear_extrude(height=jigThickness, convexity=10)(solid.polygon(registerRing)))

    register = body - innerCutout - registerCutout
    for hole in holes:
        register = register - solid.translate([hole[0], hole[1], top])(m2countersink())
    return solid.scale(toMm(1))(
            solid.translate([-centerpoint[0], -centerpoint[1], 0])(register))

def makeTopRegister(board, jigFrameSize, jigThickness, pcbThickness,
                    outerBorder=fromMm(3), innerBorder=fromMm(1),
                    tolerance=fromMm(0.05)):
    """
    Create a SolidPython representation of the top register
    """
    print("Top")
    return makeRegister(board, jigFrameSize, jigThickness, pcbThickness,
            outerBorder, innerBorder, tolerance, True)

def makeBottomRegister(board, jigFrameSize, jigThickness, pcbThickness,
                    outerBorder=fromMm(3), innerBorder=fromMm(1),
                    tolerance=fromMm(0.05)):
    """
    Create a SolidPython representation of the top register
    """
    print("Bottom")
    return makeRegister(board, jigFrameSize, jigThickness, pcbThickness,
            outerBorder, innerBorder, tolerance, False)

def renderScad(infile, outfile):
    infile = os.path.abspath(infile)
    outfile = os.path.abspath(outfile)
    subprocess.check_call(["openscad", "-o", outfile, infile])


from pathlib import Path
import os

@click.command()
@click.argument("inputBoard", type=click.Path(dir_okay=False))
@click.argument("outputDir", type=click.Path(dir_okay=True))
@click.option("--jigsize", type=(int, int), default=(100, 100),
    help="Jig frame size in mm: <width> <height>")
@click.option("--jigthickness", type=float, default=3,
    help="Jig thickness in mm")
@click.option("--pcbthickness", type=float, default=1.6,
    help="PCB thickness in mm")
@click.option("--registerborder", type=(float, float), default=(3, 1),
    help="Register borders in mm: <outer> <inner>")
@click.option("--tolerance", type=float, default=0.05,
    help="Enlarges the register by the tolerance value")
@click.option("--ignore", type=str, default="",
    help="Comma separated list of components references to exclude from the stencil")
def create(inputboard, outputdir, jigsize, jigthickness, pcbthickness,
           registerborder, tolerance, ignore):
    """
    Create stencil and register elements for manual paste dispensing jig.
    See more details at: https://github.com/yaqwsx/KiKit/blob/master/doc/stencil.md
    """
    board = pcbnew.LoadBoard(inputboard)
    refs = parseReferences(ignore)
    removeComponents(board, refs)

    Path(outputdir).mkdir(parents=True, exist_ok=True)

    jigsize = (fromMm(jigsize[0]), fromMm(jigsize[1]))
    addJigFrame(board, jigsize)

    stencilFile = os.path.join(outputdir, "stencil.kicad_pcb")
    board.Save(stencilFile)

    plotPlan = [
        # name, id, comment
        ("PasteBottom", pcbnew.B_Paste, "Paste Bottom"),
        ("PasteTop", pcbnew.F_Paste, "Paste top"),
    ]
    gerberDir = os.path.join(outputdir, "gerber")
    gerberImpl(stencilFile, gerberDir, plotPlan, False)
    gerbers = [os.path.join(gerberDir, x) for x in os.listdir(gerberDir)]
    subprocess.check_call(["zip", "-j",
        os.path.join(outputdir, "gerbers.zip")] + gerbers)

    jigthickness = fromMm(jigthickness)
    pcbthickness = fromMm(pcbthickness)
    outerBorder, innerBorder = fromMm(registerborder[0]), fromMm(registerborder[1])
    tolerance = fromMm(tolerance)
    topRegister = makeTopRegister(board, jigsize,jigthickness, pcbthickness,
        outerBorder, innerBorder, tolerance)
    bottomRegister = makeBottomRegister(board, jigsize,jigthickness, pcbthickness,
        outerBorder, innerBorder, tolerance)

    topRegisterFile = os.path.join(outputdir, "topRegister.scad")
    solid.scad_render_to_file(topRegister, topRegisterFile)
    renderScad(topRegisterFile, os.path.join(outputdir, "topRegister.stl"))

    bottomRegisterFile = os.path.join(outputdir, "bottomRegister.scad")
    solid.scad_render_to_file(bottomRegister, bottomRegisterFile)
    renderScad(bottomRegisterFile, os.path.join(outputdir, "bottomRegister.stl"))

def printedStencilSubstrate(outlineDxf, thickness, frameHeight, frameWidth, frameClearance):
    bodyOffset = solid.utils.up(0) if frameWidth + frameClearance == 0 else solid.offset(r=frameWidth + frameClearance)
    body = solid.linear_extrude(height=thickness + frameHeight)(
        bodyOffset(solid.import_dxf(outlineDxf)))
    boardOffset = solid.utils.up(0) if frameClearance == 0 else solid.offset(r=frameClearance)
    board = solid.utils.up(thickness)(
        solid.linear_extrude(height=thickness + frameHeight)(
            boardOffset(solid.import_dxf(outlineDxf))))
    return body - board

def printedStencil(outlineDxf, holesDxf, thickness, frameHeight, frameWidth,
                   frameClearance, enlargeHoles, front):
    zScale = -1 if front else 1
    xRotate = 180 if front else 0
    substrate = solid.scale([1, 1, zScale])(printedStencilSubstrate(outlineDxf,
        thickness, frameHeight, frameWidth, frameClearance))
    holesOffset = solid.utils.up(0) if enlargeHoles == 0 else solid.offset(delta=enlargeHoles)
    holes = solid.linear_extrude(height=4*thickness, center=True)(
        holesOffset(solid.import_dxf(holesDxf)))
    return solid.rotate(a=xRotate, v=[1, 0, 0])(substrate - holes)

@click.command()
@click.argument("inputBoard", type=click.Path(dir_okay=False))
@click.argument("outputDir", type=click.Path(dir_okay=True))
@click.option("--pcbthickness", type=float, default=1.6,
    help="PCB thickness in mm")
@click.option("--thickness", type=float, default=0.15,
    help="Stencil thickness in mm. Defines amount of paste dispensed")
@click.option("--framewidth", type=float, default=1,
    help="Register frame width")
@click.option("--ignore", type=str, default="",
    help="Comma separated list of components references to exclude from the stencil")
@click.option("--frameclearance", type=float, default=0,
    help="Clearance for the stencil register in milimeters")
@click.option("--enlargeholes", type=float, default=0,
    help="Enlarge pad holes by x mm")
def createPrinted(inputboard, outputdir, pcbthickness, thickness, framewidth,
                  ignore, frameclearance, enlargeholes):
    """
    Create a 3D printed self-registering stencil.
    """
    board = pcbnew.LoadBoard(inputboard)
    refs = parseReferences(ignore)
    removeComponents(board, refs)
    Path(outputdir).mkdir(parents=True, exist_ok=True)

    # We create the stencil based on DXF export. Using it avoids the necessity
    # to interpret KiCAD PAD shapes which constantly change with newer and newer
    # versions.
    height = min(pcbthickness, max(0.5, pcbthickness - 0.3))
    bottomPaste, topPaste, outline = pasteDxfExport(board, outputdir)
    topStencil = printedStencil(outline, topPaste, thickness, height,
        framewidth, frameclearance, enlargeholes, True)
    bottomStencil = printedStencil(outline, bottomPaste, thickness, height,
        framewidth, frameclearance, enlargeholes, False)

    bottomStencilFile = os.path.join(outputdir, "bottomStencil.scad")
    solid.scad_render_to_file(bottomStencil, bottomStencilFile,
        file_header=f'$fa = 0.4; $fs = 0.4;', include_orig_code=True)
    renderScad(bottomStencilFile, os.path.join(outputdir, "bottomStencil.stl"))

    topStencilFile = os.path.join(outputdir, "topStencil.scad")
    solid.scad_render_to_file(topStencil, topStencilFile,
        file_header=f'$fa = 0.4; $fs = 0.4;', include_orig_code=True)
    renderScad(topStencilFile, os.path.join(outputdir, "topStencil.stl"))


@click.group()
def stencil():
    """
    Create solder paste stencils
    """
    pass
stencil.add_command(create)
stencil.add_command(createPrinted)
