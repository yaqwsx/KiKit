from kikit.pcbnew_compatibility import pcbnew
import re

def references(board, show, pattern):
    for module in board.GetFootprints():
        if re.match(pattern, module.GetReference()):
            module.Reference().SetVisible(show)
