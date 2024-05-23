import datetime
from pathlib import Path

from pcbnewTransition import pcbnew

import kikit

from .common import ensurePassingDrc, ensureValidBoard, expandNameTemplate, naturalComponentKey

def exportOpenPnp(board, outputdir, drc, nametemplate):
    ensureValidBoard(board)
    loadedBoard = pcbnew.LoadBoard(board)

    if drc:
        ensurePassingDrc(loadedBoard)

    Path(outputdir).mkdir(parents=True, exist_ok=True)
    posname = expandNameTemplate(nametemplate, "components", loadedBoard) + ".pos"

    footprints_in_pos_file = filter(lambda x: not x.IsExcludedFromPosFiles(), loadedBoard.GetFootprints())
    footprints = sorted(footprints_in_pos_file, key=lambda f: naturalComponentKey(f.GetReference()))

    if len(footprints) == 0:
        raise  RuntimeError("No components in board, nothing to do")

    footprint_texts = [
        ["# Ref", "Val", "Package", "PosX", "PosY", "Rot", "Side"]
    ]
    for f in footprints:
        sideName = "top" if f.GetLayer() == pcbnew.F_Cu else "bottom"
        footprint_texts.append([
            f"{f.GetReference()}-{f.m_Uuid.AsString()}",
            f"{f.GetValue()}",
            f"{f.GetFPIDAsString()}",
            f"{pcbnew.ToMM(f.GetX())}",
            f"{pcbnew.ToMM(f.GetY())}",
            f"{f.GetOrientation().AsDegrees()}",
            f"{sideName}"])

    colWidths = [
        max([len(row[i]) for row in footprint_texts]) for i in range(len(footprint_texts[0]))
    ]

    def format_row(file, row):
        SPACING = 5
        for elem, pad in zip(row, colWidths):
            file.write(elem)
            file.write(" " * (pad - len(elem) + SPACING))
        file.write("\n")

    with open(Path(outputdir) / posname, "w", encoding="utf-8") as outfile:
        outfile.write(f"### Footprint positions - created on {datetime.datetime.now()} ###\n")
        outfile.write(f"### Printed by KiKit {kikit.__version__}\n")
        outfile.write(f"## Unit = mm, Angle = deg.\n")
        outfile.write(f"## Side : All\n")
        for row in footprint_texts:
            format_row(outfile, row)
