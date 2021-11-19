from pcbnewTransition import pcbnew, isV6
import sys
import tempfile
import re

class Violation:
    def __init__(self, type, description, severity):
        self.type = type
        self.description = description
        self.severity = severity
        self.objects = []

    def __str__(self):
        head = f"[{self.type}]: {self.description} Severity: {self.severity}"
        tail = "\n".join(["  " + x for x in self.objects])
        return "\n".join([head] + [tail])

def readViolations(reportFile):
    violations = []
    line = reportFile.readline()
    while True:
        m = re.match(r'\[(.*)\]: (.*) Severity: (.*)\n', line)
        if m is None:
            break
        v = Violation(m.group(1), m.group(2), m.group(3))
        line = reportFile.readline()
        while line.startswith("    "):
            v.objects.append(line.strip())
            line = reportFile.readline()
        violations.append(v)

    return line, violations

def readReport(reportFile):
    report = {}
    line = reportFile.readline()
    while True:
        if len(line) == 0:
            break
        if re.match(r'\*\* Found \d+ DRC violations \*\*', line):
            line, v = readViolations(reportFile)
            report["drc"] = v
            continue
        if re.match(r'\*\* Found \d+ unconnected pads \*\*', line):
            line, v = readViolations(reportFile)
            report["unconnected"] = v
            continue
        if re.match(r'\*\* Found \d+ Footprint errors \*\*', line):
            line, v = readViolations(reportFile)
            report["footprint"] = v
        line = reportFile.readline()
    return report

def runImpl(boardfile, useMm, strict):
    try:
        if not isV6():
            raise RuntimeError("This feature is available only with KiCAD 6.")
        units = pcbnew.EDA_UNITS_MILLIMETRES if useMm else EDA_UNITS_INCHES
        b = pcbnew.LoadBoard(boardfile)
        with tempfile.NamedTemporaryFile(mode="w+") as tmpFile:
            result = pcbnew.WriteDRCReport(b, tmpFile.name, units, strict)
            assert result

            tmpFile.seek(0)
            report = readReport(tmpFile)

            failed = False
            errorName = {
                "drc": "DRC violations",
                "unconnected": "unconnected pads",
                "footprint": "footprints errors"
            }
            for k, v in report.items():
                if len(v) == 0:
                    continue
                failed = True
                print(f"** Found {len(v)} {errorName[k]}: **")
                for x in v:
                    print(x)
                print("\n")
            if not failed:
                print("No DRC errors found.")
            else:
                print("Found some DRC violations. See the report above.")
            sys.exit(failed)
    except Exception as e:
        sys.stderr.write("An error occurred: " + str(e) + "\n")
        sys.exit(1)
