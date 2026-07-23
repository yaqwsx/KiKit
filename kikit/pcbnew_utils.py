import pcbnew

KICAD_VERSION = tuple(int(x) for x in pcbnew.GetMajorMinorVersion().split("."))

def _attr(name, fallback):
    """Resolve a pcbnew attribute that was renamed between v9 and v10."""
    v = getattr(pcbnew, name, None)
    if v is not None:
        return v
    return getattr(pcbnew, fallback)

# KiCad 10 shortened the enum names
EDA_UNITS_MM = _attr('EDA_UNITS_MM', 'EDA_UNITS_MILLIMETRES')
EDA_UNITS_INCH = _attr('EDA_UNITS_INCH', 'EDA_UNITS_INCHES')
DXF_UNITS_MM = _attr('DXF_UNITS_MM', 'DXF_UNITS_MILLIMETERS')
DIM_UNITS_MODE_MM = _attr('DIM_UNITS_MODE_MM', 'DIM_UNITS_MODE_MILLIMETRES')

def duplicateZone(zone):
    """
    Duplicate a zone without adding it to its parent group.

    KiCad 10.0.5 requires the addToParentGroup argument, while KiCad 9 and
    earlier KiCad 10 releases expose only the zero-argument signature.
    """
    try:
        duplicate = zone.Duplicate(False)
    except TypeError:
        return zone.Duplicate()
    return duplicate.Cast()

def resolveItem(board, kiid):
    # KiCad 10 renamed GetItem to ResolveItem and added a mandatory bool arg
    if hasattr(board, 'ResolveItem'):
        return board.ResolveItem(kiid, True)
    return board.GetItem(kiid)

def setDoNotAllowZoneFills(zone, value):
    # KiCad 10 renamed SetDoNotAllowCopperPour
    fn = getattr(zone, 'SetDoNotAllowZoneFills', None) or getattr(zone, 'SetDoNotAllowCopperPour')
    fn(value)

def getItemDescription(item, units=None):
    if units is None:
        units = EDA_UNITS_MM
    uProvider = pcbnew.UNITS_PROVIDER(pcbnew.pcbIUScale, units)
    return item.GetItemDescription(uProvider, True)

def increaseZonePriorities(board, amount=1):
    for zone in board.Zones():
        zone.SetAssignedPriority(zone.GetAssignedPriority() + amount)
