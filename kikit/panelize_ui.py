import click
import os
import csv
import io
import glob
import traceback
from kikit.panelize_ui_sections import *

PKG_BASE = os.path.dirname(__file__)
PRESETS = os.path.join(PKG_BASE, "resources/panelizePresets")
IS_CLICK_V8 = click.__version__.startswith("8.")

# We would like to support both, click v7 and v8 in order to maximize
# compatibility. However, since click v8.1 there is breaking change in the way
# shell completion works. This functions hides the differences and should allow
# us to use both. Pass to it as **addCompatibleCompletion(completionFunction)
def addCompatibleShellCompletion(completionFn):
    if IS_CLICK_V8:
        import click.shell_completion
        def completion(*args, **kwargs):
            return [click.shell_completion.CompletionItem(x) for x in completionFn(*args, **kwargs)]
        return {"shell_complete": completionFn}
    else:
        return {"autocompletion": completionFn}

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
                param, ctx)
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

def completePath(prefix, fileSuffix=""):
    """
    This is rather hacky and  far from ideal, however, until Click 8 we probably
    cannot do much better.
    """
    paths = []
    for p in glob.glob(prefix + "*"):
        if os.path.isdir(p):
            paths.append(p + "/")
        elif p.endswith(fileSuffix):
            paths.append(p)
    return paths

def pathCompletion(fileSuffix=""):
    def f(ctx, args, incomplete):
        return completePath(incomplete, fileSuffix)
    return f

def completePreset(ctx, args, incomplete):
    presets = [":" + x.replace(".json", "")
        for x in os.listdir(PRESETS)
        if x.endswith(".json") and (x.startswith(incomplete) or x.startswith(incomplete[1:]))]
    if incomplete.startswith(":"):
        return presets
    return presets + completePath(incomplete, ".json")

def lastSectionPair(incomplete):
    """
    Given an incomplete command text of a section, return the last (possibly
    incomplete) key-value pair
    """
    lastSection = incomplete.split(";")[-1]
    x = [x.strip() for x in lastSection.split(":", 1)]
    if len(x) == 1:
        return x[0], ""
    return x

def hasNoSectionPair(incomplete):
    return ";" not in incomplete

def completeSection(section):
    def fun(ctx, args, incomplete):
        if incomplete.startswith("'"):
            incomplete = incomplete[1:]
        key, val = lastSectionPair(incomplete)

        candidates = []
        if hasNoSectionPair(incomplete):
            candidates.extend([x for x in section["type"].vals if x.startswith(incomplete)])
        if len(val) == 0:
            trimmedIncomplete = incomplete.rsplit(";", 1)[0]
            candidates.extend([trimmedIncomplete + x + ":"
                for x in section.keys() if x.startswith(key)])
        return candidates
    return fun

@click.command()
@click.argument("input", type=click.Path(dir_okay=False),
    **addCompatibleShellCompletion(pathCompletion(".kicad_pcb")))
@click.argument("output", type=click.Path(dir_okay=False),
    **addCompatibleShellCompletion(pathCompletion(".kicad_pcb")))
@click.option("--preset", "-p", multiple=True,
    help="A panelization preset file; use prefix ':' for built-in styles.",
    **addCompatibleShellCompletion(completePreset))
@click.option("--layout", "-l", type=Section(),
    help="Override layout settings.",
    **addCompatibleShellCompletion(completeSection(LAYOUT_SECTION)))
@click.option("--source", "-s", type=Section(),
    help="Override source settings.",
    **addCompatibleShellCompletion(completeSection(SOURCE_SECTION)))
@click.option("--tabs", "-t", type=Section(),
    help="Override tab settings.",
    **addCompatibleShellCompletion(completeSection(TABS_SECTION)))
@click.option("--cuts", "-c", type=Section(),
    help="Override cut settings.",
    **addCompatibleShellCompletion(completeSection(CUTS_SECTION)))
@click.option("--framing", "-r", type=Section(),
    help="Override framing settings.",
    **addCompatibleShellCompletion(completeSection(FRAMING_SECTION)))
@click.option("--tooling", "-o", type=Section(),
    help="Override tooling settings.",
    **addCompatibleShellCompletion(completeSection(TOOLING_SECTION)))
@click.option("--fiducials", "-f", type=Section(),
    help="Override fiducials settings.",
    **addCompatibleShellCompletion(completeSection(FIDUCIALS_SECTION)))
@click.option("--text", "-t", type=Section(),
    help="Override text settings.",
    **addCompatibleShellCompletion(completeSection(TEXT_SECTION)))
@click.option("--page", "-P", type=Section(),
    help="Override page settings.",
    **addCompatibleShellCompletion(completeSection(POST_SECTION)))
@click.option("--post", "-z", type=Section(),
    help="Override post processing settings.",
    **addCompatibleShellCompletion(completeSection(POST_SECTION)))
@click.option("--debug", type=Section(),
    help="Include debug traces or drawings in the panel.",
    **addCompatibleShellCompletion(completeSection(DEBUG_SECTION)))
@click.option("--dump", "-d", type=click.Path(file_okay=True, dir_okay=False),
    help="Dump constructured preset into a JSON file.")
def panelize(input, output, preset, layout, source, tabs, cuts, framing,
                tooling, fiducials, text, page, post, debug, dump):
    """
    Panelize boards
    """
    try:
        # Hide the import in the function to make KiKit start faster
        from kikit import panelize_ui_impl as ki
        import sys
        from kikit.common import fakeKiCADGui
        app = fakeKiCADGui()

        preset = ki.obtainPreset(preset,
            layout=layout, source=source, tabs=tabs, cuts=cuts, framing=framing,
            tooling=tooling, fiducials=fiducials, text=text, page=page, post=post,
            debug=debug)

        doPanelization(input, output, preset)

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

def doPanelization(input, output, preset):
    """
    The panelization logic is separated into a separate function so we can
    handle errors based on the context; e.g., CLI vs GUI
    """
    from kikit import panelize_ui_impl as ki
    from kikit.panelize import Panel
    from pcbnewTransition.transition import isV6, pcbnew
    from pcbnew import LoadBoard
    from itertools import chain

    if preset["debug"]["deterministic"] and isV6():
        pcbnew.KIID.SeedGenerator(42)

    board = LoadBoard(input)

    panel = Panel(output)

    # Register extra footprints for annotations
    for tabFootprint in preset["tabs"]["tabfootprints"]:
        panel.annotationReader.registerTab(tabFootprint.lib, tabFootprint.footprint)

    panel.inheritDesignSettings(board)
    panel.inheritProperties(board)
    panel.inheritTitleBlock(board)

    sourceArea = ki.readSourceArea(preset["source"], board)
    substrates = ki.buildLayout(preset["layout"], panel, input, sourceArea)
    framingSubstrates = ki.dummyFramingSubstrate(substrates,
        ki.frameOffset(preset["framing"]))
    panel.buildPartitionLineFromBB(framingSubstrates)

    tabCuts = ki.buildTabs(preset["tabs"], panel, substrates,
        framingSubstrates, ki.frameOffset(preset["framing"]))
    backboneCuts = ki.buildBackBone(preset["layout"], panel, substrates,
        ki.frameOffset(preset["framing"]))
    frameCuts = ki.buildFraming(preset["framing"], panel)

    ki.buildTooling(preset["tooling"], panel)
    ki.buildFiducials(preset["fiducials"], panel)
    ki.buildText(preset["text"], panel)
    ki.buildPostprocessing(preset["post"], panel)

    ki.makeTabCuts(preset["cuts"], panel, tabCuts)
    ki.makeOtherCuts(preset["cuts"], panel, chain(backboneCuts, frameCuts))

    ki.setStackup(preset["source"], panel)
    ki.positionPanel(preset["page"], panel)
    ki.setPageSize(preset["page"], panel, board)

    ki.runUserScript(preset["post"], panel)

    ki.buildDebugAnnotation(preset["debug"], panel)

    panel.save()


@click.command()
@click.argument("input", type=click.Path(dir_okay=False))
@click.argument("output", type=click.Path(dir_okay=False))
@click.option("--source", "-s", type=Section(),
    help="Specify source settings.")
@click.option("--page", "-P", type=Section(),
    help="Override page settings.",
    **addCompatibleShellCompletion(completeSection(POST_SECTION)))
@click.option("--debug", type=Section(),
    help="Include debug traces or drawings in the panel.")
@click.option("--keepAnnotations/--stripAnnotations", default=True,
    help="Do not strip annotations" )
def separate(input, output, source, page, debug, keepannotations):
    """
    Separate a single board out of a multi-board design. The separated board is
    placed in the middle of the sheet.

    You can specify the board via bounding box or annotation. See documentation
    for further details on usage.
    """
    try:
        from kikit import panelize_ui_impl as ki
        from kikit.panelize import Panel
        from pcbnewTransition.transition import isV6, pcbnew
        from pcbnew import LoadBoard, wxPointMM
        from kikit.common import fakeKiCADGui
        app = fakeKiCADGui()

        preset = ki.obtainPreset([], validate=False, source=source, page=page, debug=debug)

        if preset["debug"]["deterministic"] and isV6():
            pcbnew.KIID.SeedGenerator(42)

        board = LoadBoard(input)
        sourceArea = ki.readSourceArea(preset["source"], board)

        panel = Panel(output)
        panel.inheritDesignSettings(board)
        panel.inheritProperties(board)
        panel.inheritTitleBlock(board)

        destination = wxPointMM(150, 100)
        panel.appendBoard(input, destination, sourceArea,
            interpretAnnotations=(not keepannotations))
        ki.setStackup(preset["source"], panel)
        ki.positionPanel(preset["page"], panel)
        ki.setPageSize(preset["page"], panel, board)

        panel.save()
    except Exception as e:
        import sys
        sys.stderr.write("An error occurred: " + str(e) + "\n")
        sys.stderr.write("No output files produced\n")
        if isinstance(preset, dict) and preset["debug"]["trace"]:
            traceback.print_exc(file=sys.stderr)
        sys.exit(1)
