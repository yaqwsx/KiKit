from dataclasses import dataclass, field
from kikit.sexpr import Atom, parseSexprF
from itertools import islice
import os

@dataclass
class Symbol:
    uuid: str = None
    path: str = None
    unit: int = None
    lib_id: str = None
    in_bom: bool = None
    on_board: bool = None
    properties: dict = field(default_factory=dict)

@dataclass
class SymbolInstance:
    path: str = None
    reference: str = None
    unit: int = None
    value: str = None
    footprint: str = None

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

def extractSymbol(sexpr, path):
    s = Symbol()
    for x in islice(sexpr, 1, None):
        if not x:
            continue
        key = x[0]
        if not isinstance(key, Atom):
            continue
        key = key.value
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
        elif key == "property":
            s.properties[x[1].value] = x[2].value
    return s

def extractSymbolInstance(sexpr):
    s = SymbolInstance()
    s.path = sexpr[1].value
    for x in islice(sexpr, 2, None):
        if not len(x) > 1:
            continue
        key = x[0]
        if not isinstance(key, Atom):
            continue
        key = key.value
        if key == "reference":
            s.reference = x[1].value
        elif key == "unit":
            s.unit = int(x[1].value)
        elif key == "value":
            s.value = x[1].value
        elif key == "footprint":
            s.footprint = x[1].value
    return s

def collectSymbols(filename, path=""):
    """
    Crawl given sheet and return two lists - one with symbols, one with
    symbol instances
    """
    with open(filename) as f:
        import time
        start_time = time.time()
        sheetSExpr = parseSexprF(f)
    symbols, instances = [], []
    for item in sheetSExpr.items:
        if isSymbol(item):
            symbols.append(extractSymbol(item, path))
            continue
        if isSheet(item):
            f = getProperty(item, "Sheet file")
            uuid = getUuid(item)
            dirname = os.path.dirname(filename)
            if len(dirname) > 0:
                f = dirname + "/" + f
            s, i = collectSymbols(f, path + "/" + uuid)
            symbols += s
            instances += i
            continue
        if isSymbolInstances(item):
            for p in item.items:
                if isPath(p):
                    instances.append(extractSymbolInstance(p))
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
        s = symbolsDict[inst.path]
        # Note that s should be unique, so we can safely modify it
        s.properties["Reference"] = inst.reference
        s.properties["Value"] = inst.value
        s.properties["Footprint"] = inst.footprint
        s.unit = inst.unit
        components.append(s)
    return components
