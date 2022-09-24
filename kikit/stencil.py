
from pcbnewTransition import pcbnew
from pcbnew import wxRect, wxPoint, PCB_SHAPE, BOARD
import numpy as np
import json
from collections import OrderedDict
from kikit.common import *
from kikit.defs import *
from kikit.substrate import Substrate, extractRings, toShapely, linestringToKicad
from kikit.export import gerberImpl, pasteDxfExport, LayerToPlot, PasteTop, PasteBottom, AdhesiveTop, AdhesiveBottom
from kikit.export import exportSettingsJlcpcb
import solid
import solid.utils
import subprocess
import shutil
from kikit.common import removeComponents, parseReferences

from shapely.geometry import Point


OUTER_BORDER = fromMm(7.5)
INNER_BORDER = fromMm(5)
MOUNTING_HOLES_COUNT = 3
MOUNTING_HOLE_R = fromMm(1)
HOLE_SPACING = fromMm(20)


class StencilType(Enum):
    SolderPaste = (PasteTop, PasteBottom)
    Adhesive = (AdhesiveTop, AdhesiveBottom)

    def __init__(self, top_layer: LayerToPlot, bottom_layer: LayerToPlot):
        self.top_layer = top_layer
        self.bottom_layer = bottom_layer


def addBottomCounterpart(board: BOARD, item: PCB_SHAPE, stencil_type: StencilType = StencilType.SolderPaste):
    item = item.Duplicate()
    item.SetLayer(stencil_type.bottom_layer.id)
    board.Add(item)

def addRoundedCorner(board: BOARD, center: wxPoint, start: wxPoint, end: wxPoint, thickness, stencil_type: StencilType = StencilType.SolderPaste):
    corner = pcbnew.PCB_SHAPE()
    corner.SetShape(STROKE_T.S_ARC)
    corner.SetCenter(toKiCADPoint((center[0], center[1])))
    corner.SetStart(toKiCADPoint((start[0], start[1])))

    if np.cross(start - center, end - center) > 0:
        corner.SetArcAngleAndEnd(fromDegrees(90), True)
    else:
        corner.SetArcAngleAndEnd(fromDegrees(-90), True)
    corner.SetWidth(thickness)
    corner.SetLayer(stencil_type.top_layer.id)
    board.Add(corner)
    addBottomCounterpart(board, corner, stencil_type)

def addLine(board: BOARD, start: wxPoint, end: wxPoint, thickness: int, stencil_type: StencilType = StencilType.SolderPaste):
    line = pcbnew.PCB_SHAPE()
    line.SetShape(STROKE_T.S_SEGMENT)
    line.SetStart(toKiCADPoint((start[0], start[1])))
    line.SetEnd(toKiCADPoint((end[0], end[1])))
    line.SetWidth(thickness)
    line.SetLayer(stencil_type.top_layer.id)
    board.Add(line)
    addBottomCounterpart(board, line, stencil_type)

def addBite(board: BOARD, origin: wxPoint, direction: wxPoint, normal: wxPoint, thickness: int, stencil_type: StencilType = StencilType.SolderPaste):
    """
    Adds a bite to the stencil, direction points to the bridge, normal points
    inside the stencil
    """
    direction = normalize(direction) * thickness
    normal = normalize(normal) * thickness
    center = toKiCADPoint((origin[0], origin[1])) + toKiCADPoint((normal[0], normal[1]))
    start = origin
    end = center + toKiCADPoint((direction[0], direction[1]))
    # addLine(board, end, end + normal / 2, thickness)
    addRoundedCorner(board, center, start, end, thickness, stencil_type)

def numberOfCuts(length, bridgeWidth, bridgeSpacing):
    """
    Return number of bridges which fit inside the length and cut length
    """
    count = int(np.floor((length + bridgeWidth) / (bridgeWidth + bridgeSpacing)))
    cutLength = (length - (count - 1) * bridgeWidth) / count
    return count, cutLength


def addFrame(board: BOARD, rect: wxRect, bridgeWidth: int, bridgeSpacing: int, clearance: int, stencil_type: StencilType = StencilType.SolderPaste):
    """
    Add rectangular frame to the board
    """
    R=fromMm(1)

    corners = [
        (tl(rect), toKiCADPoint((R, 0)), toKiCADPoint((0, R))), # TL
        (tr(rect), toKiCADPoint((0, R)), toKiCADPoint((-R, 0))), # TR
        (br(rect), toKiCADPoint((-R, 0)), toKiCADPoint((0, -R))), # BR
        (bl(rect), toKiCADPoint((0, -R)), toKiCADPoint((R, 0))) # BL
    ]
    for c, sOffset, eOffset in corners:
        addRoundedCorner(board, c + sOffset + eOffset, c + sOffset, c + eOffset, clearance, stencil_type)

    count, cutLength = numberOfCuts(rect.GetWidth() - 2 * R, bridgeWidth, bridgeSpacing)
    for i in range(count):
        start = rect.GetX() + R + i * bridgeWidth + i * cutLength
        end = start + cutLength

        y1, y2 = rect.GetY(), rect.GetY() + rect.GetHeight()
        addLine(board, toKiCADPoint((start, y1)), toKiCADPoint((end, y1)), clearance, stencil_type)
        if i != 0:
            addBite(board, toKiCADPoint((start, y1)), toKiCADPoint((-1, 0)), toKiCADPoint((0, 1)), clearance, stencil_type)
        if i != count - 1:
            addBite(board, toKiCADPoint((end, y1)), toKiCADPoint((1, 0)), toKiCADPoint((0, 1)), clearance, stencil_type)
        addLine(board, toKiCADPoint((start, y2)), toKiCADPoint((end, y2)), clearance, stencil_type)
        if i != 0:
            addBite(board, toKiCADPoint((start, y2)), toKiCADPoint((-1, 0)), toKiCADPoint((0, -1)), clearance, stencil_type)
        if i != count - 1:
            addBite(board, toKiCADPoint((end, y2)), toKiCADPoint((1, 0)), toKiCADPoint((0, -1)), clearance, stencil_type)

    count, cutLength = numberOfCuts(rect.GetHeight() - 2 * R, bridgeWidth, bridgeSpacing)
    for i in range(count):
        start = rect.GetY() + R + i * bridgeWidth + i * cutLength
        end = start + cutLength

        x1, x2 = rect.GetX(), rect.GetX() + rect.GetWidth()
        addLine(board, toKiCADPoint((x1, start)), toKiCADPoint((x1, end)), clearance, stencil_type)
        if i != 0:
            addBite(board, toKiCADPoint((x1, start)), toKiCADPoint((0, -1)), toKiCADPoint((1, 0)), clearance, stencil_type)
        if i != count - 1:
            addBite(board, toKiCADPoint((x1, end)), toKiCADPoint((0, 1)), toKiCADPoint((1, 0)), clearance, stencil_type)
        addLine(board, toKiCADPoint((x2, start)), toKiCADPoint((x2, end)), clearance, stencil_type)
        if i != 0:
            addBite(board, toKiCADPoint((x2, start)), toKiCADPoint((0, -1)), toKiCADPoint((-1, 0)), clearance, stencil_type)
        if i != count - 1:
            addBite(board, toKiCADPoint((x2, end)), toKiCADPoint((0, 1)), toKiCADPoint((-1, 0)), clearance, stencil_type)


def addHole(board: BOARD, position: wxPoint, radius: int, stencil_type: StencilType = StencilType.SolderPaste):
    circle = pcbnew.PCB_SHAPE()
    circle.SetShape(STROKE_T.S_CIRCLE)
    circle.SetCenter(toKiCADPoint((position[0], position[1])))
    # Set 3'oclock point of the circle to set radius
    circle.SetEnd(toKiCADPoint((position[0], position[1])) + toKiCADPoint((radius/2, 0)))

    circle.SetWidth(radius)
    circle.SetLayer(stencil_type.top_layer.id)
    board.Add(circle)
    addBottomCounterpart(board, circle, stencil_type)

def addJigFrame(board: BOARD, jigFrameSize: (int, int), bridgeWidth: int=fromMm(2),
                bridgeSpacing: int=fromMm(10), clearance: int=fromMm(0.5), stencil_type: StencilType = StencilType.SolderPaste):
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
    addFrame(board, cutSize, bridgeWidth, bridgeSpacing, clearance, stencil_type)

    for i in range(MOUNTING_HOLES_COUNT):
        x = frameSize.GetX() + OUTER_BORDER / 2 + (i + 1) * (frameSize.GetWidth() - OUTER_BORDER) / (MOUNTING_HOLES_COUNT + 1)
        addHole(board, toKiCADPoint((x, OUTER_BORDER / 2 + frameSize.GetY())), MOUNTING_HOLE_R, stencil_type)
        addHole(board, toKiCADPoint((x, - OUTER_BORDER / 2 +frameSize.GetY() + frameSize.GetHeight())), MOUNTING_HOLE_R, stencil_type)
    for i in range(MOUNTING_HOLES_COUNT):
        y = frameSize.GetY() + OUTER_BORDER / 2 + (i + 1) * (frameSize.GetHeight() - OUTER_BORDER) / (MOUNTING_HOLES_COUNT + 1)
        addHole(board, toKiCADPoint((OUTER_BORDER / 2 + frameSize.GetX(), y)), MOUNTING_HOLE_R, stencil_type)
        addHole(board, toKiCADPoint((- OUTER_BORDER / 2 +frameSize.GetX() + frameSize.GetWidth(), y)), MOUNTING_HOLE_R, stencil_type)

    PIN_TOLERANCE = fromMm(0.05)
    addHole(board, tl(frameSize) + toKiCADPoint((OUTER_BORDER / 2, OUTER_BORDER / 2)), MOUNTING_HOLE_R + PIN_TOLERANCE, stencil_type)
    addHole(board, tr(frameSize) + toKiCADPoint((-OUTER_BORDER / 2, OUTER_BORDER / 2)), MOUNTING_HOLE_R + PIN_TOLERANCE, stencil_type)
    addHole(board, br(frameSize) + toKiCADPoint((-OUTER_BORDER / 2, -OUTER_BORDER / 2)), MOUNTING_HOLE_R + PIN_TOLERANCE, stencil_type)
    addHole(board, bl(frameSize) + toKiCADPoint((OUTER_BORDER / 2, -OUTER_BORDER / 2)), MOUNTING_HOLE_R + PIN_TOLERANCE, stencil_type)

def jigMountingHoles(jigFrameSize, origin=toKiCADPoint((0, 0))):
    """ Get list of all mounting holes in a jig of given size """
    w, h = jigFrameSize
    holes = [
        toKiCADPoint((0, (w + INNER_BORDER) / 2)),
        toKiCADPoint((0, -(w + INNER_BORDER) / 2)),
        toKiCADPoint(((h + INNER_BORDER) / 2, 0)),
        toKiCADPoint((-(h + INNER_BORDER) / 2, 0)),
    ]
    return [x + origin for x in holes]

def createOuterPolygon(board, jigFrameSize, outerBorder):
    bBox = findBoardBoundingBox(board)
    centerpoint = rectCenter(bBox)
    holes = jigMountingHoles(jigFrameSize, centerpoint)

    outerSubstrate = Substrate(collectEdges(board, Layer.Edge_Cuts))
    outerSubstrate.substrates = outerSubstrate.substrates.buffer(outerBorder)
    tabs = []
    for hole in holes:
        tab, _ = outerSubstrate.tab(hole, centerpoint - hole, INNER_BORDER, maxHeight=fromMm(1000))
        tabs.append(tab)
    outerSubstrate.union(tabs)
    outerSubstrate.union([Point(x).buffer(INNER_BORDER / 2) for x in holes])
    outerSubstrate.millFillets(fromMm(3))
    return outerSubstrate.exterior(), holes

def createOffsetPolygon(board, offset):
    outerSubstrate = Substrate(collectEdges(board, Layer.Edge_Cuts))
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
        innerRing = mirrorX(innerRing, centerpoint[0])
    innerCutout = solid.utils.down(jigThickness)(
        solid.linear_extrude(height=3 * jigThickness, convexity=10)(solid.polygon(innerRing)))
    registerRing = createOffsetPolygon(board, tolerance).exterior.coords
    if topSide:
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
    return makeRegister(board, jigFrameSize, jigThickness, pcbThickness,
            outerBorder, innerBorder, tolerance, True)

def makeBottomRegister(board, jigFrameSize, jigThickness, pcbThickness,
                    outerBorder=fromMm(3), innerBorder=fromMm(1),
                    tolerance=fromMm(0.05)):
    """
    Create a SolidPython representation of the top register
    """
    return makeRegister(board, jigFrameSize, jigThickness, pcbThickness,
            outerBorder, innerBorder, tolerance, False)

def renderScad(infile, outfile):
    infile = os.path.abspath(infile)
    outfile = os.path.abspath(outfile)
    try:
        subprocess.run(["openscad", "-o", outfile, infile],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except subprocess.CalledProcessError as e:
        message = f"Cannot render {outfile}, OpenSCAD error:\n"
        message += (e.stdout.decode("utf-8") + "\n") if e.stdout is not None else ""
        message += (e.stderr.decode("utf-8") + "\n") if e.stderr is not None else ""
        raise RuntimeError(message)
    except FileNotFoundError as e:
        message = f"OpenSCAD is not available.\n"
        message += f"Did you install it? Program `openscad` has to be in PATH"
        raise RuntimeError(message)

def shapelyToSHAPE_POLY_SET(polygon):
    p = pcbnew.SHAPE_POLY_SET()
    p.AddOutline(linestringToKicad(polygon.exterior))
    return p

def cutoutComponents(board: BOARD, components: list[str], stencil_type: StencilType = StencilType.SolderPaste):
    topCutout = extractComponentPolygons(components, pcbnew.F_CrtYd)
    for polygon in topCutout:
        zone = pcbnew.PCB_SHAPE()
        zone.SetShape(STROKE_T.S_POLYGON)
        zone.SetPolyShape(shapelyToSHAPE_POLY_SET(polygon))
        zone.SetLayer(stencil_type.top_layer.id)
        board.Add(zone)
    bottomCutout = extractComponentPolygons(components, pcbnew.B_CrtYd)
    for polygon in bottomCutout:
        zone = pcbnew.PCB_SHAPE()
        zone.SetShape(STROKE_T.S_POLYGON)
        zone.SetPolyShape(shapelyToSHAPE_POLY_SET(polygon))
        zone.SetLayer(stencil_type.bottom_layer.id)
        board.Add(zone)

def setStencilLayerVisibility(boardName):
    prlPath = os.path.splitext(boardName)[0] + ".kicad_prl"
    try:
        with open(prlPath, encoding="utf-8") as f:
            # We use ordered dict, so we preserve the ordering of the keys and
            # thus, formatting
            prl = json.load(f, object_pairs_hook=OrderedDict)
    except FileNotFoundError:
        # KiCAD didn't generate project local settings, let's create an empty one
        prl = {
            "board": {}
        }
    prl["board"]["visible_layers"] = "ffc000c_7ffffffe"
    prl["board"]["visible_items"] = [
        1,
        2,
        3,
        4,
        9,
        10,
        12,
        13,
        21,
        22,
        24,
        25,
        26,
        27,
        28,
        29,
        30,
        34,
        35
    ]
    with open(prlPath, "w", encoding="utf-8") as f:
        json.dump(prl, f, indent=2)
    pass

from pathlib import Path
import os

def create(inputboard: str, outputdir: str, jigsize: (int, int), jigthickness: float, pcbthickness: float,
           registerborder: (float, float), tolerance: float, ignore: str, cutout: str, type: StencilType = StencilType.SolderPaste):
    board = pcbnew.LoadBoard(inputboard)
    removeComponents(board, parseReferences(ignore))
    cutoutComponents(board, getComponents(board, parseReferences(cutout)), type)

    Path(outputdir).mkdir(parents=True, exist_ok=True)

    jigsize = (fromMm(jigsize[0]), fromMm(jigsize[1]))
    addJigFrame(board, jigsize, stencil_type=type)

    stencilFile = os.path.join(outputdir, "stencil.kicad_pcb")
    board.Save(stencilFile)

    setStencilLayerVisibility(inputboard)
    plot_plan = [type.top_layer, type.bottom_layer]

    # get a copy of exportSettingsJlcpcb dictionary and
    # exclude the Edge.Cuts layer for creation of stencil gerber files
    exportSettings = exportSettingsJlcpcb.copy()
    exportSettings["ExcludeEdgeLayer"] = True
    gerberDir = os.path.join(outputdir, "gerber")
    gerberImpl(stencilFile, gerberDir, plot_plan, False, exportSettings)

    shutil.make_archive(os.path.join(outputdir, "gerbers"), "zip", gerberDir)

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

def getComponents(board, references):
    """
    Return a list of components based on designator
    """
    return [f for f in board.GetFootprints() if f.GetReference() in references]

def collectFootprintEdges(footprint, layer):
    """
    Return all edges on given layer in given footprint
    """
    return [e for e in footprint.GraphicalItems() if e.GetLayer() == layer]

def extractComponentPolygons(footprints, srcLayer):
    """
    Return a list of shapely polygons with holes for already placed components.
    The source layer defines the geometry on which the cutout is computed.
    Usually it a font or back courtyard
    """
    polygons = []
    for f in footprints:
       edges = collectFootprintEdges(f, srcLayer)
       for ring in extractRings(edges):
           polygons.append(toShapely(ring, edges))
    return polygons

def printedStencil(outlineDxf, holesDxf, extraHoles, thickness, frameHeight, frameWidth,
                   frameClearance, enlargeHoles, front):
    zScale = -1 if front else 1
    xRotate = 180 if front else 0
    substrate = solid.scale([1, 1, zScale])(printedStencilSubstrate(outlineDxf,
        thickness, frameHeight, frameWidth, frameClearance))
    holesOffset = solid.utils.up(0) if enlargeHoles == 0 else solid.offset(delta=enlargeHoles)
    holes = solid.linear_extrude(height=4*thickness, center=True)(
        holesOffset(solid.import_dxf(holesDxf)))
    substrate -= holes
    for h in extraHoles:
        substrate -= solid.scale([toMm(1), -toMm(1), 1])(
                solid.linear_extrude(height=4*thickness, center=True)(
                    solid.polygon(h.exterior.coords)))
    return solid.rotate(a=xRotate, v=[1, 0, 0])(substrate)

def createPrinted(inputboard, outputdir, pcbthickness, thickness, framewidth,
                  ignore, cutout, frameclearance, enlargeholes):
    """
    Create a 3D printed self-registering stencil.
    """
    board = pcbnew.LoadBoard(inputboard)
    refs = parseReferences(ignore)
    cutoutComponents = getComponents(board, parseReferences(cutout))
    removeComponents(board, refs)
    Path(outputdir).mkdir(parents=True, exist_ok=True)

    # We create the stencil based on DXF export. Using it avoids the necessity
    # to interpret KiCAD PAD shapes which constantly change with newer and newer
    # versions.
    height = min(pcbthickness, max(0.5, pcbthickness - 0.3))
    bottomPaste, topPaste, outline = pasteDxfExport(board, outputdir)
    # On Windows, OpenSCAD requires to use forward slashes instead of backslashes,
    # hence, the replacement:
    if os.name == "nt":
        bottomPaste = bottomPaste.replace("\\", "/")
        topPaste = topPaste.replace("\\", "/")
        outline = outline.replace("\\", "/")

    topCutout = extractComponentPolygons(cutoutComponents, pcbnew.F_CrtYd)
    bottomCutout = extractComponentPolygons(cutoutComponents, pcbnew.B_CrtYd)
    topStencil = printedStencil(outline, topPaste, topCutout, thickness, height,
        framewidth, frameclearance, enlargeholes, True)
    bottomStencil = printedStencil(outline, bottomPaste, bottomCutout, thickness,
        height, framewidth, frameclearance, enlargeholes, False)

    bottomStencilFile = os.path.join(outputdir, "bottomStencil.scad")
    solid.scad_render_to_file(bottomStencil, bottomStencilFile,
        file_header=f'$fa = 0.4; $fs = 0.4;', include_orig_code=True)
    renderScad(bottomStencilFile, os.path.join(outputdir, "bottomStencil.stl"))

    topStencilFile = os.path.join(outputdir, "topStencil.scad")
    solid.scad_render_to_file(topStencil, topStencilFile,
        file_header=f'$fa = 0.4; $fs = 0.4;', include_orig_code=True)
    renderScad(topStencilFile, os.path.join(outputdir, "topStencil.stl"))



