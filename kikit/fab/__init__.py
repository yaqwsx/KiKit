import click
from kikit.fab.jlcpcb import jlcpcb


@click.group()
def fab():
    """
    Export complete manufacturing data for given fabrication houses
    """
    pass

fab.add_command(jlcpcb)