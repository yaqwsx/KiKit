from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, TextIO, Tuple, Union
from pathlib import Path

from pcbnewTransition import isV6, pcbnew

from kikit.common import fromMm, toMm
from kikit.drc_ui import ReportLevel

ItemFingerprint = Tuple[int, int, str]

def roundCoord(x: int) -> int:
    # KiCAD doesn't round the values, it just cuts the decimal places. So let's
    # emulate that
    return round(x - 50, -4)

def getItemFingerprint(item: pcbnew.BOARD_ITEM):
    return (roundCoord(item.GetPosition()[0]), # Round down, since the output does the same
            roundCoord(item.GetPosition()[1]), # Round down, since the output does the same
            item.GetSelectMenuText(pcbnew.EDA_UNITS_MILLIMETRES))

def collectFingerprints(board: pcbnew.BOARD) -> Dict[ItemFingerprint, pcbnew.BOARD_ITEM]:
    """
    Traverse the board and collect fingerprints of all items in the board
    """
    fingerprints = {}
    def collect(items: Iterable[pcbnew.BOARD_ITEM]) -> None:
        nonlocal fingerprints
        for x in items:
            fingerprints[getItemFingerprint(x)] = x

    collect(board.GetDrawings())
    collect(board.GetFootprints())
    for f in board.GetFootprints():
        collect(f.Pads())
        collect(f.GraphicalItems())
        collect(f.Zones())
        collect([f.Reference(), f.Value()])
    collect(board.GetTracks())
    collect(board.Zones())

    return fingerprints

@dataclass
class DrcExclusion:
    type: str
    position: pcbnew.wxPoint
    objects: List[pcbnew.BOARD_ITEM] = field(default_factory=list)

    def eqRepr(self) -> Tuple[str, Union[Tuple[str, str], str]]:
        if len(self.objects) == 1:
            return (self.type, self.objects[0])
        if len(self.objects) == 2:
            return (self.type, tuple(str(x.m_Uuid.AsString()) for x in self.objects))
        raise RuntimeError("Unsupported exclusion object count")

@dataclass
class Violation:
    type: str
    description: str
    rule: str
    severity: str
    objects: List[pcbnew.BOARD_ITEM] = field(default_factory=list)

    def format(self, units: Any) -> str:
        head = f"[{self.type}]: {self.description}\n    {self.rule}; Severity: {self.severity}"
        tail = "\n".join(["    " + self._formatObject(x, units) for x in self.objects])
        return "\n".join([head] + [tail])

    def _formatObject(self, obj: pcbnew.BOARD_ITEM, units: Any) -> str:
        p = obj.GetPosition()
        pos = "unknown"
        if units == pcbnew.EDA_UNITS_MILLIMETRES:
            pos = f"{toMm(p[0]):.4f} mm, {toMm(p[1]):.4f} mm"
        if units == pcbnew.EDA_UNITS_INCHES:
            pos = f"{pcbnew.ToMils(p[0]):.1f} mil, {pcbnew.ToMils(p[1]):.1f} mil"
        return f"@({pos}): {obj.GetSelectMenuText(units)}"

    def eqRepr(self) -> Tuple[str, Union[Tuple[str, str], str]]:
        if len(self.objects) == 1:
            return (self.type, self.objects[0])
        if len(self.objects) == 2:
            return (self.type, tuple(str(x.m_Uuid.AsString()) for x in self.objects))
        raise RuntimeError("Unsupported violation object count")

@dataclass
class DrcReport:
    """
    Lists of DRC type violations
    """
    drc: List[Violation]
    unconnected: List[Violation]
    footprint: List[Violation]

    def items(self) -> Iterable[Tuple[str, List[Violation]]]:
        return {
            "drc": self.drc,
            "unconnected": self.unconnected,
            "footprint": self.footprint
        }.items()

    def pruneExclusions(self, exclusions: List[DrcExclusion]) -> None:
        """
        Given a list of exclusions, prune the report.
        """
        prints = set(x.eqRepr() for x in exclusions)
        self.drc = [x for x in self.drc if x.eqRepr() not in prints]
        self.unconnected = [x for x in self.unconnected if x.eqRepr() not in prints]
        self.footprint = [x for x in self.footprint if x.eqRepr() not in prints]

def readBoardItem(text: str,
                  fingerprints: Dict[ItemFingerprint, pcbnew.BOARD_ITEM]) \
                    -> pcbnew.BOARD_ITEM:
    """
    Given DRC report object description, try to find it in the board
    """
    itemMatch = re.match(r'\s*@\((-?\d*(\.\d*)?) mm, (-?\d*(\.\d*)?) mm\): (.*)$', text)
    if itemMatch is None:
        raise RuntimeError(f"Cannot parse board item from '{text}'")
    posX = float(itemMatch.group(1))
    posY = float(itemMatch.group(3))
    descr = itemMatch.group(5)
    fPrint = (roundCoord(fromMm(posX)), roundCoord(fromMm(posY)), str(descr))
    try:
        return fingerprints[fPrint]
    except KeyError:
        raise RuntimeError(f"Cannot find board item from '{text}', fingerprint: '{fPrint}'") # from None

def readViolations(reportFile: TextIO,
                   fingerprints: Dict[ItemFingerprint, pcbnew.BOARD_ITEM]) \
                        -> Tuple[str, List[Violation]]:
    violations = []
    line = reportFile.readline()
    while True:
        headerMatch = re.match(r'\[(.*)\]: (.*)\n', line)
        if headerMatch is None:
            break
        line = reportFile.readline()
        bodyMatch = re.match(r'\s*(.*); Severity: (.*)', line)
        if bodyMatch is None:
            break
        v = Violation(
            type = headerMatch.group(1),
            description = headerMatch.group(2),
            rule = bodyMatch.group(1),
            severity = bodyMatch.group(2))
        line = reportFile.readline()
        while line.startswith("    "):
            v.objects.append(readBoardItem(line, fingerprints))
            line = reportFile.readline()
        violations.append(v)

    return line, violations

def readReport(reportFile: TextIO, board: pcbnew.BOARD) -> DrcReport:
    fingerprints = collectFingerprints(board)
    drcV: List[Violation] = []
    unconnectedV: List[Violation] = []
    footprintV: List[Violation] = []
    line = reportFile.readline()
    while True:
        if len(line) == 0:
            break
        if re.match(r'\*\* Found \d+ DRC violations \*\*', line):
            line, drcV = readViolations(reportFile, fingerprints)
            continue
        if re.match(r'\*\* Found \d+ unconnected pads \*\*', line):
            line, unconnectedV = readViolations(reportFile, fingerprints)
            continue
        if re.match(r'\*\* Found \d+ Footprint errors \*\*', line):
            line, footprintV = readViolations(reportFile, fingerprints)
        line = reportFile.readline()
    return DrcReport(drcV, unconnectedV, footprintV)

def runBoardDrc(board: pcbnew.BOARD, strict: bool) -> DrcReport:
    projectPath = Path(board.GetFileName()).with_suffix(".kicad_pro")
    pcbnew.GetSettingsManager().LoadProject(str(projectPath))
    with tempfile.NamedTemporaryFile(mode="w+", delete=False) as tmpFile:
        try:
            tmpFile.close()
            result = pcbnew.WriteDRCReport(board, tmpFile.name,
                                           pcbnew.EDA_UNITS_MILLIMETRES, strict)
            if not result:
                raise RuntimeError("Cannot run DRC: Unspecified KiCAD error")
            with open(tmpFile.name) as f:
                report = readReport(f, board)
        finally:
            tmpFile.close()
            os.unlink(tmpFile.name)
    return report

def deserializeExclusion(exclusionText: str, board: pcbnew.BOARD) -> DrcExclusion:
    items = exclusionText.split("|")
    objects = [board.GetItem(pcbnew.KIID(x)) for x in items[3:]]
    objects = [x for x in objects if x is not None]
    return DrcExclusion(items[0],
                        pcbnew.wxPoint(int(items[1]), int(items[2])),
                        objects)

def serializeExclusion(exclusion: DrcExclusion) -> str:
    objIds = [x.m_Uuid.AsString() for x in exclusion.objects]
    while len(objIds) < 2:
        objIds.append("00000000-0000-0000-0000-000000000000")
    return "|".join([
        str(exclusion.type),
        str(exclusion.position[0]),
        str(exclusion.position[1])] + objIds
    )

def readBoardDrcExclusions(board: pcbnew.BOARD) -> List[DrcExclusion]:
    projectFilename = os.path.splitext(board.GetFileName())[0]+'.kicad_pro'
    try:
        with open(projectFilename) as f:
            project = json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Board '{board.GetFileName()}' has no project, cannot read DRC exclusions")
    try:
        exclusions = project["board"]["design_settings"]["drc_exclusions"]
    except KeyError:
        return [] # There are no exclusions
    return [deserializeExclusion(e, board) for e in exclusions]

def runImpl(board, useMm, ignoreExcluded, strict, level, yieldViolation):
    units = pcbnew.EDA_UNITS_MILLIMETRES if useMm else EDA_UNITS_INCHES
    report = runBoardDrc(board, strict)
    if ignoreExcluded:
        report.pruneExclusions(readBoardDrcExclusions(board))

    failed = False
    errorName = {
        "drc": "DRC violations",
        "unconnected": "unconnected pads",
        "footprint": "footprints errors"
    }
    for k, v in report.items():
        if len(v) == 0:
            continue
        failed = False
        failedCases = []
        for x in v:
            thisFailed = False
            if level == ReportLevel.warning and x.severity == "warning":
                thisFailed = True
            if x.severity == "error":
                thisFailed = True
            if thisFailed:
                failedCases.append(x)
            failed = failed or thisFailed
        if failedCases:

            msg = f"** Found {len(failedCases)} {errorName[k]}: **\n"
            msg += "\n".join([x.format(units) for x in failedCases])
            yieldViolation(msg)
    return failed
