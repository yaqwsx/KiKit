from __future__ import annotations
from typing import Dict, List, Set, Union
import numpy as np
import pcbnew
from kikit import units # type: ignore

from kikit.common import fromMm, readParameterList

KString = Union[str, pcbnew.UTF8]

def readKiKitProps(footprint):
    """
    Given a footprint, returns a string containing KiKit annotations.
    Annotations are in FP_TEXT starting with prefix `KIKIT:`.

    Returns a dictionary of key-value pairs.
    """
    for x in footprint.GraphicalItems():
        if not isinstance(x, pcbnew.FP_TEXT):
            continue
        text = x.GetText()
        if text.startswith("KIKIT:"):
            return readParameterList(text[len("KIKIT:"):])
    return {}

class KiKitAnnotation:
    pass

class TabAnnotation(KiKitAnnotation):
    def __init__(self, ref, origin, direction, width, maxLength=fromMm(100)):
        self.ref = ref
        self.origin = origin
        self.direction = direction
        self.width = width
        self.maxLength = maxLength

    @staticmethod
    def fromFootprint(footprint):
        origin = footprint.GetPosition()
        radOrientaion = footprint.GetOrientationRadians()
        direction = (np.cos(radOrientaion), -np.sin(radOrientaion))
        props = readKiKitProps(footprint)
        width = units.readLength(props["width"])
        return TabAnnotation(footprint.GetReference(), origin, direction, width)

class AnnotationReader:
    """
    Instance of this class can convert footprints into KiCAD annotations. Having
    a class instead of a function allows the users to specify source footprints.
    """
    def __init__(self) -> None:
        self._tabSources: Dict[str, Set[str]] = {}
        self._boardSources: Dict[str, Set[str]] = {}

    def registerTab(self, lib: KString, footprint: KString) -> None:
        self._register(self._tabSources, lib, footprint)

    def registerBoard(self, lib: KString, footprint: KString) -> None:
        self._register(self._boardSources, lib, footprint)

    def _register(self, where: Dict[str, Set[str]], lib: KString, footprint: KString) -> None:
        libstr = str(lib).lower()
        footprintstr = str(footprint).lower()

        if libstr not in where:
            where[libstr] = set()
        where[libstr].add(footprintstr)

    def _isIn(self, where: Dict[str, Set[str]], lib: str, footprint: str) -> bool:
        lib = lib.lower()
        footprint = footprint.lower()
        if lib not in where:
            return False
        return footprint in where[lib]


    def isAnnotation(self, footprint: pcbnew.FOOTPRINT) -> bool:
        """
        Given a footprint, decide if it is KiKit annotation
        """
        info = footprint.GetFPID()
        lib = str(info.GetLibNickname())
        fname = str(info.GetLibItemName())

        for aType in [self._tabSources, self._boardSources]:
            if self._isIn(aType, lib, fname):
                return True
        return False

    def convertToAnnotation(self, footprint: pcbnew.FOOTPRINT) -> List[KiKitAnnotation]:
        """
        Given a footprint, convert it into an annotation. One footprint might
        represent a zero or multiple annotations, so this function returns a list.
        """
        info = footprint.GetFPID()
        lib = str(info.GetLibNickname())
        fname = str(info.GetLibItemName())

        if self._isIn(self._tabSources, lib, fname):
            return [TabAnnotation.fromFootprint(footprint)]
        # We ignore Board annotation
        return []


    @staticmethod
    def getDefault() -> AnnotationReader:
        r = AnnotationReader()
        r.registerTab("kikit", "Tab")
        r.registerBoard("kikit", "Board")
        return r

