import click
import sys


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
