# Based on https://github.com/KiCad/kicad-source-mirror/blob/master/demos/python_scripts_examples/gen_gerber_and_drill_files_board.py
import sys
import os
from pcbnewTransition import pcbnew
from pcbnewTransition.pcbnew import *

from kikit.defs import Layer

fullGerberPlotPlan = [
    # name, id, comment
    ("CuTop", Layer.F_Cu, "Top layer"),
    ("CuBottom", Layer.B_Cu, "Bottom layer"),
    ("PasteBottom", Layer.B_Paste, "Paste Bottom"),
    ("PasteTop", Layer.F_Paste, "Paste top"),
    ("SilkTop", Layer.F_SilkS, "Silk top"),
    ("SilkBottom", Layer.B_SilkS, "Silk top"),
    ("MaskBottom", Layer.B_Mask, "Mask bottom"),
    ("MaskTop", Layer.F_Mask, "Mask top"),
    ("EdgeCuts", Layer.Edge_Cuts, "Edges"),
    ("CmtUser", Layer.Cmts_User, "V-CUT")
]

exportSettingsJlcpcb = {
    "UseGerberProtelExtensions": True,
    "UseAuxOrigin": True,
    "ExcludeEdgeLayer": True,
    "MinimalHeader": False,
    "NoSuffix": False,
    "MergeNPTH": False,
    "MapFileFormat": PLOT_FORMAT_GERBER,
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
    "MapFileFormat": PLOT_FORMAT_PDF,
    "ZerosFormat": GENDRILL_WRITER_BASE.SUPPRESS_LEADING,
}

exportSettingsOSHPark = {
    "UseGerberProtelExtensions": True,
    "UseAuxOrigin": False,
    "ExcludeEdgeLayer": True,
    "MinimalHeader": False,
    "NoSuffix": False,
    "MergeNPTH": True,
    "MapFileFormat": PLOT_FORMAT_PDF,
    "ZerosFormat": GENDRILL_WRITER_BASE.DECIMAL_FORMAT,
}


def hasCopper(plotPlan):
    for _, layer, _ in plotPlan:
        if layer in [Layer.F_Cu, Layer.B_Cu]:
            return True
    return False

def setExcludeEdgeLayer(plotOptions, excludeEdge):
    try:
        plotOptions.SetExcludeEdgeLayer(excludeEdge)
    except AttributeError:
        if excludeEdge:
            plotOptions.SetLayerSelection(LSET())
        else:
            plotOptions.SetLayerSelection(LSET(Layer.Edge_Cuts))

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
    setExcludeEdgeLayer(popt, settings["ExcludeEdgeLayer"])
    popt.SetScale(1)
    popt.SetUseAuxOrigin(settings["UseAuxOrigin"])
    popt.SetUseGerberX2format(False)

    # This by gerbers only
    popt.SetSubtractMaskFromSilk(False)
    popt.SetDrillMarksType(pcbnew.DRILL_MARKS_NO_DRILL_SHAPE)
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
            raise RuntimeError("KiCAD plot error")

    if hasCopper(plot_plan):
        #generate internal copper layers, if any
        for i, layer in enumerate(Layer.innerCu(board.GetCopperLayerCount())):
            popt.SetSkipPlotNPTH_Pads(True)
            pctl.SetLayer(layer)
            layerName = "" if settings["NoSuffix"] else f"inner{i + 1}"
            pctl.OpenPlotfile(layerName, PLOT_FORMAT_GERBER, "inner")
            jobfile_writer.AddGbrFile(layer, os.path.basename(pctl.GetPlotFileName()))
            if pctl.PlotLayer() == False:
                raise RuntimeError("KiCAD plot error")

    # At the end you have to close the last plot, otherwise you don't know when
    # the object will be recycled!
    pctl.ClosePlot()

    if drilling:
        # Fabricators need drill files.
        # sometimes a drill map file is asked (for verification purpose)
        drlwriter = EXCELLON_WRITER(board)
        mapFmt = settings['MapFileFormat']
        drlwriter.SetMapFileFormat(mapFmt)

        mirror = False
        minimalHeader = settings["MinimalHeader"]
        if settings["UseAuxOrigin"]:
            offset = board.GetDesignSettings().GetAuxOrigin()
        else:
            offset = VECTOR2I(0, 0)

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
    setExcludeEdgeLayer(popt, True)
    popt.SetScale(1)
    popt.SetDXFPlotUnits(DXF_UNITS_MM)
    popt.SetDXFPlotPolygonMode(False)
    popt.SetDrillMarksType(DRILL_MARKS_NO_DRILL_SHAPE)

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
