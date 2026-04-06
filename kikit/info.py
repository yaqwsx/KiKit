
from kikit.pcbnew_utils import KICAD_VERSION
from kikit.common import KIKIT_LIB
import sys
import click

@click.command()
def kicadversion():
    """
    Return version of KiCAD
    """
    print(f"{KICAD_VERSION[0]}.{KICAD_VERSION[1]}")

@click.command()
def drcapi():
    """
    Return version of the DRC API
    """
    print("1")

@click.command()
def lib():
    """
    Return KiKit library location
    """
    print(KIKIT_LIB)


@click.group()
def cli():
    """
    Get information about the KiCAD installation
    """
    pass

cli.add_command(kicadversion)
cli.add_command(drcapi)
cli.add_command(lib)
