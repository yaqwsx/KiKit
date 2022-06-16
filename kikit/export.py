# Based on https://github.com/KiCad/kicad-source-mirror/blob/master/demos/python_scripts_examples/gen_gerber_and_drill_files_board.py
import sys
import os
from enum import Enum

from pcbnewTransition import pcbnew
from pcbnew import *


class LayerToPlot(Enum):
    CuTop = (pcbnew.F_Cu, "Top layer")
    CuBottom = (pcbnew.B_Cu, "Bottom layer")
    PasteTop = (pcbnew.F_Paste, "Paste top")
    PasteBottom = (pcbnew.B_Paste, "Paste bottom")
    SilkTop = (pcbnew.F_SilkS, "Silk top")
    SilkBottom = (pcbnew.B_SilkS, "Silk bottom")
    MaskTop = (pcbnew.F_Mask, "Mask top")
    MaskBottom = (pcbnew.B_Mask, "Mask bottom")
    EdgeCuts = (pcbnew.Edge_Cuts, "Edges")
    CmtUser = (pcbnew.Cmts_User, "V-CUT")
    AdhesiveTop = (pcbnew.F_Adhes, "Adhesive top")
    AdhesiveBottom = (pcbnew.B_Adhes, "Adhesive bottom")

    def __init__(self, id: int, description: str):
        self.id = id
        self.description = description

fullGerberPlotPlan = [
    LayerToPlot.CuTop,
    LayerToPlot.CuBottom,
    LayerToPlot.PasteBottom,
    LayerToPlot.PasteTop,
    LayerToPlot.SilkTop,
    LayerToPlot.SilkBottom,
    LayerToPlot.MaskBottom,
    LayerToPlot.MaskTop,
    LayerToPlot.EdgeCuts,
    LayerToPlot.CmtUser
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


def hasCopper(plotPlan: list[LayerToPlot]):
    for layer_to_plot in plotPlan:
        if layer_to_plot.id in [F_Cu, B_Cu]:
            return True
    return False


def gerberImpl(boardfile, outputdir, plot_plan: list[LayerToPlot]=fullGerberPlotPlan, drilling=True, settings=exportSettingsJlcpcb):
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

    plot_controller = PLOT_CONTROLLER(board)
    plot_options = plot_controller.GetPlotOptions()

    plot_options.SetOutputDirectory(plotDir)

    plot_options.SetPlotFrameRef(False)
    plot_options.SetSketchPadLineWidth(FromMM(0.35))
    plot_options.SetAutoScale(False)
    plot_options.SetScale(1)
    plot_options.SetMirror(False)
    plot_options.SetUseGerberAttributes(False)
    plot_options.SetIncludeGerberNetlistInfo(True)
    plot_options.SetCreateGerberJobFile(True)
    plot_options.SetUseGerberProtelExtensions(settings["UseGerberProtelExtensions"])
    plot_options.SetExcludeEdgeLayer(settings["ExcludeEdgeLayer"])
    plot_options.SetScale(1)
    plot_options.SetUseAuxOrigin(settings["UseAuxOrigin"])
    plot_options.SetUseGerberX2format(False)
    plot_options.SetDrillMarksType(0) # NO_DRILL_SHAPE

    # This by gerbers only
    plot_options.SetSubtractMaskFromSilk(False)
    plot_options.SetDrillMarksType(PCB_PLOT_PARAMS.NO_DRILL_SHAPE)
    plot_options.SetSkipPlotNPTH_Pads(False)

    # prepare the gerber job file
    jobfile_writer = GERBER_JOBFILE_WRITER(board)

    for layer_to_plot in plot_plan:
        if layer_to_plot.id <= B_Cu:
            plot_options.SetSkipPlotNPTH_Pads(True)
        else:
            plot_options.SetSkipPlotNPTH_Pads(False)

        plot_controller.SetLayer(layer_to_plot.id)
        suffix = "" if settings["NoSuffix"] else layer_to_plot.name
        plot_controller.OpenPlotfile(suffix, PLOT_FORMAT_GERBER, layer_to_plot.description)
        jobfile_writer.AddGbrFile(layer_to_plot.id, os.path.basename(plot_controller.GetPlotFileName()))
        if plot_controller.PlotLayer() == False:
            print("plot error")

    if hasCopper(plot_plan):
        #generate internal copper layers, if any
        lyrcnt = board.GetCopperLayerCount()
        for innerlyr in range (1, lyrcnt - 1):
            plot_options.SetSkipPlotNPTH_Pads(True)
            plot_controller.SetLayer(innerlyr)
            lyrname = "" if settings["NoSuffix"] else 'inner{}'.format(innerlyr)
            plot_controller.OpenPlotfile(lyrname, PLOT_FORMAT_GERBER, "inner")
            jobfile_writer.AddGbrFile(innerlyr, os.path.basename(plot_controller.GetPlotFileName()))
            if plot_controller.PlotLayer() == False:
                print("plot error")

    # At the end you have to close the last plot, otherwise you don't know when
    # the object will be recycled!
    plot_controller.ClosePlot()

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
        drlwriter.CreateDrillandMapFilesSet(plot_controller.GetPlotDirName(), genDrl, genMap)

        # One can create a text file to report drill statistics
        rptfn = plot_controller.GetPlotDirName() + 'drill_report.rpt'
        drlwriter.GenDrillReportFile(rptfn)

    job_fn=os.path.dirname(plot_controller.GetPlotFileName()) + '/' + os.path.basename(boardfile)
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
        LayerToPlot.PasteBottom,
        LayerToPlot.PasteTop,
        LayerToPlot.EdgeCuts
    ]

    output = []
    for layer_to_plot in plot_plan:
        pctl.SetLayer(layer_to_plot.id)
        pctl.OpenPlotfile(layer_to_plot.name, PLOT_FORMAT_DXF, layer_to_plot.description)
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
