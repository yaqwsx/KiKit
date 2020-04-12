import pcbnew
import click
import sys
import re

@click.command()
@click.argument("board", type=click.Path(dir_okay=False, exists=True))
@click.option("--show/--hide", "-s", help="Show/hide references mathing a pattern")
@click.option("--pattern", "-p", type=str, help="Regular expression for references")
def references(board, show, pattern):
    """
    Show or hide references on the board matching a pattern.
    """
    b = pcbnew.LoadBoard(board)
    for module in b.GetModules():
        if re.match(pattern, module.GetReference()):
            module.Reference().SetVisible(show)
    b.Save(board)