import click

@click.command()
@click.argument("board", type=click.Path(dir_okay=False, exists=True))
@click.option("--show/--hide", "-s", help="Show/hide references mathing a pattern")
@click.option("--pattern", "-p", type=str, help="Regular expression for references")
def references(**kwargs):
    """
    Show or hide references on the board matching a pattern.
    """
    from kikit import modify
    return modify.references(**kwargs)

@click.group()
def modify():
    """
    Modify board items
    """
    pass

modify.add_command(references)