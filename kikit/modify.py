from pcbnewTransition import pcbnew
import re

def references(board, show, pattern, generous=False):
    """
    Show or hide references in a footprint. The generous mode hides references on
    all text items in the footprint, not just the reference text label.
    """
    for footprint in board.GetFootprints():
        if re.match(pattern, footprint.GetReference()):
            footprint.Reference().SetVisible(show)

    if not generous:
        return

    for x in footprint.GraphicalItems():
        if not isinstance(x, pcbnew.FP_TEXT):
            continue
        if x.GetText().strip() == "${REFERENCE}":
            x.SetVisible(show)


def values(board, show, pattern, generous=False):
    """
    Show or hide values in a footprint. The generous mode hides values on
    all text items in the footprint, not just the reference text label.
    """
    for footprint in board.GetFootprints():
        if re.match(pattern, footprint.GetReference()):
            footprint.Value().SetVisible(show)

    if not generous:
        return

    for x in footprint.GraphicalItems():
        if not isinstance(x, pcbnew.FP_TEXT):
            continue
        if x.GetText().strip() == "${VALUE}":
            x.SetVisible(show)
