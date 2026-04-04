import click
from kikit import (panelize_ui, export_ui, present_ui, stencil_ui,
    modify_ui, fab_ui, drc_ui)
from kikit import __version__
import os
import sys

try:
    import pcbnew
except ImportError:
    if os.name == "nt":
        message = "No Pcbnew Python module found.\n" + \
                  "Please make sure that you use KiCAD command prompt, " + \
                  "not the standard Command Prompt or Power Shell\n" + \
                  "See https://github.com/yaqwsx/KiKit/blob/master/doc/installation.md#installation-on-windows"
    else:
        message = "No Pcbnew Python module found for the current Python interpreter.\n" + \
                  "First, make sure that KiCAD is actually installed\n." + \
                  "Then, make sure that you use the same Python interpreter as KiCAD uses.\n" + \
                  "Usually a good way is to invoke 'python3 -m pip install kikit'."
    delimiter = 100 * "=" + "\n" + 100 * "=" + "\n"
    sys.stderr.write(
        delimiter + f"** Cannot run KiKit**\n{message}\n" + delimiter)
    raise RuntimeError("Cannot run KiKit, see error message above") from None
except AttributeError:
    raise RuntimeError("KiCAD v5 is no longer supported for KiKit. Version v1.0.x is the last one that supports KiCAD 5.")

@click.group(context_settings={"help_option_names": ["-h", "--help"]})
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
    # When KiCAD crashes, we want the user to know
    import faulthandler
    import sys
    faulthandler.enable(sys.stderr)

    cli()
