import click
import os
import csv
import io
import traceback
from kikit.units import readLength, readAngle

def splitStr(delimiter, escapeChar, s):
    """
    Splits s based on delimiter that can be escaped via escapeChar
    """
    # Let's use csv reader to implement this
    reader = csv.reader(io.StringIO(s), delimiter=delimiter, escapechar=escapeChar)
    # Unpack first line
    for x in reader:
        return x


class Section(click.ParamType):
    """
    A CLI argument type for overriding section parameters. Basically a semicolon
    separated list of `key: value` pairs. The first word might omit the key; in
    that case "type" key is used.
    """
    name = "parameter_list"

    def convert(self, value, param, ctx):
        if len(value.strip()) == 0:
            self.fail(f"{value} is not a valid argument specification",
                param, ct)
        try:
            values = {}
            for i, pair in enumerate(splitStr(";", "\\", value)):
                if len(pair.strip()) == 0:
                    continue
                s = pair.split(":")
                if i == 0 and len(s) == 1:
                    values["type"] = s[0].strip()
                    continue
                key, value = s[0].strip(), s[1].strip()
                values[key] = value
            return values
        except (TypeError, IndexError):
            self.fail(f"'{pair}' is not a valid key: value pair",
                param,
                ctx)

class PresetError(RuntimeError):
    pass

@click.command()
@click.argument("input", type=click.Path(dir_okay=False))
@click.argument("output", type=click.Path(dir_okay=False))
@click.option("--preset", "-p", multiple=True,
    help="A panelization preset file; use prefix ':' for built-in styles.")
@click.option("--layout", "-l", type=Section(),
    help="Override layout settings.")
@click.option("--source", "-s", type=Section(),
    help="Override source settings.")
@click.option("--tabs", "-t", type=Section(),
    help="Override tab settings.")
@click.option("--cuts", "-c", type=Section(),
    help="Override cut settings.")
@click.option("--framing", "-r", type=Section(),
    help="Override framing settings.")
@click.option("--tooling", "-o", type=Section(),
    help="Override tooling settings.")
@click.option("--fiducials", "-f", type=Section(),
    help="Override fiducials settings.")
@click.option("--text", "-t", type=Section(),
    help="Override text settings.")
@click.option("--post", "-z", type=Section(),
    help="Override post processing settings settings.")
@click.option("--debug", type=Section(),
    help="Include debug traces or drawings in the panel.")
@click.option("--dump", "-d", type=click.Path(file_okay=True, dir_okay=False),
    help="Dump constructured preset into a JSON file.")
def panelize(input, output, preset, layout, source, tabs, cuts, framing,
                tooling, fiducials, text, post, debug, dump):
    """
    Panelize boards
    """
    try:
        # Hide the import in the function to make KiKit start faster
        from kikit import panelize_ui_impl as ki
        from kikit.panelize import Panel
        from pcbnew import LoadBoard, wxPointMM
        import json
        import commentjson
        import sys
        from itertools import chain


        preset = ki.obtainPreset(preset,
            layout=layout, source=source, tabs=tabs, cuts=cuts, framing=framing,
            tooling=tooling, fiducials=fiducials, text=text, post=post, debug=debug)

        board = LoadBoard(input)

        panel = Panel()
        panel.inheritDesignSettings(input)
        panel.inheritProperties(input)

        sourceArea = ki.readSourceArea(preset["source"], board)
        substrates = ki.buildLayout(preset["layout"], panel, input, sourceArea)
        framingSubstrates = ki.dummyFramingSubstrate(substrates,
            ki.frameOffset(preset["framing"]))
        panel.buildPartitionLineFromBB(framingSubstrates)

        tabCuts = ki.buildTabs(preset["tabs"], panel, substrates,
            framingSubstrates)
        backboneCuts = ki.buildBackBone(preset["layout"], panel, substrates,
            ki.frameOffset(preset["framing"]))
        frameCuts = ki.buildFraming(preset["framing"], panel)

        ki.buildTooling(preset["tooling"], panel)
        ki.buildFiducials(preset["fiducials"], panel)
        ki.buildText(preset["text"], panel)
        ki.buildPostprocessing(preset["post"], panel)

        ki.makeTabCuts(preset["cuts"], panel, tabCuts)
        ki.makeOtherCuts(preset["cuts"], panel, chain(backboneCuts, frameCuts))

        ki.runUserScript(preset["post"], panel)

        ki.buildDebugAnnotation(preset["debug"], panel)

        panel.save(output)

        if (dump):
            with open(dump, "w") as f:
                f.write(ki.dumpPreset(preset))
    except Exception as e:
        import sys
        sys.stderr.write("An error occurred: " + str(e) + "\n")
        sys.stderr.write("No output files produced\n")
        if isinstance(preset, dict) and preset["debug"]["trace"]:
            traceback.print_exc(file=sys.stderr)
        sys.exit(1)

@click.command()
@click.argument("input", type=click.Path(dir_okay=False))
@click.argument("output", type=click.Path(dir_okay=False))
@click.option("--source", "-s", type=Section(),
    help="Specify source settings.")
@click.option("--debug", type=Section(),
    help="Include debug traces or drawings in the panel.")
def separate(input, output, source, debug):
    """
    Separate a single board out of a multi-board design. The separated board is
    placed in the middle of the sheet.

    You can specify the board via bounding box or annotation. See documentation
    for further details on usage.
    """
    try:
        from kikit import panelize_ui_impl as ki
        from kikit.panelize import Panel
        from pcbnew import LoadBoard, wxPointMM

        preset = ki.obtainPreset([], validate=False, source=source, debug=debug)

        board = LoadBoard(input)
        sourceArea = ki.readSourceArea(preset["source"], board)

        panel = Panel()
        panel.inheritDesignSettings(input)
        panel.inheritProperties(input)
        destination = wxPointMM(150, 100)
        panel.appendBoard(input, destination, sourceArea)
        panel.save(output)
    except Exception as e:
        sys.stderr.write("An error occurred: " + str(e) + "\n")
        sys.stderr.write("No output files produced\n")
        if isinstance(preset, dict) and preset["debug"]["trace"]:
            traceback.print_exc(file=sys.stderr)
        sys.exit(1)