# Simple, rather hacky parser for eeshema files (.sch). This is a mid-term
# workaround before proper support for scripting is introduced into Eeschema

import shlex
import os

class EeschemaException(Exception):
    pass

def getField(component, field):
    for f in component["fields"]:
        n = f["number"]
        if field == "Reference" and n == 0:
            return f["text"]
        if field == "Value" and n == 1:
            return f["text"]
        if field == "Footprint" and n == 2:
            return f["text"]
        if "name" in f and field == f["name"]:
            return f["text"]
    return None

def readEeschemaLine(file):
    line = ""
    quotationOpen = False
    while True:
        c = file.read(1)
        if c is None:
            raise EeschemaException("Cannot parse EEschema, line expected, got EOF")
        if c == '"':
            quotationOpen = not quotationOpen
        if c == '\n' and not quotationOpen:
            break
        line += c
    return line.strip()

def readHeader(file):
    VERSION_STRING = "EESchema Schematic File Version"
    DESCR_STRING = "$Descr "
    header = {}
    while True:
        line = readEeschemaLine(file)
        if line == "$EndDescr":
            return header

        if line.startswith(VERSION_STRING):
            header["version"] = line[len(VERSION_STRING):].strip()
        elif line.startswith("LIBS:"):
            header["libs"] = header.get("libs", []) + [line[len("LIBS:"):].strip()]
        elif line.startswith("EELAYER"):
            pass
        elif line.startswith(DESCR_STRING):
            header["size"] = line[len(DESCR_STRING):].split()
        elif line.startswith("Sheet"):
            items = shlex.split(line)
            header["sheet"] = (int(items[1]), int(items[2]))
        elif line.startswith("Title"):
            header["title"] = shlex.split(line)[1]
        elif line.startswith("Date"):
            header["date"] = shlex.split(line)[1]
        elif line.startswith("Comp"):
            header["company"] = shlex.split(line)[1]
        elif line.startswith("Rev"):
            header["revision"] = shlex.split(line)[1]
        elif line.startswith("Comment1"):
            header["comment1"] = shlex.split(line)[1]
        elif line.startswith("Comment2"):
            header["comment2"] = shlex.split(line)[1]
        elif line.startswith("Comment3"):
            header["comment3"] = shlex.split(line)[1]
        elif line.startswith("Comment4"):
            header["comment4"] = shlex.split(line)[1]
        elif line.startswith("encoding"):
            header["encoding"] = shlex.split(line)[1]
        else:
            raise EeschemaException(f"Unexpected line: '{line}'")

def readComponent(file, sheetPath=""):
    component = {}
    while True:
        line = readEeschemaLine(file)
        if line == "$EndComp":
            return component

        if line.startswith("L"):
            items = shlex.split(line)
            component["reference"] = items[2]
            component["name"] = items[1]
        elif line.startswith("U"):
            items = shlex.split(line)
            component["u"] = items[3]
            component["unit"] = int(items[1])
        elif line.startswith("P"):
            items = shlex.split(line)
            component["position"] = (int(items[1]), int(items[2]))
        elif line.startswith("F"):
            items = shlex.split(line)
            field = {
                "number": int(items[1]),
                "text": items[2],
                "orientation": items[3],
                "position": (int(items[4]), int(items[5])),
                "size": items[6],
                "flags": items[7],
                "justify": items[8],
                "style": items[9]
            }
            if field["number"] >= 4:
                field["name"] = items[10]
            component["fields"] = component.get("fields", []) + [field]
        elif line.startswith("AR"):
            # Hierarchical sheet reference. We assume all sheets are used within
            # the project, therefore we do not check validity of path
            items = shlex.split(line)
            path = None
            ref = None
            for item in items:
                if item.startswith('Path='):
                    path = item[len('Path='):]
                    break
            for item in items:
                if item.startswith('Ref='):
                    ref = item[len('Ref='):]
                    break
            if path is not None and ref is not None:
                compPath = sheetPath + "/" + component["u"]
                if path == compPath:
                    component["reference"] = ref
        else:
            items = shlex.split(line)
            try:
                int(items[0])
                if len(items) == 3 and items[0] == "1":
                    # Duplicate position entry
                    pass
                if len(items) == 4:
                    component["orientation"] = [int(x) for x in items[1:]]
            except ValueError:
                raise EeschemaException(f"Unexpected line: '{line}'")

def readSheet(file):
    # Note that the parser is incomplete an only extracts filename and reference
    # from the sheet as it is all we need currently
    sheet = {}
    while True:
        line = readEeschemaLine(file)
        if line == "$EndSheet":
            return sheet
        if line.startswith("F1 "):
            items = shlex.split(line)
            sheet["f1"] = items[1]
        elif line.startswith("U "):
            sheet["u"] = shlex.split(line)[1]

def extractComponents(filename, path=""):
    """
    Extract all components from the schematics
    """
    components = []
    sheets = []
    with open(filename, "r", encoding="utf-8") as file:
        header = readHeader(file)
        while True:
            line = file.readline()
            if not line:
                break
            line = line.strip()
            if line.startswith("$Comp"):
                components.append(readComponent(file, path))
            if line.startswith("$Sheet"):
                sheets.append(readSheet(file))
    for s in sheets:
        dirname = os.path.dirname(filename)
        sheetfilename = os.path.join(dirname, s["f1"])
        components += extractComponents(sheetfilename, path + "/" + s["u"])
    return components

def getUnit(component):
    return component["unit"]

def getReference(component):
    return component["reference"]