from pcbnewTransition import pcbnew
import os
import shutil
from pathlib import Path
from kikit.export import gerberImpl, exportSettingsOSHPark, fullGerberPlotPlan
from kikit.fab.common import ensurePassingDrc

plotPlanNoVCuts = [(name, id, comment) for name, id, comment in fullGerberPlotPlan if name != "CmtUser"]

def exportOSHPark(board, outputdir, nametemplate, drc):
    """
    Prepare fabrication files for OSH Park
    """
    loadedBoard = pcbnew.LoadBoard(board)
    Path(outputdir).mkdir(parents=True, exist_ok=True)

    if drc:
        ensurePassingDrc(loadedBoard)

    gerberdir = os.path.join(outputdir, "gerber")
    shutil.rmtree(gerberdir, ignore_errors=True)
    gerberImpl(board, gerberdir, plot_plan=plotPlanNoVCuts, settings=exportSettingsOSHPark)
    archiveName = nametemplate.format("gerbers")
    shutil.make_archive(os.path.join(outputdir, archiveName), "zip", outputdir, "gerber")
