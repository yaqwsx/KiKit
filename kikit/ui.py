import click
import kikit.export as kiexport
from kikit.panelize import Panel, fromMm, wxPointMM, wxRectMM

@click.group()
def panelize():
    """
    Create a simple predefined panel patterns
    """
    pass

@click.command()
@click.argument("input", type=click.Path(dir_okay=False))
@click.argument("output", type=click.Path(dir_okay=False))
@click.option("--sourcearea", "-s", type=(int, int, int, int), help="x y w h in millimeters")
def extractBoard(input, output, sourcearea):
    """
    Extract a single board out of a file

    The extracted board is placed in the middle of the sheet
    """
    panel = Panel()
    destination = wxPointMM(150, 100)
    area = wxRectMM(*sourcearea)
    panel.appendBoard(input, destination, area, tolerance=fromMm(5), shrink=True)
    panel.save(output)

@click.command()
@click.argument("input", type=click.Path(dir_okay=False))
@click.argument("output", type=click.Path(dir_okay=False))
@click.option("--space", "-s", type=float, help="Space between boards")
@click.option("--gridsize", "-g", type=(int, int), help="Panel size <rows> <cols>")
@click.option("--panelsize", "-p", type=(float, float), help="<width> <height>")
@click.option("--tabwidth", type=float, default=0,
    help="Size of the bottom/up tabs, leave unset for full width")
@click.option("--tabheight", type=float, default=0,
    help="Size of the left/right tabs, leave unset for full height")
@click.option("--vcuts", type=bool, help="Use V-cuts to separe the boards", default=False)
@click.option("--mousebites", type=(float, float), default=(None, None),
    help="Use mouse bites to separate the boards. Specify drill size and spacing")
@click.option("--radius", type=float, default=0, help="Add a radius to inner corners (warning: slow)")
@click.option("--sourcearea", type=(float, float, float, float),
    help="x y w h in millimeters. If not specified, automatically detected", default=(None, None, None, None))
def grid(input, output, space, gridsize, panelsize, tabwidth, tabheight, vcuts,
         mousebites, radius, sourcearea):
    """
    Create a regular panel placed in a frame
    """
    panel = Panel()
    rows, cols = gridsize
    if sourcearea[0]:
        sourcearea = wxRectMM(*sourcearea)
    else:
        sourcearea = None
    psize, cuts = panel.makeGrid(input, rows, cols, wxPointMM(50, 50),
        sourceArea=sourcearea, tolerance=fromMm(5), radius=fromMm(radius),
        verSpace=fromMm(space), horSpace=fromMm(space),
        verTabWidth=fromMm(tabwidth), horTabWidth=fromMm(tabheight),
        outerHorTabThickness=fromMm(space), outerVerTabThickness=fromMm(space))
    if vcuts:
        panel.makeVCuts(cuts)
    if mousebites[0]:
        drill, spacing = mousebites
        panel.makeMouseBites(cuts, fromMm(drill), fromMm(spacing))
    w, h = panelsize
    panel.makeFrame(psize, fromMm(w), fromMm(h), fromMm(space), radius=fromMm(radius))
    panel.save(output)


panelize.add_command(extractBoard)
panelize.add_command(grid)

@click.group()
def export():
    """
    Export KiCAD boards
    """
    pass

export.add_command(kiexport.gerber)
export.add_command(kiexport.dxf)

@click.group()
def cli():
    pass
cli.add_command(export)
cli.add_command(panelize)



if __name__ == '__main__':
    cli()