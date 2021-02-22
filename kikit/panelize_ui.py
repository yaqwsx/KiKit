import click

def validateSpaceRadius(space, radius):
    if space <= 0:
        return
    if space < 2 * radius:
        raise RuntimeError(f"Fillet radius ({radius} mm) should to be less than " \
                           f"half space between boards ({space} mm).")

def getPlacementClass(name):
    from kikit.panelize import (BasicGridPosition, OddEvenColumnPosition,
        OddEvenRowsPosition, OddEvenRowsColumnsPosition)
    mapping = {
        "none": BasicGridPosition,
        "rows": OddEvenRowsPosition,
        "cols": OddEvenColumnPosition,
        "rowsCols": OddEvenRowsColumnsPosition
    }
    try:
        return mapping[name]
    except KeyError:
        raise RuntimeError(f"Invalid alternation option '{name}' passed. " +
            "Valid options are: " + ", ".join(mapping.keys()))

def addSingleFiducials(panel, singleFiducials):
    from kikit.panelize import Panel, fromMm, wxPoint, wxRectMM, fromDegrees
    for fiducial in singleFiducials:
        hOffset, vOffset, copperDia, openingDia = tuple(map(fromMm, fiducial[:4]))
        bottom = fiducial[4]
        offsetFromTop = fiducial[5]
        offsetFromLeft = fiducial[6]
        square = fiducial[7]

        minx, miny, maxx, maxy = panel.boardSubstrate.bounds()
        if bottom != offsetFromLeft:  # xor
            x = minx + hOffset
        else:
            x = maxx - hOffset
        if offsetFromTop:
            y = miny + vOffset
        else:
            y = maxy - vOffset

        panel.addFiducial(wxPoint(x, y), copperDia, openingDia, bottom=bottom, square=square)


@click.group()
def panelize():
    """
    Create a simple predefined panel patterns
    """
    pass

@click.command()
@click.argument("input", type=click.Path(dir_okay=False))
@click.argument("output", type=click.Path(dir_okay=False))
@click.option("--sourcearea", "-s", type=(float, float, float, float), help="x y w h in millimeters")
def extractBoard(input, output, sourcearea):
    """
    Extract a single board out of a file

    The extracted board is placed in the middle of the sheet
    """
    # Hide the import in the function to make KiKit start faster
    from kikit.panelize import Panel, fromMm, wxPointMM, wxRectMM, fromDegrees
    import sys
    try:
        panel = Panel()
        destination = wxPointMM(150, 100)
        area = wxRectMM(*sourcearea)
        panel.inheritDesignSettings(input)
        panel.inheritProperties(input)
        panel.appendBoard(input, destination, area, tolerance=fromMm(2))
        panel.save(output)
    except Exception as e:
        sys.stderr.write("An error occurred: " + str(e) + "\n")
        sys.stderr.write("No output files produced\n")
        sys.exit(1)

@click.command()
@click.argument("input", type=click.Path(dir_okay=False))
@click.argument("output", type=click.Path(dir_okay=False))
@click.option("--hspace", type=float, default=None,
    help="Horizontal space between boards. This option has a precedenc over --space")
@click.option("--vspace", type=float, default=None,
    help="Horizontal space between boards. This option has a precedenc over --space")
@click.option("--space", "-s", type=float, default=2,
    help="Space between boards. This option is overriden by --hspace and --vspace if specified")
@click.option("--gridsize", "-g", type=(int, int), default=(-1, -1), help="Panel size <rows> <cols>")
@click.option("--panelsize", "-p", type=(float, float), default=(None, None),
    help="Add a frame to a panel. The argument specifies it size as <width> <height>")
@click.option("--railsTb", type=float, default=None,
    help="Add bottom and top rail. Specify its thickness in mm")
@click.option("--railsLr", type=float, default=None,
    help="Add left and right rail. Specify its thickness in mm")
@click.option("--tabwidth", type=float, default=0,
    help="Size of the bottom/up tabs, leave unset for full width")
@click.option("--tabheight", type=float, default=0,
    help="Size of the left/right tabs, leave unset for full height")
@click.option("--htabs", type=int, default=1,
    help="Number of horizontal tabs for each board")
@click.option("--vtabs", type=int, default=1,
    help="Number of vertical tabs for each board")
@click.option("--vcuts", type=bool, help="Use V-cuts to separe the boards", is_flag=True)
@click.option("--vcutcurves", type=bool, help="Use V-cuts to approximate curves using starting and ending point", is_flag=True)
@click.option("--mousebites", type=(float, float, float), default=(None, None, None),
    help="Use mouse bites to separate the boards. Specify drill size, spacing and offset from cutedge (use 0.25 mm if unsure)")
@click.option("--radius", type=float, default=0, help="Add a radius to inner corners")
@click.option("--rotation", type=float, default=0,
    help="Rotate input board (in degrees)")
@click.option("--sourcearea", type=(float, float, float, float),
    help="x y w h in millimeters. If not specified, automatically detected", default=(None, None, None, None))
@click.option("--tolerance", type=float, default=5,
    help="Include items <tolerance> millimeters out of board outline")
@click.option("--renamenet", type=str, default="Board_{n}-{orig}",
    help="Rename pattern for nets. You can use '{n}' for board sequential number and '{orig}' for original net name")
@click.option("--renameref", type=str, default="{orig}",
    help="Rename pattern for references. You can use '{n}' for board sequential number and '{orig}' for original reference name")
@click.option("--tabsfrom", type=(str, float), multiple=True,
    help="Create tabs from lines in given layer. You probably want to specify --vtabs=0 and --htabs=0. Format <layer name> <tab width>")
@click.option("--framecutV", type=bool, help="Insert vertical cuts through the frame", is_flag=True)
@click.option("--framecutH", type=bool, help="Insert horizontal cuts through the frame", is_flag=True)
@click.option("--copperfill/--nocopperfill", help="Fill unsed areas of the panel with copper")
@click.option("--tooling", type=(float, float, float), default=(None, None, None),
    help="Add tooling holes to corners of the panel. Specify <horizontalOffset> <verticalOffset> <diameter>.")
@click.option("--fiducials", type=(float, float, float, float), default=(None, None, None, None),
    help="Add fiducials holes to corners of the panel. Specify <horizontalOffset> <verticalOffset> <copperDiameter> <openingDiameter>.")
@click.option("--singlefiducial", type=(float, float, float, float, bool, bool, bool, bool), default=(None, None, None, None, None, None, None, None), multiple=True,
    help="Add fiducials holes to corners of the panel. Specify <horizontalOffset> <verticalOffset> <copperDiameter> <openingDiameter> <bottomLayer> (True for top) <offsetFromTop> <offsetFromLeft> <square>.")
@click.option("--alternation", type=str, default="none",
    help="Rotate the boards based on their positions in the grid. Valid options: default, rows, cols, rowsCols")
def grid(input, output, space, hspace, vspace, gridsize, panelsize, tabwidth,
         tabheight, vcuts, mousebites, radius, sourcearea, vcutcurves, htabs,
         vtabs, rotation, tolerance, renamenet, renameref, tabsfrom, framecutv,
         framecuth, copperfill, railstb, railslr, tooling, fiducials, singlefiducial, alternation):
    """
    Create a regular panel placed in a frame.

    If you do not specify the panelsize, no frame is created
    """
    # Hide the import in the function to make KiKit start faster
    from kikit.panelize import Panel, fromMm, wxPointMM, wxRectMM, fromDegrees
    import sys
    try:
        panel = Panel()
        panel.inheritDesignSettings(input)
        panel.inheritProperties(input)
        rows, cols = gridsize
        if rows == -1 or cols == -1:
            raise RuntimeError("Gridsize is mandatory. Please specify the --gridsize option.")
        if hspace is None:
            hspace = space
        if vspace is None:
            vspace = space
        if sourcearea[0]:
            sourcearea = wxRectMM(*sourcearea)
        else:
            sourcearea = None
        if panelsize[0]:
            w, h = panelsize
            frame = True
            oht, ovt = fromMm(hspace), fromMm(vspace)
        else:
            frame = False
            oht, ovt = 0, 0
        if railstb:
            frame = False
            railstb = fromMm(railstb)
            ovt = fromMm(vspace)
        if railslr:
            frame = False
            railslr = fromMm(railslr)
            oht = fromMm(hspace)
        placementClass = getPlacementClass(alternation)

        validateSpaceRadius(vspace, radius)
        validateSpaceRadius(hspace, radius)
        tolerance = fromMm(tolerance)
        psize, cuts = panel.makeGrid(input, rows, cols, wxPointMM(50, 50),
            sourceArea=sourcearea, tolerance=tolerance,
            verSpace=fromMm(vspace), horSpace=fromMm(hspace),
            verTabWidth=fromMm(tabwidth), horTabWidth=fromMm(tabheight),
            outerHorTabThickness=oht, outerVerTabThickness=ovt,
            horTabCount=htabs, verTabCount=vtabs, rotation=fromDegrees(rotation),
            netRenamePattern=renamenet, refRenamePattern=renameref,
            forceOuterCutsV=railstb or frame, forceOuterCutsH=railslr or frame,
            placementClass=placementClass)
        tabs = []
        for layer, width in tabsfrom:
            tab, cut = panel.layerToTabs(layer, fromMm(width))
            cuts += cut
            tabs += tab
        panel.appendSubstrate(tabs)
        if vcuts:
            panel.makeVCuts(cuts, vcutcurves)
        if frame:
            (_, frame_cuts_v, frame_cuts_h) = panel.makeFrame(psize, fromMm(w), fromMm(h), fromMm(space))
            if framecutv:
                cuts += frame_cuts_v
            if framecuth:
                cuts += frame_cuts_h
        if railslr:
            panel.makeRailsLr(railslr)
        if railstb:
            panel.makeRailsTb(railstb)
        if fiducials[0] is not None:
            hOffset, vOffset, copperDia, openingDia = tuple(map(fromMm, fiducials))
            panel.addFiducials(hOffset, vOffset, copperDia, openingDia)
        if singlefiducial[0] is not None:
            addSingleFiducials(panel, singlefiducial)

        if tooling[0] is not None:
            hOffset, vOffset, dia = tuple(map(fromMm, tooling))
            panel.addTooling(hOffset, vOffset, dia)
        if mousebites[0]:
            drill, spacing, offset = mousebites
            panel.makeMouseBites(cuts, fromMm(drill), fromMm(spacing), fromMm(offset))
        panel.addMillFillets(fromMm(radius))
        if copperfill:
            panel.copperFillNonBoardAreas()
        panel.save(output)
    except Exception as e:
        sys.stderr.write("An error occurred: " + str(e) + "\n")
        sys.stderr.write("No output files produced\n")
        sys.exit(1)

@click.command()
@click.argument("input", type=click.Path(dir_okay=False))
@click.argument("output", type=click.Path(dir_okay=False))
@click.option("--hspace", type=float, default=None,
    help="Horizontal space between boards. This option has a precedenc over --space")
@click.option("--vspace", type=float, default=None,
    help="Horizontal space between boards. This option has a precedenc over --space")
@click.option("--space", "-s", type=float, default=2,
    help="Space between boards. This option is overriden by --hspace and --vspace if specified")
@click.option("--slotwidth", "-w", type=float, default=2, help="Milled slot width")
@click.option("--gridsize", "-g", type=(int, int), default=(-1, -1), help="Panel size <rows> <cols>")
@click.option("--panelsize", "-p", type=(float, float), help="<width> <height>", required=True)
@click.option("--tabwidth", type=float, default=5,
    help="Size of the bottom/up tabs")
@click.option("--tabheight", type=float, default=5,
    help="Size of the left/right tabs")
@click.option("--htabs", type=int, default=1,
    help="Number of horizontal tabs for each board")
@click.option("--vtabs", type=int, default=1,
    help="Number of vertical tabs for each board")
@click.option("--vcuts", type=bool, help="Use V-cuts to separe the boards", is_flag=True)
@click.option("--vcutcurves", type=bool, help="Use V-cuts to approximate curves using starting and ending point", is_flag=True)
@click.option("--mousebites", type=(float, float, float), default=(None, None, None),
    help="Use mouse bites to separate the boards. Specify drill size, spacing and offset from cutedge (use 0.25 mm if unsure)")
@click.option("--radius", type=float, default=0, help="Add a radius to inner corners")
@click.option("--rotation", type=float, default=0,
    help="Rotate input board (in degrees)")
@click.option("--sourcearea", type=(float, float, float, float),
    help="x y w h in millimeters. If not specified, automatically detected", default=(None, None, None, None))
@click.option("--tolerance", type=float, default=5,
    help="Include items <tolerance> millimeters out of board outline")
@click.option("--renamenet", type=str, default="Board_{n}-{orig}",
    help="Rename pattern for nets. You can use '{n}' for board sequential number and '{orig}' for original net name")
@click.option("--renameref", type=str, default="{orig}",
    help="Rename pattern for references. You can use '{n}' for board sequential number and '{orig}' for original reference name")
@click.option("--tabsfrom", type=(str, float), multiple=True,
    help="Create tabs from lines in given layer. You probably want to specify --vtabs=0 and --htabs=0. Format <layer name> <tab width>")
@click.option("--copperfill/--nocopperfill", help="Fill unsed areas of the panel with copper")
@click.option("--tooling", type=(float, float, float), default=(None, None, None),
    help="Add tooling holes to corners of the panel. Specify <horizontalOffset> <verticalOffset> <diameter>.")
@click.option("--fiducials", type=(float, float, float, float), default=(None, None, None, None),
    help="Add fiducials holes to corners of the panel. Specify <horizontalOffset> <verticalOffset> <copperDiameter> <openingDiameter>.")
@click.option("--singlefiducial", type=(float, float, float, float, bool, bool, bool, bool), default=(None, None, None, None, None, None, None, None), multiple=True,
    help="Add fiducials holes to corners of the panel. Specify <horizontalOffset> <verticalOffset> <copperDiameter> <openingDiameter> <bottomLayer> (True for top) <offsetFromTop> <offsetFromLeft> <square>.")
@click.option("--alternation", type=str, default="none",
    help="Rotate the boards based on their positions in the grid. Valid options: default, rows, cols, rowsCols")
def tightgrid(input, output, space, hspace, vspace, gridsize, panelsize,
         tabwidth, tabheight, vcuts, mousebites, radius, sourcearea, vcutcurves,
         htabs, vtabs, rotation, slotwidth, tolerance, renamenet, renameref,
         tabsfrom, copperfill, fiducials, tooling,
         alternation):
    """
    Create a regular panel placed in a frame by milling a slot around the
    boards' perimeters.
    """
    # Hide the import in the function to make KiKit start faster
    from kikit.panelize import Panel, fromMm, wxPointMM, wxRectMM, fromDegrees
    import sys
    try:
        panel = Panel()
        panel.inheritDesignSettings(input)
        panel.inheritProperties(input)
        rows, cols = gridsize
        if rows == -1 or cols == -1:
            raise RuntimeError("Gridsize is mandatory. Please specify the --gridsize option.")
        if hspace is None:
            hspace = space
        if vspace is None:
            vspace = space
        if sourcearea[0]:
            sourcearea = wxRectMM(*sourcearea)
        else:
            sourcearea = None
        w, h = panelsize
        placementClass = getPlacementClass(alternation)
        validateSpaceRadius(vspace, radius)
        validateSpaceRadius(hspace, radius)
        if 2 * radius > 1.1 * slotwidth:
            raise RuntimeError("The slot is too narrow for given radius (it has to be at least 10% larger")
        tolerance = fromMm(tolerance)
        psize, cuts = panel.makeTightGrid(input, rows, cols, wxPointMM(50, 50),
            verSpace=fromMm(vspace), horSpace=fromMm(hspace),
            slotWidth=fromMm(slotwidth), width=fromMm(w), height=fromMm(h),
            sourceArea=sourcearea, tolerance=tolerance,
            verTabWidth=fromMm(tabwidth), horTabWidth=fromMm(tabheight),
            verTabCount=htabs, horTabCount=vtabs, rotation=fromDegrees(rotation),
            netRenamePattern=renamenet, refRenamePattern=renameref,
            placementClass=placementClass)
        tabs = []
        for layer, width in tabsfrom:
            tab, cut = panel.layerToTabs(layer, fromMm(width))
            cuts += cut
            tabs += tab
        panel.appendSubstrate(tabs)
        panel.addMillFillets(fromMm(radius))
        if vcuts:
            panel.makeVCuts(cuts, vcutcurves)
        if fiducials[0] is not None:
            hOffset, vOffset, copperDia, openingDia = tuple(map(fromMm, fiducials))
            panel.addFiducials(hOffset, vOffset, copperDia, openingDia)
        if singlefiducial[0] is not None:
            addSingleFiducials(panel, singlefiducial)
        if tooling[0] is not None:
            hOffset, vOffset, dia = tuple(map(fromMm, tooling))
            panel.addTooling(hOffset, vOffset, dia)
        if mousebites[0]:
            drill, spacing, offset = mousebites
            panel.makeMouseBites(cuts, fromMm(drill), fromMm(spacing), fromMm(offset))
        if copperfill:
            panel.copperFillNonBoardAreas()
        panel.save(output)
    except Exception as e:
        sys.stderr.write("An error occurred: " + str(e) + "\n")
        sys.stderr.write("No output files produced\n")
        sys.exit(1)

panelize.add_command(extractBoard)
panelize.add_command(grid)
panelize.add_command(tightgrid)