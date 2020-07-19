import pcbnew


def hasNonSMDPins(module):
    for pad in module.Pads():
        if pad.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
            return True
    return False