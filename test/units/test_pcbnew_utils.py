import pcbnew

from kikit.pcbnew_utils import duplicateZone


def testDuplicateZoneUsesNewSignature():
    duplicate = object()

    class BoardItem:
        def Cast(self):
            return duplicate

    class Zone:
        def Duplicate(self, addToParentGroup):
            assert addToParentGroup is False
            return BoardItem()

    assert duplicateZone(Zone()) is duplicate


def testDuplicateZoneFallsBackToOldSignature():
    duplicate = object()

    class Zone:
        def Duplicate(self):
            return duplicate

    assert duplicateZone(Zone()) is duplicate


def testDuplicateZoneCanBeAddedToZoneContainer():
    board = pcbnew.BOARD()
    zone = pcbnew.ZONE(board)
    zones = pcbnew.ZONES()

    zones.append(duplicateZone(zone))

    assert len(zones) == 1
