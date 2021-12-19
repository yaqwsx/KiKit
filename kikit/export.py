# Based on https://github.com/KiCad/kicad-source-mirror/blob/master/demos/python_scripts_examples/gen_gerber_and_drill_files_board.py
import sys
import os
from pcbnewTransition import pcbnew
from pcbnew import *

fullGerberPlotPlan = [
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

exportSettingsJlcpcb = {
    "UseGerberProtelExtensions": True,
    "UseAuxOrigin": False,
    "ExcludeEdgeLayer": True,
    "MinimalHeader": False,
    "NoSuffix": False,
    "MergeNPTH": True,
    "ZerosFormat": GENDRILL_WRITER_BASE.DECIMAL_FORMAT,
    "SubstractMaskFromSilk": True
}

exportSettingsPcbway = {
    "UseGerberProtelExtensions": True,
    "UseAuxOrigin": False,
    "ExcludeEdgeLayer": True,
    "MinimalHeader": True,
    "NoSuffix": True,
    "MergeNPTH": False,
    "ZerosFormat": GENDRILL_WRITER_BASE.SUPPRESS_LEADING,
}

exportSettingsOSHPark = {
    "UseGerberProtelExtensions": True,
    "UseAuxOrigin": False,
    "ExcludeEdgeLayer": True,
    "MinimalHeader": False,
    "NoSuffix": False,
    "MergeNPTH": True,
    "ZerosFormat": GENDRILL_WRITER_BASE.DECIMAL_FORMAT,
}


def hasCopper(plotPlan):
    for _, layer, _ in plotPlan:
        if layer in [F_Cu, B_Cu]:
            return True
    return False

def gerberImpl(boardfile, outputdir, plot_plan=fullGerberPlotPlan, drilling=True, settings=exportSettingsJlcpcb):
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
    popt.SetSketchPadLineWidth(FromMM(0.35))
    popt.SetAutoScale(False)
    popt.SetScale(1)
    popt.SetMirror(False)
    popt.SetUseGerberAttributes(False)
    popt.SetIncludeGerberNetlistInfo(True)
    popt.SetCreateGerberJobFile(True)
    popt.SetUseGerberProtelExtensions(settings["UseGerberProtelExtensions"])
    popt.SetExcludeEdgeLayer(settings["ExcludeEdgeLayer"])
    popt.SetScale(1)
    popt.SetUseAuxOrigin(settings["UseAuxOrigin"])
    popt.SetUseGerberX2format(False)

    # This by gerbers only
    popt.SetSubtractMaskFromSilk(False)
    popt.SetDrillMarksType(PCB_PLOT_PARAMS.NO_DRILL_SHAPE)
    popt.SetSkipPlotNPTH_Pads(False)

    # prepare the gerber job file
    jobfile_writer = GERBER_JOBFILE_WRITER(board)

    for name, id, comment in plot_plan:
        if id <= B_Cu:
            popt.SetSkipPlotNPTH_Pads(True)
        else:
            popt.SetSkipPlotNPTH_Pads(False)

        pctl.SetLayer(id)
        suffix = "" if settings["NoSuffix"] else name
        pctl.OpenPlotfile(suffix, PLOT_FORMAT_GERBER, comment)
        jobfile_writer.AddGbrFile(id, os.path.basename(pctl.GetPlotFileName()))
        if pctl.PlotLayer() == False:
            print("plot error")

    if hasCopper(plot_plan):
        #generate internal copper layers, if any
        lyrcnt = board.GetCopperLayerCount()
        for innerlyr in range (1, lyrcnt - 1):
            popt.SetSkipPlotNPTH_Pads(True)
            pctl.SetLayer(innerlyr)
            lyrname = "" if settings["NoSuffix"] else 'inner{}'.format(innerlyr)
            pctl.OpenPlotfile(lyrname, PLOT_FORMAT_GERBER, "inner")
            jobfile_writer.AddGbrFile(innerlyr, os.path.basename(pctl.GetPlotFileName()))
            if pctl.PlotLayer() == False:
                print("plot error")

    # At the end you have to close the last plot, otherwise you don't know when
    # the object will be recycled!
    pctl.ClosePlot()

    if drilling:
        # Fabricators need drill files.
        # sometimes a drill map file is asked (for verification purpose)
        drlwriter = EXCELLON_WRITER(board)
        drlwriter.SetMapFileFormat(PLOT_FORMAT_PDF)

        mirror = False
        minimalHeader = settings["MinimalHeader"]
        if settings["UseAuxOrigin"]:
            offset = board.GetDesignSettings().GetAuxOrigin()
        else:
            offset = wxPoint(0,0)

        # False to generate 2 separate drill files (one for plated holes, one for non plated holes)
        # True to generate only one drill file
        mergeNPTH = settings["MergeNPTH"]
        drlwriter.SetOptions(mirror, minimalHeader, offset, mergeNPTH)
        drlwriter.SetRouteModeForOvalHoles(False)

        metricFmt = True
        zerosFmt = settings["ZerosFormat"]
        drlwriter.SetFormat(metricFmt, zerosFmt)
        genDrl = True
        genMap = True
        drlwriter.CreateDrillandMapFilesSet(pctl.GetPlotDirName(), genDrl, genMap)

        # One can create a text file to report drill statistics
        rptfn = pctl.GetPlotDirName() + 'drill_report.rpt'
        drlwriter.GenDrillReportFile(rptfn)

    job_fn=os.path.dirname(pctl.GetPlotFileName()) + '/' + os.path.basename(boardfile)
    job_fn=os.path.splitext(job_fn)[0] + '.gbrjob'
    jobfile_writer.CreateJobFile(job_fn)

def pasteDxfExport(board, plotDir):
    pctl = PLOT_CONTROLLER(board)
    popt = pctl.GetPlotOptions()

    popt.SetOutputDirectory(os.path.abspath(plotDir))
    popt.SetAutoScale(False)
    popt.SetScale(1)
    popt.SetMirror(False)
    popt.SetExcludeEdgeLayer(True)
    popt.SetScale(1)
    popt.SetDXFPlotUnits(DXF_UNITS_MILLIMETERS)
    popt.SetDXFPlotPolygonMode(False)

    plot_plan = [
        # name, id, comment
        ("PasteBottom", B_Paste, "Paste Bottom"),
        ("PasteTop", F_Paste, "Paste top"),
        ("EdgeCuts", Edge_Cuts, "Edges"),
    ]

    output = []
    for name, id, comment in plot_plan:
        pctl.SetLayer(id)
        pctl.OpenPlotfile(name, PLOT_FORMAT_DXF, comment)
        output.append(pctl.GetPlotFileName())
        if pctl.PlotLayer() == False:
            print("plot error")
    pctl.ClosePlot()
    return tuple(output)

def dxfImpl(boardfile, outputdir):
    basename = os.path.dirname(boardfile)
    if outputdir:
        plotDir = outputdir
    else:
        plotDir = basename
    plotDir = os.path.abspath(plotDir)

    board = LoadBoard(boardfile)

    pasteDxfExport(board, plotDir)
