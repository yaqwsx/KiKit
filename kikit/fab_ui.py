import click

def fabCommand(f):
    """
    A decorator to add the same functionality to all fab commands
    """
    # Note that the decorators has to be specified in a reverse order
    f = click.argument("outputdir", type=click.Path(file_okay=False))(f)
    f = click.argument("board", type=click.Path(dir_okay=False))(f)

    f = click.option('--drc/--no-drc', is_flag=True, default=True,
        help="Run DRC check before building the output.")(f)
    f = click.option("--nametemplate", default="{}",
        help="Template for naming the output files.")(f)
    return f

@click.command()
@fabCommand
@click.option("--assembly/--no-assembly", help="Generate files for SMT assembly (schematics is required)")
@click.option("--schematic", type=click.Path(dir_okay=False), help="Board schematics (required for assembly files)")
@click.option("--ignore", type=str, default="", help="Comma separated list of designators to exclude from SMT assembly")
@click.option("--field", type=str, default="LCSC",
    help="Comma separated list of component fields field with LCSC order code. First existing field is used")
@click.option("--corrections", type=str, default="JLCPCB_CORRECTION",
    help="Comma separated list of component fields with the correction value. First existing field is used")
@click.option("--missingError/--missingWarn", help="If a non-ignored component misses LCSC field, fail")
def jlcpcb(**kwargs):
    """
    Prepare fabrication files for JLCPCB including their assembly service
    """
    from kikit.fab import jlcpcb
    return jlcpcb.exportJlcpcb(**kwargs)


@click.command()
@fabCommand
@click.option("--assembly/--no-assembly", help="Generate files for SMT assembly (schematics is required)")
@click.option("--schematic", type=click.Path(dir_okay=False), help="Board schematics (required for assembly files)")
@click.option("--ignore", type=str, default="", help="Comma separated list of designators to exclude from SMT assembly")
@click.option("--corrections", type=str, default="PCBWAY_CORRECTION",
    help="Comma separated list of component fields with the correction value. First existing field is used")
@click.option("--manufacturer", type=str, default="Manufacturer",
    help="Comma separated list of fields to extract manufacturer name from. First existing field is used.")
@click.option("--partNumber", type=str, default="PartNumber",
    help="Comma separated list of fields to extract part number from. First existing field is used.")
@click.option("--description", type=str, default="Description",
    help="Comma separated list of fields to extract description from. First existing field is used.")
@click.option("--notes", type=str, default="Notes",
    help="Comma separated list of fields to extract notes from. First existing field is used.")
@click.option("--solderType", type=str, default="Type",
    help="Comma separated list of fields to extract solder type from. First existing field is used.")
@click.option("--footprint", type=str, default="FootprintPCBWay",
    help="Comma separated list of fields to extract the footprint name for the BOM. First existing field is used, otherwise the footprint library name.")
@click.option("--nBoards", type=int, default=1,
    help="Number of boards per panel (default 1).")
@click.option("--missingError/--missingWarn", help="If a non-ignored component misses Manufacturer / PartNumber field, fail")
def pcbway(**kwargs):
    """
    Prepare fabrication files for PCBWAY including their assembly service
    """
    from kikit.fab import pcbway
    return pcbway.exportPcbway(**kwargs)


@click.command()
@fabCommand
def oshpark(**kwargs):
    """
    Prepare fabrication files for OSH Park
    """
    from kikit.fab import oshpark
    return oshpark.exportOSHPark(**kwargs)


@click.group()
def fab():
    """
    Export complete manufacturing data for given fabrication houses
    """
    pass

fab.add_command(jlcpcb)
fab.add_command(pcbway)
fab.add_command(oshpark)
