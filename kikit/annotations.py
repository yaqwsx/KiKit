from __future__ import annotations
from typing import Dict, List, Set, Union
import numpy as np
from pcbnewTransition import pcbnew
from kikit import units # type: ignore

from kikit.common import fromMm, readParameterList

KString = Union[str, pcbnew.UTF8]

def readKiKitProps(footprint):
    """
    Given a footprint, returns a string containing KiKit annotations.
    Annotations are in fields starting with prefix `KIKIT:`.

    Returns a dictionary of key-value pairs.
    """
    for x in footprint.GraphicalItems():
        if not isinstance(x, pcbnew.FIELD_TYPE) and not isinstance(x, pcbnew.PCB_TEXT):
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
        radOrientation = footprint.GetOrientation().AsRadians()
        direction = (np.cos(radOrientation), -np.sin(radOrientation))
        props = readKiKitProps(footprint)
        if "width" not in props:
            raise ValueError("Tab annotation must a KiKit annotation text with 'width' property defined")
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
        represent zero or multiple annotations, so this function returns a list.
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
        """
        Return AnnotationReader object initialized with default annotations registered
        """
        r = AnnotationReader()
        r.registerTab("kikit", "Tab")
        r.registerBoard("kikit", "Board")

        # Since KiCAD 7.0 the plugins installed via the Plugin and Content Manager get prepended with `PCM_`
        r.registerTab("PCM_kikit", "Tab")
        r.registerBoard("PCM_kikit", "Board")
        return r

