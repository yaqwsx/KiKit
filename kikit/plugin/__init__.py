import textwrap
import os
import sys
import platform
from pathlib import Path
import click
from itertools import islice
from copy import deepcopy
from datetime import datetime
import shutil
from kikit.sexpr import Atom, SExpr, parseSexprF
from kikit.common import KIKIT_FP_LIB, KIKIT_SYM_LIB

# Tuple: package, name, description
availablePlugins = [
    ("hideReferences", "Show/hide references",
        "Allows you to batch show or hide references based on regular expression")
]

def registrationRoutine(allowedPlugins):
    """
    Build content of file for plugin registration
    """

    return "\n".join([
        textwrap.dedent(f"""
            try:
                from kikit.plugin import {x[0]}
                {x[0]}.plugin().register()
            except ImportError:
                pass
            """) for x in allowedPlugins])

@click.command()
def list():
    """
    Show available plugins.
    """
    table = [("Identifier", "Name", "Description")] + availablePlugins
    width1 = len(max(table, key=lambda x: len(x[0]))[0])
    width2 = len(max(table, key=lambda x: len(x[1]))[1])

    def rowStr(row):
        ident, name, help = row
        offset = width1 + width2 + 8
        lines = textwrap.wrap(help, width=(80 - offset))
        rowStr = f"{ident:<{width1}}    {name:<{width2}}    {lines[0]}"
        for line in lines[1:]:
            rowStr += "\n" + " " * offset + line
        return rowStr

    header = rowStr(table[0])
    print(header)
    print("-" * len(header))

    for row in availablePlugins:
        print(rowStr(row))

@click.command()
@click.argument("plugin", nargs=-1)
@click.option("--all", is_flag=True, help="Allow all plugins without explicitly naming them")
def enable(all, plugin):
    """
    Enable given plugins. Specify none to disable all plugins.
    """
    if all:
        plugins = availablePlugins
    else:
        pNames = [x[0] for x in availablePlugins]
        for p in plugin:
            if p not in pNames:
                sys.exit(f"Unknown plugin '{p}'. See available plugins via kikit-plugin list")
        plugins = [p for p in availablePlugins if p[0] in plugin]

    location = str(Path.home()) + "/.kicad_plugins/"
    Path(location).mkdir(exist_ok=True)
    location += "kikit_plugin.py"
    with open(location, "w") as f:
        f.write(registrationRoutine(plugins))

def getFpLibTablePath():
    """
    Return path to the FP Lib table
    """
    # Currently, we only support Linux and stable KiKit
    if platform.system() != "Linux":
        raise RuntimeError(f"Usupported platform '{platform.system()}'")
    return str(Path.home() / ".config" / "kicad" / "fp-lib-table")

def getSymLibTablePath():
    """
    Return path to the Sym Lib table
    """
    # Currently, we only support Linux and stable KiKit
    if platform.system() != "Linux":
        raise RuntimeError(f"Usupported platform '{platform.system()}'")
    return str(Path.home() / ".config" / "kicad" / "sym-lib-table")  

def findLib(libTable, lib):
    """
    Given footprint library table, find a library entry
    """
    if len(libTable) == 0 or (libTable[0] != "fp_lib_table" and libTable[0] !="sym_lib_table"):
        raise RuntimeError("Invalid table")
    for x in islice(libTable, 1, None):
        if x[0] != "lib":
            continue
        for y in islice(x, 1, None):
            if not isinstance(y, SExpr) or len(y) != 2:
                continue
            if y[0] == "name" and y[1] == lib:
                return x
    return None

def pushNewLib(libTable):
    """
    Add new KiCAD library into the table. Try to respect the formatting. Return
    the Sexpression for the newly inserted item.
    """
    if len(libTable) == 0 or (libTable[0] != "fp_lib_table" and libTable[0] !="sym_lib_table"):
        raise RuntimeError("Invalid table")
    if len(libTable) == 1:
        # There are no libraries, we can choose formatting
        s = SExpr([
            Atom("lib"),
            SExpr([Atom("name"), Atom("", " ")], " "),
            SExpr([Atom("type"), Atom("", " ")]),
            SExpr([Atom("uri"), Atom("", " ")]),
            SExpr([Atom("options"), Atom("", " ")]),
            SExpr([Atom("descr"), Atom("", " ")])
        ], "\n    ")
        libTable.trailingWhitespace = "\n"
        libTable.items.append(s)
        return s
    # There are already libraries, copy last item and erase it:
    s = deepcopy(libTable[-1])
    libTable.items.append(s)
    for x in islice(s, 1, None):
        x[1].value = ""
    return s

@click.command()
@click.option("--path", "-p",
    type=click.Path(dir_okay=False, file_okay=True, exists=True),
    default=None,
    help="You can optionally specify custom path for the fp_lib_table file")
def registerlib(path):
    """
    Add KiKit's footprint library into the global footprint library table. If
    the library has already been registered, update the path.
    """
    if path is None:
        path = getFpLibTablePath()
    with open(path, "r") as f:
        fpLibTable = parseSexprF(f)
        rest = f.read()
    kikitLib = findLib(fpLibTable, "kikit")
    if kikitLib is None:
        kikitLib = pushNewLib(fpLibTable)

    rewriteTable = {
        "name": "kikit",
        "type": "KiCAD",
        "uri": KIKIT_FP_LIB,
        "options": "",
        "descr": "KiKit Footprint library"
    }
    for x in islice(kikitLib, 1, None):
        x[1].value = rewriteTable[x[0].value]
    
    print(f"New footprint lib: {KIKIT_FP_LIB}")

    ident = datetime.now().strftime("%Y-%m-%d--%H-%M:%S")
    backupName = f"{path}.bak.{ident}"
    shutil.copy(path, backupName)
    print(f"A copy of the original {path} was made into {backupName}. ", end="")
    print("You can restore it if something goes wrong.", end="\n\n")

    with open(path, "w") as f:
        f.write(str(fpLibTable))
        f.write(rest)

    print(f"KiKit footprint library successfully added to the global footprint table '{path}'. Please restart KiCAD.")


@click.command()
@click.option("--path", "-p",
    type=click.Path(dir_okay=False, file_okay=True, exists=True),
    default=None,
    help="You can optionally specify custom path for the fp_sym_table file")
def registersym(path):
    """
    Add KiKit's symbol library into the global symbol library table. If
    the library has already been registered, update the path.
    """
    if path is None:
        path = getSymLibTablePath()
    with open(path, "r") as f:
        symLibTable = parseSexprF(f)
        rest = f.read()
    kikitLib = findLib(symLibTable, "kikit")
    if kikitLib is None:
        kikitLib = pushNewLib(symLibTable)

    rewriteTable = {
        "name": "kikit",
        "type": "KiCAD",
        "uri": KIKIT_SYM_LIB,
        "options": "",
        "descr": "KiKit Symbol library"
    }
    for x in islice(kikitLib, 1, None):
        x[1].value = rewriteTable[x[0].value]
    
    print(f"New footprint lib: {KIKIT_SYM_LIB}")

    ident = datetime.now().strftime("%Y-%m-%d--%H-%M:%S")
    backupName = f"{path}.bak.{ident}"
    shutil.copy(path, backupName)
    print(f"A copy of the original {path} was made into {backupName}. ", end="")
    print("You can restore it if something goes wrong.", end="\n\n")

    with open(path, "w") as f:
        f.write(str(symLibTable))
        f.write(rest)

    print(f"KiKit Symbol library successfully added to the global symbol table '{path}'. Please restart KiCAD.")







@click.group()
def cli():
    """
    Enable or disable KiKit's plugins for KiCAD (available via menu in
    KiCAD)
    """
    pass

cli.add_command(enable)
cli.add_command(list)
cli.add_command(registerlib)
cli.add_command(registersym)

if __name__ == "__main__":
    cli()