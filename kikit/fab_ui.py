import click

@click.command()
@click.argument("board", type=click.Path(dir_okay=False))
@click.argument("outputdir", type=click.Path(file_okay=False))
@click.option("--assembly/--no-assembly", help="Generate files for SMT assembly (schematics is required)")
@click.option("--schematic", type=click.Path(dir_okay=False), help="Board schematics (required for assembly files)")
@click.option("--forceSMD", is_flag=True, help="Force include all components having only SMD pads")
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


@click.group()
def fab():
    """
    Export complete manufacturing data for given fabrication houses
    """
    pass

fab.add_command(jlcpcb)