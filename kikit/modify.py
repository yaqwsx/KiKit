from typing import Set
from pcbnewTransition import pcbnew
from .defs import Layer
import re

def references(board: pcbnew.BOARD, show: bool, pattern: str, generous: bool=False,
               allowedLayers: Set[Layer] = set(Layer.all())) -> None:
    """
    Show or hide references in a footprint. The generous mode hides references on
    all text items in the footprint, not just the reference text label.
    """
    for footprint in board.GetFootprints():
        if re.match(pattern, footprint.GetReference()) and footprint.Reference().GetLayer() in allowedLayers:
            footprint.Reference().SetVisible(show)

    if not generous:
        return

    for footprint in board.GetFootprints():
        for x in footprint.GraphicalItems():
            if not isinstance(x, pcbnew.FP_TEXT):
                continue
            if x.GetText().strip() in ["${REFERENCE}", "REF**"] and x.GetLayer() in allowedLayers:
                x.SetVisible(show)


def values(board: pcbnew.BOARD, show: bool, pattern: str, generous: bool=False,
           allowedLayers: Set[Layer] = set(Layer.all())) -> None:
    """
    Show or hide values in a footprint. The generous mode hides values on
    all text items in the footprint, not just the reference text label.
    """
    for footprint in board.GetFootprints():
        if re.match(pattern, footprint.GetReference()) and footprint.Value().GetLayer() in allowedLayers:
            footprint.Value().SetVisible(show)

    if not generous:
        return

    for footprint in board.GetFootprints():
        for x in footprint.GraphicalItems():
            if not isinstance(x, pcbnew.FP_TEXT):
                continue
            if x.GetText().strip() in ["${VALUE}", "VAL**"] and x.GetLayer() in allowedLayers:
                x.SetVisible(show)
