import pcbnew
import re

def references(board, show, pattern):
    b = pcbnew.LoadBoard(board)
    for module in b.GetModules():
        if re.match(pattern, module.GetReference()):
            module.Reference().SetVisible(show)
    b.Save(board)