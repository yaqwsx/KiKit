from dataclasses import dataclass, field
from kikit.sexpr import Atom, parseSexprF
from itertools import islice
import os
from typing import Optional
from copy import deepcopy

class SchematicError(RuntimeError):
    pass

@dataclass
class Symbol:
    uuid: Optional[str] = None
    path: Optional[str] = None
    unit: Optional[int] = None
    lib_id: Optional[str] = None
    in_bom: bool = True
    on_board: bool = True
    dnp: bool = False
    properties: dict = field(default_factory=dict)

@dataclass
class SymbolInstance:
    symbol_path: Optional[str] = None
    path: Optional[str] = None
    reference: Optional[str] = None
    unit: Optional[int] = None
    value: Optional[str] = None
    footprint: Optional[str] = None

def getProperty(sexpr, field):
    for x in islice(sexpr, 1, None):
        if len(x) > 0 and \
            isinstance(x[0], Atom) and x[0].value == "property" and \
            isinstance(x[1], Atom) and x[1].value == field:
            return x[2].value
    return None

def isSymbol(sexpr):
    if isinstance(sexpr, Atom) or len(sexpr) == 0:
        return False
    item = sexpr[0]
    return isinstance(item, Atom) and item.value == "symbol"

def isSymbolInstances(sexpr):
    if isinstance(sexpr, Atom) or len(sexpr) == 0:
        return False
    item = sexpr[0]
    return isinstance(item, Atom) and item.value == "symbol_instances"

def isSheet(sexpr):
    if isinstance(sexpr, Atom) or len(sexpr) == 0:
        return False
    item = sexpr[0]
    return isinstance(item, Atom) and item.value == "sheet"

def isUuid(sexpr):
    if isinstance(sexpr, Atom) or len(sexpr) == 0:
        return False
    item = sexpr[0]
    return isinstance(item, Atom) and item.value == "uuid"

def isPath(sexpr):
    if isinstance(sexpr, Atom) or len(sexpr) == 0:
        return False
    item = sexpr[0]
    return isinstance(item, Atom) and item.value == "path"

def getUuid(sexpr):
    for x in islice(sexpr, 1, None):
        if x and x[0] == "uuid":
            return x[1].value
    return None

def getElement(sexpr, name):
    for x in islice(sexpr, 1, None):
        key = getAttributeKey(x)
        if key is None:
            continue
        if key == name:
            return x
    return None

def getAttributeKey(sexpr):
    if not sexpr:
        return None
    key = sexpr[0]
    if not isinstance(key, Atom):
        return None
    return key.value

def extractSymbol(sexpr, path):
    s = Symbol()
    for x in islice(sexpr, 1, None):
        key = getAttributeKey(x)
        if key is None:
            continue
        if key == "lib_id":
            s.lib_id = x[1].value
        elif key == "lib_id":
            s.unit = int(x[1].value)
        elif key == "uuid":
            s.uuid = x[1].value
            s.path = path + "/" + s.uuid
        elif key == "in_bom":
            s.in_bom = x[1].value == "yes"
        elif key == "on_board":
            s.on_board = x[1].value == "yes"
        elif key == "dnp":
            s.dnp = x[1].value == "yes"
        elif key == "property":
            s.properties[x[1].value] = x[2].value
    return s

def extractSymbolInstance(sexpr, sheetPath):
    i = SymbolInstance()
    seen = False

    def collectInstanceProperties(pathElem):
        nonlocal i, seen
        for x in islice(pathElem, 2, None):
            key = getAttributeKey(x)
            if key is None:
                continue
            seen = True
            if key == "reference":
                i.reference = x[1].value
            elif key == "unit":
                i.unit = int(x[1].value)
            elif key == "value":
                i.value = x[1].value
            elif key == "footprint":
                i.footprint = x[1].value

    for x in islice(sexpr, 1, None):
        key = getAttributeKey(x)
        if key is None:
            continue
        if key == "uuid":
            i.symbol_path = sheetPath + "/" + x[1].value
        elif key == "instances":
            projects = [proj for proj in islice(x, 1, None)
                if getAttributeKey(proj) == "project"]
            for proj in projects:
                paths = [path for path in islice(proj, 1, None)
                    if isPath(path) and sheetPath == path.items[1].value]
                for path in paths:
                    collectInstanceProperties(path)
    return i if seen else None

def extractSymbolInstanceV6(sexpr, path):
    s = SymbolInstance()
    s.symbol_path = path + sexpr[1].value
    for x in islice(sexpr, 2, None):
        key = getAttributeKey(x)
        if key is None:
            continue
        if key == "reference":
            s.reference = x[1].value
        elif key == "unit":
            s.unit = int(x[1].value)
        elif key == "value":
            s.value = x[1].value
        elif key == "footprint":
            s.footprint = x[1].value
    return s

def collectSymbols(filename, path = None):
    """
    Crawl given sheet and return two lists - one with symbols, one with
    symbol instances
    """
    isRoot = path is None
    with open(filename, encoding="utf-8") as f:
        sheetSExpr = parseSexprF(f)
    symbols, instances = [], []
    for item in sheetSExpr.items:
        if isUuid(item) and path is None:
            path = "/" + item.items[1].value
        if isSymbol(item):
            symbols.append(extractSymbol(item, path))
            instance = extractSymbolInstance(item, path)
            if instance is not None:
                instances.append(instance)
            continue
        if isSheet(item):
            f = getProperty(item, "Sheet file")
            if f is None:
                # v7 format
                f = getProperty(item, "Sheetfile")
            if f is None:
                raise SchematicError("Invalid format - no Sheet file")
            uuid = getUuid(item)
            dirname = os.path.dirname(filename)
            if len(dirname) > 0:
                f = dirname + "/" + f
            s, i = collectSymbols(f, path + "/" + uuid)
            symbols += s
            instances += i
            continue
        # v6 contains symbol instances in a top-level sheet in symbol instances
        if isSymbolInstances(item) and isRoot:
            for p in item.items:
                if isPath(p):
                    instances.append(extractSymbolInstanceV6(p, path))
            continue
    return symbols, instances


def getField(component, field):
    return component.properties.get(field, None)

def getUnit(component):
    return component.unit

def getReference(component):
    return component.properties["Reference"]

def extractComponents(filename):
    symbols, instances = collectSymbols(filename)
    symbolsDict = {x.path: x for x in symbols}

    assert len(symbols) == len(instances)

    components = []
    for inst in instances:
        s = deepcopy(symbolsDict[inst.symbol_path])
        # Note that s should be unique, so we can safely modify it
        if inst.reference is not None:
            s.properties["Reference"] = inst.reference
        if inst.value is not None:
            s.properties["Value"] = inst.value
        if inst.footprint is not None:
            s.properties["Footprint"] = inst.footprint
        if inst.unit is not None:
            s.unit = inst.unit
        components.append(s)
    return components
