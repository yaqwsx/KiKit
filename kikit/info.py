from kikit import pcbnew_compatibility
import sys
import click

version = pcbnew_compatibility.getVersion()


@click.command()
def kicadversion():
    """
    Return version of KiCAD
    """
    print(f"{version[0]}.{version[1]}")

@click.command()
def drcapi():
    """
    Return version of the DRC API
    """
    if pcbnew_compatibility.isV6(version):
        print("1")
    else:
        print("0")


@click.group()
def cli():
    """
    Get information about the KiCAD installation
    """
    pass

cli.add_command(kicadversion)
cli.add_command(drcapi)