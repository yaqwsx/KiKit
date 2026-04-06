from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, TextIO, Tuple
from pathlib import Path

import pcbnew
from kikit.pcbnew_utils import EDA_UNITS_MM, EDA_UNITS_INCH, getItemDescription, resolveItem

from kikit.common import fromMm, toMm
from kikit.drc_ui import ReportLevel

NULL_UUID = "00000000-0000-0000-0000-000000000000"

def _find_kicad_cli() -> Optional[str]:
    """Locate the kicad-cli binary."""
    # Try PATH first
    result = shutil.which("kicad-cli")
    if result is not None:
        return result

    # Derive from the _pcbnew native module location
    try:
        import importlib.util
        spec = importlib.util.find_spec("_pcbnew")
        if spec is None or spec.origin is None:
            return None
        bindir = Path(os.path.realpath(spec.origin)).parent

        # macOS: _pcbnew.kiface is in Contents/Frameworks/, kicad-cli is in
        # Contents/MacOS/
        if "Contents/Frameworks" in str(bindir):
            bindir = bindir.parent / "MacOS"

        for name in ("kicad-cli", "kicad-cli.exe"):
            candidate = bindir / name
            if candidate.is_file():
                return str(candidate)
    except Exception:
        pass

    return None

ItemFingerprint = Tuple[int, int, str]

def roundCoord(x: int) -> int:
    # KiCAD doesn't round the values, it just cuts the decimal places. So let's
    # emulate that
    return round(x - 50, -4)


def getItemFingerprint(item: pcbnew.BOARD_ITEM):
    return (roundCoord(item.GetPosition()[0]), # Round down, since the output does the same
            roundCoord(item.GetPosition()[1]), # Round down, since the output does the same
            getItemDescription(item))

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
    position: pcbnew.VECTOR2I
    objects: List[pcbnew.BOARD_ITEM] = field(default_factory=list)

    def eqRepr(self):
        if len(self.objects) == 0:
            return (self.type, ())
        if len(self.objects) == 1:
            objRepr = str(self.objects[0].m_Uuid.AsString()) if isinstance(self.objects[0], pcbnew.BOARD_ITEM) else self.objects[0]
            return (self.type, objRepr)
        if len(self.objects) == 2 or self.type in ["starved_thermal"]:
            return (self.type, frozenset(str(x.m_Uuid.AsString()) for x in self.objects))
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
        if units == EDA_UNITS_MM:
            pos = f"{toMm(p[0]):.4f} mm, {toMm(p[1]):.4f} mm"
        if units == EDA_UNITS_INCH:
            pos = f"{pcbnew.ToMils(p[0]):.1f} mil, {pcbnew.ToMils(p[1]):.1f} mil"
        return f"@({pos}): {getItemDescription(obj, units)}"

    def eqRepr(self):
        if len(self.objects) == 0: # E.g., copper sliver has no related objects
            return (self.type, self.description)
        if len(self.objects) == 1:
            return (self.type, self.objects[0].m_Uuid.AsString())
        if len(self.objects) == 2:
            return (self.type, frozenset(str(x.m_Uuid.AsString()) for x in self.objects))
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

@dataclass
class CliViolation:
    """A DRC violation parsed from kicad-cli JSON output."""
    type: str
    description: str
    severity: str
    items: List[Dict] = field(default_factory=list)

    def format(self, units: Any) -> str:
        head = f"[{self.type}]: {self.description}\n    Severity: {self.severity}"
        lines = []
        for item in self.items:
            pos = item.get("pos", {})
            x, y = pos.get("x", 0), pos.get("y", 0)
            if units == EDA_UNITS_MM:
                pos_str = f"{x:.4f} mm, {y:.4f} mm"
            elif units == EDA_UNITS_INCH:
                pos_str = f"{x / 0.0254:.1f} mil, {y / 0.0254:.1f} mil"
            else:
                pos_str = "unknown"
            lines.append(f"    @({pos_str}): {item.get('description', '')}")
        return "\n".join([head] + lines)

    def eqRepr(self):
        uuids = [item["uuid"] for item in self.items if "uuid" in item]
        if len(uuids) == 0:
            return (self.type, self.description)
        if len(uuids) == 1:
            return (self.type, uuids[0])
        return (self.type, frozenset(uuids))

@dataclass
class CliDrcExclusion:
    """A DRC exclusion parsed from the project file without pcbnew."""
    type: str
    uuids: List[str] = field(default_factory=list)

    def eqRepr(self):
        if len(self.uuids) == 0:
            return (self.type, ())
        if len(self.uuids) == 1:
            return (self.type, self.uuids[0])
        return (self.type, frozenset(self.uuids))

def _readExclusionsFromProjectFile(boardFilename: str) -> List[CliDrcExclusion]:
    """Read DRC exclusions from .kicad_pro without needing pcbnew."""
    projectFilename = os.path.splitext(boardFilename)[0] + '.kicad_pro'
    try:
        with open(projectFilename, encoding="utf-8") as f:
            project = json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Board '{boardFilename}' has no project, cannot read DRC exclusions")
    try:
        exclusions = project["board"]["design_settings"]["drc_exclusions"]
    except KeyError:
        return []
    if len(exclusions) > 0 and isinstance(exclusions[0], list):
        exclusions = [x[0] for x in exclusions]
    result = []
    for e in exclusions:
        items = e.split("|")
        uuids = [u for u in items[3:] if u != NULL_UUID]
        result.append(CliDrcExclusion(items[0], uuids))
    return result

def _runCliDrc(kicadCli: str, boardFile: str, strict: bool) -> DrcReport:
    """Run DRC via kicad-cli and return a DrcReport with CliViolation objects."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
        tmpName = tmp.name
    try:
        cmd = [kicadCli, "pcb", "drc",
               "--format", "json",
               "--output", tmpName,
               "--units", "mm",
               "--severity-all",
               "--exit-code-violations"]
        if strict:
            cmd.append("--all-track-errors")
        cmd.append(boardFile)

        proc = subprocess.run(cmd, capture_output=True, text=True)
        # Exit 0 = clean, 5 = violations found (both ok), anything else = error
        if proc.returncode not in (0, 5):
            raise RuntimeError(
                f"kicad-cli DRC failed (exit {proc.returncode}): "
                f"{proc.stderr.strip() or proc.stdout.strip()}")

        with open(tmpName, encoding="utf-8") as f:
            data = json.load(f)
    finally:
        try:
            os.unlink(tmpName)
        except OSError:
            pass

    def parseViolations(items: List[Dict]) -> List[CliViolation]:
        return [CliViolation(
            type=v["type"],
            description=v["description"],
            severity=v["severity"],
            items=v.get("items", [])
        ) for v in items]

    return DrcReport(
        drc=parseViolations(data.get("violations", [])),
        unconnected=parseViolations(data.get("unconnected_items", [])),
        footprint=parseViolations(data.get("schematic_parity", []))
    )

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
        bodyMatch = re.match(r'\s*(.*); (Severity: )?(.*)', line)
        if bodyMatch is None:
            break
        v = Violation(
            type = headerMatch.group(1),
            description = headerMatch.group(2),
            rule = bodyMatch.group(1),
            severity = bodyMatch.group(3))
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
    projectPath = Path(board.GetFileName()).resolve().with_suffix(".kicad_pro")
    pcbnew.GetSettingsManager().LoadProject(str(projectPath))
    with tempfile.NamedTemporaryFile(mode="w+", delete=False) as tmpFile:
        try:
            tmpFile.close()
            result = pcbnew.WriteDRCReport(board, tmpFile.name,
                                           EDA_UNITS_MM, strict)
            if not result:
                raise RuntimeError("Cannot run DRC: Unspecified KiCAD error")
            with open(tmpFile.name, encoding="utf-8") as f:
                report = readReport(f, board)
        finally:
            tmpFile.close()
            os.unlink(tmpFile.name)
    return report

def deserializeExclusion(exclusionText: str, board: pcbnew.BOARD) -> DrcExclusion:
    items = exclusionText.split("|")
    objects = [resolveItem(board, pcbnew.KIID(x)) for x in items[3:]]
    objects = [x for x in objects if x is not None]
    return DrcExclusion(items[0],
                        pcbnew.VECTOR2I(int(items[1]), int(items[2])),
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
        with open(projectFilename, encoding="utf-8") as f:
            project = json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Board '{board.GetFileName()}' has no project, cannot read DRC exclusions")
    try:
        exclusions = project["board"]["design_settings"]["drc_exclusions"]
    except KeyError:
        return [] # There are no exclusions
    if len(exclusions) > 0 and isinstance(exclusions[0], list):
        exclusions = [x[0] for x in exclusions]
    return [deserializeExclusion(e, board) for e in exclusions]

def runImpl(board, useMm, ignoreExcluded, strict, level, yieldViolation):
    import faulthandler
    faulthandler.enable(sys.stderr)

    units = EDA_UNITS_MM if useMm else EDA_UNITS_INCH
    boardFile = board.GetFileName()

    kicadCli = _find_kicad_cli()
    if kicadCli is not None:
        report = _runCliDrc(kicadCli, boardFile, strict)
        if ignoreExcluded:
            report.pruneExclusions(_readExclusionsFromProjectFile(boardFile))
    else:
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
