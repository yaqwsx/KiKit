import pcbnew

# KiCAD 6 renames some of the types, ensure compatibility by introducing aliases
# when KiCAD 5 is used

def getVersion():
    try:
        v = [int(x) for x in pcbnew.GetMajorMinorVersion().split(".")]
        return tuple(v)
    except AttributeError:
        # KiCAD 5 does not have such function, assume it version 5.something
        return 5, 0

def boardGetProperties(self):
    return {}

def boardSetProperties(self, p):
    pass

def isV6(version):
    if version[0] == 5 and version[1] == 99:
        return True
    return version[0] == 6

pcbnewVersion = getVersion()

if not isV6(pcbnewVersion):
    # Introduce type aliases
    pcbnew.PCB_SHAPE = pcbnew.DRAWSEGMENT
    pcbnew.FP_SHAPE = pcbnew.EDGE_MODULE
    pcbnew.PCB_TEXT = pcbnew.TEXTE_PCB
    pcbnew.FP_TEXT = pcbnew.TEXTE_MODULE
    pcbnew.PCB_PLOT_PARAMS.SetSketchPadLineWidth = pcbnew.PCB_PLOT_PARAMS.SetLineWidth
    pcbnew.PCB_TEXT.SetTextThickness = pcbnew.PCB_TEXT.SetThickness
    pcbnew.ZONES = pcbnew.ZONE_CONTAINER

    # Add board properties
    pcbnew.BOARD.GetProperties = boardGetProperties
    pcbnew.BOARD.SetProperties = boardSetProperties
