import click

@click.group()
def export():
    """
    Export KiCAD boards
    """
    pass

@click.command()
@click.argument("boardfile", type=click.Path(dir_okay=False))
@click.argument("outputdir", type=click.Path(file_okay=False), default=None)
def gerber(boardfile, outputdir):
    from kikit.export import gerberImpl
    from kikit.common import fakeKiCADGui
    app = fakeKiCADGui()

    gerberImpl(boardfile, outputdir)

@click.command()
@click.argument("boardfile", type=click.Path(dir_okay=False))
@click.argument("outputdir", type=click.Path(file_okay=False), default=None)
def dxf(boardfile, outputdir):
    """
    Export board edges and pads to DXF.

    If no output dir is specified, use working directory.

    This command is designed for building 3D printed stencils
    """
    from kikit.export import dxfImpl
    from kikit.common import fakeKiCADGui
    app = fakeKiCADGui()

    dxfImpl(boardfile, outputdir)

export.add_command(gerber)
export.add_command(dxf)
