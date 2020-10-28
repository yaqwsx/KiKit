import click

@click.command()
@click.argument("outdir", type=click.Path(file_okay=False))
@click.option("--description", "-d", type=click.Path(dir_okay=False),
    required=True, help="markdown file with page text")
@click.option("--board", "-b", type=(str, str, click.Path(dir_okay=False)),
    multiple=True, help="<name> <comment> <kicad_pcb file> to include in generated page.")
@click.option("--resource", "-r", type=click.Path(dir_okay=True), multiple=True,
    help="Additional resource files to (e.g., images referenced in description) to include.")
@click.option("--template", type=click.Path(), default="default",
    help="Path to a template directory or a name of built-in one. See doc/present.md for template specification.")
@click.option("--repository", type=str, help="URL of the repository")
@click.option("--name", type=str, help="Name of the board (used e.g., for title)", required=True)
def boardpage(**kwargs):
    """
    Build a board presentation page based on markdown description and include
    download links for board sources and gerbers.
    """
    from kikit import present
    return present.boardpage(**kwargs)

@click.group()
def present():
    """
    Prepare board presentation
    """
    pass

present.add_command(boardpage)