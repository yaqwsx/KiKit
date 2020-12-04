import click

@click.group()
def drc():
    """
    Validate design rules of the board
    """
    pass

@click.command()
@click.argument("boardfile", type=click.Path(dir_okay=False))
@click.option("--useMm/--useInch", default=True)
@click.option("--strict/--weak", default=False,
    help="Check all track errors")
def run(boardfile, usemm, strict):
    """
    Check DRC rules. If no rules are validated, the process exists with code 0.

    If any errors are detected, the process exists with non-zero return code and
    prints DRC report on the standard output.
    """
    from kikit.drc import runImpl
    runImpl(boardfile, usemm, strict)

drc.add_command(run)
