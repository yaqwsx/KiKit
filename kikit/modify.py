from pcbnewTransition import pcbnew
import re

def references(board, show, pattern):
    for footprint in board.GetFootprints():
        if re.match(pattern, footprint.GetReference()):
            footprint.Reference().SetVisible(show)
