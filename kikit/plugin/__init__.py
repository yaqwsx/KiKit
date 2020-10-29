import textwrap
import os
import sys
from pathlib import Path
import click

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
    width1 = len(max(table, key=lambda x: x[0])[0])
    width2 = len(max(table, key=lambda x: x[1])[1])

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

@click.group()
def cli():
    """
    Enable or disable KiKit's plugins for KiCAD (available via menu in
    KiCAD)
    """
    pass

cli.add_command(enable)
cli.add_command(list)

if __name__ == "__main__":
    cli()