from typing import Set
from pcbnewTransition import pcbnew
from .defs import Layer
import re

def references(board: pcbnew.BOARD, show: bool, pattern: str,
               allowedLayers: Set[Layer] = set(Layer.all()),
               isSelectedItemOnly: bool = False) -> None:
    """
    Show or hide references in a footprint.
    """
    for footprint in board.GetFootprints():
        if isSelectedItemOnly and not footprint.IsSelected():
            continue
        if re.match(pattern, footprint.GetReference()) and footprint.Reference().GetLayer() in allowedLayers:
            footprint.Reference().SetVisible(show)
        for x in footprint.GraphicalItems():
            if not isinstance(x, pcbnew.FP_TEXT):
                continue
            if x.GetText().strip() in ["${REFERENCE}", "REF**"] and x.GetLayer() in allowedLayers:
                x.SetVisible(show)


def values(board: pcbnew.BOARD, show: bool, pattern: str,
           allowedLayers: Set[Layer] = set(Layer.all()),
           isSelectedItemOnly: bool = False) -> None:
    """
    Show or hide values in a footprint.
    """
    for footprint in board.GetFootprints():
        if isSelectedItemOnly and not footprint.IsSelected():
            continue
        if re.match(pattern, footprint.GetReference()) and footprint.Value().GetLayer() in allowedLayers:
            footprint.Value().SetVisible(show)
        for x in footprint.GraphicalItems():
            if not isinstance(x, pcbnew.FP_TEXT):
                continue
            if x.GetText().strip() in ["${VALUE}", "VAL**"] and x.GetLayer() in allowedLayers:
                x.SetVisible(show)
