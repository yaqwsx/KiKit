import enum
import sys
import typing

import click
from click import Choice
from kikit.stencil import StencilType


# from https://github.com/pallets/click/pull/2210/files#diff-dcb534e6a7591b92836537d4655ddbd2f18e3b293c3420144c30a9ca08f65c4e
class EnumChoice(Choice):
    def __init__(self, enum_type: typing.Type[enum.Enum], case_sensitive: bool = True):
        super().__init__(
            choices=[element.name for element in enum_type],
            case_sensitive=case_sensitive,
        )
        self.enum_type = enum_type

    def convert(self, value: typing.Any, param: typing.Optional["Parameter"], ctx: typing.Optional["Context"]) -> typing.Any:
        value = super().convert(value=value, param=param, ctx=ctx)
        if value is None:
            return None
        return self.enum_type[value]


@click.command()
@click.argument("inputBoard", type=click.Path(dir_okay=False))
@click.argument("outputDir", type=click.Path(dir_okay=True))
@click.option("--pcbthickness", type=float, default=1.6,
    help="PCB thickness in mm")
@click.option("--thickness", type=float, default=0.15,
    help="Stencil thickness in mm. Defines amount of paste dispensed")
@click.option("--framewidth", type=float, default=1,
    help="Register frame width")
@click.option("--ignore", type=str, default="",
    help="Comma separated list of components references to exclude from the stencil")
@click.option("--cutout", type=str, default="",
    help="Comma separated list of components references to cutout from the stencil based on the courtyard")
@click.option("--frameclearance", type=float, default=0,
    help="Clearance for the stencil register in milimeters")
@click.option("--enlargeholes", type=float, default=0,
    help="Enlarge pad holes by x mm")
def createPrinted(**kwargs):
    """
    Create a 3D printed self-registering stencil.
    """
    from kikit import stencil
    try:
        return stencil.createPrinted(**kwargs)
    except Exception as e:
        sys.stderr.write(f"{e}\n")

@click.command()
@click.argument("inputBoard", type=click.Path(dir_okay=False))
@click.argument("outputDir", type=click.Path(dir_okay=True))
@click.option("--jigsize", type=(int, int), default=(100, 100),
    help="Jig frame size in mm: <width> <height>")
@click.option("--jigthickness", type=float, default=3,
    help="Jig thickness in mm")
@click.option("--pcbthickness", type=float, default=1.6,
    help="PCB thickness in mm")
@click.option("--registerborder", type=(float, float), default=(3, 1),
    help="Register borders in mm: <outer> <inner>")
@click.option("--tolerance", type=float, default=0.05,
    help="Enlarges the register by the tolerance value")
@click.option("--ignore", type=str, default="",
    help="Comma separated list of components references to exclude from the stencil")
@click.option("--cutout", type=str, default="",
    help="Comma separated list of components references to cutout from the stencil based on the courtyard")
@click.option("--type", type=EnumChoice(StencilType, case_sensitive=False), default="solderpaste",
    help="Stencil for SolderPaste or Adhesive")
def create(**kwargs):
    """
    Create stencil and register elements for manual paste dispensing jig.
    See more details at: https://github.com/yaqwsx/KiKit/blob/master/doc/stencil.md
    """
    from kikit import stencil
    from kikit.common import fakeKiCADGui
    app = fakeKiCADGui()

    try:
        return stencil.create(**kwargs)
    except Exception as e:
            sys.stderr.write(f"{e}\n")


@click.group()
def stencil():
    """
    Create solder paste stencils
    """
    pass

stencil.add_command(create)
stencil.add_command(createPrinted)
