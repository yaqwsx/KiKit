# Based on https://github.com/KiCad/kicad-source-mirror/blob/master/demos/python_scripts_examples/gen_gerber_and_drill_files_board.py
import sys
import os
import click
from pcbnew import *

@click.command()
@click.argument("boardfile", type=click.Path(dir_okay=False))
@click.argument("outputdir", type=click.Path(file_okay=False), default=None)
def gerber(boardfile, outputdir):
    """
    Export board to gerbers.

    If no output dir is specified, use '<board file>-gerber'
    """
    basename = os.path.basename(boardfile)
    if outputdir:
        plotDir = outputdir
    else:
        plotDir = basename + "-gerber"
    plotDir = os.path.abspath(plotDir)

    board = LoadBoard(boardfile)

    pctl = PLOT_CONTROLLER(board)
    popt = pctl.GetPlotOptions()

    popt.SetOutputDirectory(plotDir)

    popt.SetPlotFrameRef(False)
    popt.SetLineWidth(FromMM(0.35))
    popt.SetAutoScale(False)
    popt.SetScale(1)
    popt.SetMirror(False)
    popt.SetUseGerberAttributes(True)
    popt.SetIncludeGerberNetlistInfo(True)
    popt.SetCreateGerberJobFile(True)
    popt.SetUseGerberProtelExtensions(False)
    popt.SetExcludeEdgeLayer(False)
    popt.SetScale(1)
    popt.SetUseAuxOrigin(True)

    # This by gerbers only
    popt.SetSubtractMaskFromSilk(False)
    popt.SetDrillMarksType(PCB_PLOT_PARAMS.NO_DRILL_SHAPE)
    popt.SetSkipPlotNPTH_Pads(False)


    # prepare the gerber job file
    jobfile_writer = GERBER_JOBFILE_WRITER(board)

    plot_plan = [
        # name, id, comment
        ("CuTop", F_Cu, "Top layer"),
        ("CuBottom", B_Cu, "Bottom layer"),
        ("PasteBottom", B_Paste, "Paste Bottom"),
        ("PasteTop", F_Paste, "Paste top"),
        ("SilkTop", F_SilkS, "Silk top"),
        ("SilkBottom", B_SilkS, "Silk top"),
        ("MaskBottom", B_Mask, "Mask bottom"),
        ("MaskTop", F_Mask, "Mask top"),
        ("EdgeCuts", Edge_Cuts, "Edges"),
        ("CmtUser", Cmts_User, "V-CUT")
    ]

    for name, id, comment in plot_plan:
        if id <= B_Cu:
            popt.SetSkipPlotNPTH_Pads(True)
        else:
            popt.SetSkipPlotNPTH_Pads(False)

        pctl.SetLayer(id)
        pctl.OpenPlotfile(name, PLOT_FORMAT_GERBER, comment)
        print('plot {}'.format(pctl.GetPlotFileName()))
        jobfile_writer.AddGbrFile(id, os.path.basename(pctl.GetPlotFileName()))
        if pctl.PlotLayer() == False:
            print("plot error")

    #generate internal copper layers, if any
    lyrcnt = board.GetCopperLayerCount()

    for innerlyr in range (1, lyrcnt - 1):
        popt.SetSkipPlotNPTH_Pads(True)
        pctl.SetLayer(innerlyr)
        lyrname = 'inner{}'.format(innerlyr)
        pctl.OpenPlotfile(lyrname, PLOT_FORMAT_GERBER, "inner")
        print('plot {}'.format(pctl.GetPlotFileName()))
        if pctl.PlotLayer() == False:
            print("plot error")

    # At the end you have to close the last plot, otherwise you don't know when
    # the object will be recycled!
    pctl.ClosePlot()

    # Fabricators need drill files.
    # sometimes a drill map file is asked (for verification purpose)
    drlwriter = EXCELLON_WRITER(board)
    drlwriter.SetMapFileFormat(PLOT_FORMAT_PDF)

    mirror = False
    minimalHeader = False
    offset = wxPoint(0,0)
    # False to generate 2 separate drill files (one for plated holes, one for non plated holes)
    # True to generate only one drill file
    mergeNPTH = False
    drlwriter.SetOptions(mirror, minimalHeader, offset, mergeNPTH)

    metricFmt = True
    drlwriter.SetFormat(metricFmt)

    genDrl = True
    genMap = True
    print('create drill and map files in {}'.format(pctl.GetPlotDirName()))
    drlwriter.CreateDrillandMapFilesSet(pctl.GetPlotDirName(), genDrl, genMap);

    # One can create a text file to report drill statistics
    rptfn = pctl.GetPlotDirName() + 'drill_report.rpt'
    print('report: {}'.format(rptfn))
    drlwriter.GenDrillReportFile(rptfn)

    job_fn=os.path.dirname(pctl.GetPlotFileName()) + '/' + os.path.basename(boardfile)
    job_fn=os.path.splitext(job_fn)[0] + '.gbrjob'
    print('create job file {}'.format(job_fn))
    jobfile_writer.CreateJobFile(job_fn)

@click.command()
@click.argument("boardfile", type=click.Path(dir_okay=False))
@click.argument("outputdir", type=click.Path(file_okay=False), default=None)
def dxf(boardfile, outputdir):
    """
    Export board edges and pads to DXF.

    If no output dir is specified, use working directory.

    This command is designed for building 3D printed stencils
    """
    basename = os.path.dirname(boardfile)
    if outputdir:
        plotDir = outputdir
    else:
        plotDir = basename
    plotDir = os.path.abspath(plotDir)

    board = LoadBoard(boardfile)

    pctl = PLOT_CONTROLLER(board)
    popt = pctl.GetPlotOptions()

    popt.SetOutputDirectory(plotDir)
    popt.SetAutoScale(False)
    popt.SetScale(1)
    popt.SetMirror(False)
    popt.SetExcludeEdgeLayer(True)
    popt.SetScale(1)
    popt.SetDXFPlotUnits(DXF_PLOTTER.DXF_UNIT_MILLIMETERS)
    popt.SetDXFPlotPolygonMode(False)

    plot_plan = [
        # name, id, comment
        ("PasteBottom", B_Paste, "Paste Bottom"),
        ("PasteTop", F_Paste, "Paste top"),
        ("EdgeCuts", Edge_Cuts, "Edges"),
    ]

    for name, id, comment in plot_plan:
        pctl.SetLayer(id)
        pctl.OpenPlotfile(name, PLOT_FORMAT_DXF, comment)
        print('plot {}'.format(pctl.GetPlotFileName()))
        if pctl.PlotLayer() == False:
            print("plot error")
    pctl.ClosePlot()