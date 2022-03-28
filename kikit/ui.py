import click
from kikit import (panelize_ui, export_ui, present_ui, stencil_ui,
    modify_ui, fab_ui, drc_ui)
from kikit import __version__
import sys

@click.group()
@click.version_option(__version__)
def cli():
    pass

cli.add_command(export_ui.export)
cli.add_command(panelize_ui.panelize)
cli.add_command(panelize_ui.separate)
cli.add_command(present_ui.present)
cli.add_command(modify_ui.modify)
cli.add_command(stencil_ui.stencil)
cli.add_command(fab_ui.fab)
cli.add_command(drc_ui.drc)


if __name__ == '__main__':
    cli()
