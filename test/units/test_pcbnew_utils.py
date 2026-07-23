from kikit.pcbnew_utils import duplicateZone


def testDuplicateZoneUsesNewSignature():
    duplicate = object()

    class Zone:
        def Duplicate(self, addToParentGroup):
            assert addToParentGroup is False
            return duplicate

    assert duplicateZone(Zone()) is duplicate


def testDuplicateZoneFallsBackToOldSignature():
    duplicate = object()

    class Zone:
        def Duplicate(self):
            return duplicate

    assert duplicateZone(Zone()) is duplicate
