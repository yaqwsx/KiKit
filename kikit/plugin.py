# This has nothing to do with KiKit plugins, instead, it is the registration
# routine for Action plugins. However, the original implementation used the name
# 'plugin'. In order not to break the existing PCM installations we import this
# and leave it here for at least a couple of months to ensure that everybody
# upgrades to a new PCM package.
from kikit.actionPlugins import importAllPlugins # type: ignore

from typing import Any, Dict, Iterable

from kikit.panelize import Panel
from kikit.substrate import Substrate
from pcbnewTransition import pcbnew
from shapely.geometry import LineString

Preset = Dict[str, Dict[str, Any]]


class HookPlugin:
    """
    This type of plugin has a number of callbacks that are invoked during the
    panelization process. The plugin can tweak the process by modifying the
    panel. Inherit from this class and override the callbacks listed below.

    The same instance of the plugin object is used for invoking all of the
    callbacks. So you can safely store information between the calls.

    If you want to know the precise order of operation, please refer to the
    function kikit.panelize_ui:doPanelization.
    """
    def __init__(self, userArg: str, board: pcbnew.BOARD,
                 preset: Dict[str, Dict[str, Any]]) -> None:
        """
        The constructor of the hook plugin will always receive a single string
        from the user, the source design and the presets Dictionary.
        """
        self.userArg = userArg
        self.board = board
        self.preset = preset

    def prePanelSetup(self, panel: Panel) -> None:
        """
        This callback is invoked just after a panel instance was created and no
        operations were performed on it.
        """
        pass

    def afterPanelSetup(self, panel: Panel) -> None:
        """
        This callback is invoked after the panel has inherited design setting,
        properties and the title block.
        """
        pass

    def afterLayout(self, panel: Panel, substrates: Iterable[Substrate]) -> None:
        """
        This callback is invoked after the boards are placed in panel and before
        the partition line is constructed. substrates is an iterable of
        individual boards substrates in the panel
        """
        pass

    def afterTabs(self, panel: Panel, tabCuts: Iterable[LineString],
                  backboneCuts: Iterable[LineString]) -> None:
        """
        This callback is invoked after the tabs have been formed.
        """
        pass

    def afterFraming(self, panel: Panel, frameCuts: Iterable[LineString]) -> None:
        """
        This callback is invoked after the frame was build and before any frame
        decorators (cuts, fiducials) were placed.
        """
        pass

    def afterCuts(self, panel: Panel) -> None:
        """
        This callback is invoked after the cuts were rendered.
        """
        pass

    def finish(self, panel: Panel) -> None:
        """
        This callback is invoked after the panel is finished, just before
        debugging information is collected and the panel is saved.
        """
        pass


class LayoutPlugin:
    """
    This type of plugin can create user specified board layouts
    """
    def __init__(self, preset: Preset, userArg: str, netPattern: str,
                 refPattern: str, vspace: int, hspace: int, rotation: int) -> None:
        self.preset = preset
        self.userArg = userArg
        self.netPattern = netPattern
        self.refPattern = refPattern
        self.vspace = vspace
        self.hspace = hspace
        self.rotation = rotation

    def buildLayout(self, panel: Panel, inputFile: str,
                    sourceArea: pcbnew.wxRect) -> Iterable[Substrate]:
        """
        This function is supposed to build the layout (append the boards to the
        panel) and return an iterable of substrates of these boards.
        """
        raise NotImplementedError("Layout plugin has to define buildLayout")

    def buildPartitionLine(self, panel: Panel, framingSubstrates: Iterable[Substrate]) -> None:
        """
        This function should build the partition line in the panel. It gets an
        iterable of extra substrates that represent soon-to-be frame of the
        panel.
        """
        return panel.buildPartitionLineFromBB(framingSubstrates)

    def buildExtraCuts(self, panel: Panel) -> Iterable[LineString]:
        """
        This function can return extra cuts, e.g., from internal backbone. It
        shouldn't deal with tab cuts.
        """
        return []


class FramingPlugin:
    """
    This type of plugin can build custom framing
    """
    def __init__(self, preset: Preset, userArg: str) -> None:
        self.preset = preset
        self.userArg = userArg

    def buildFraming(self, panel: Panel) -> Iterable[LineString]:
        """
        This function should append frame to the panel and return list of cuts.
        """
        raise NotImplementedError("FramingPlugin has to define buildFraming")

    def buildDummyFramingSubstrates(self, substrates: Iterable[Substrate]) -> Iterable[Substrate]:
        """
        This function should build dummy substrates that emulate the
        soon-to-be-frame. These substrates are used for partition line
        computation.
        """
        raise NotImplementedError("FramingPlugin has to define buildDummyFramingSubstrates")


class TabsPlugin:
    """
    This plugin can make custom tabs. It provides two functions, however, you
    should override only one of them.
    """
    def __init__(self, preset: Preset, userArg: str) -> None:
        self.preset = preset
        self.userArg = userArg

    def buildTabAnnotations(self, panel: Panel) -> None:
        """
        This function should append tabs annotations to the panel. The rendering
        will be handled automatically.
        """
        raise NotImplementedError("Tabs plugin has to provide buildTabAnnotations when it doesn't override buildTabs")

    def buildTabs(self, panel: Panel) -> Iterable[LineString]:
        """
        This function can directly build the tabs. In most cases, you don't have
        to override this and instead, override buildTabAnnotations.
        """
        panel.clearTabsAnnotations()
        self.buildTabAnnotations(panel)
        return panel.buildTabsFromAnnotations()

class CutsPlugin:
    """
    This plugin renders tabs (LineStrings) into board features. The cuts are
    divided into two types so you can, e.g., inset you tab cuts.
    """
    def __init__(self, preset: Preset, userArg: str) -> None:
        self.preset = preset
        self.userArg = userArg

    def renderTabCuts(self, panel: Panel, cuts: Iterable[LineString]) -> None:
        """
        Render tab cuts into the panel.
        """
        raise NotImplementedError("Cuts plugin has to provide renderTabCuts")

    def renderOtherCuts(self, panel: Panel, cuts: Iterable[LineString]) -> None:
        """
        Render any other type of cuts (frame, backbone, etc.)
        """
        raise NotImplementedError("Cuts plugin has to provide renderOtherCuts")


class ToolingPlugin:
    """
    This plugin places tooling holes on the board frame.
    """
    def __init__(self, preset: Preset, userArg: str) -> None:
        self.preset = preset
        self.userArg = userArg

    def buildTooling(self, panel: Panel) -> None:
        """
        Add  tooling holes
        """
        raise NotImplementedError("Tooling plugin has to provide buildTooling")

class FiducialsPlugin:
    """
    This plugin places fiducials holes on the board frame.
    """
    def __init__(self, preset: Preset, userArg: str) -> None:
        self.preset = preset
        self.userArg = userArg

    def buildFiducials(self, panel: Panel) -> None:
        """
        Add  fiducials
        """
        raise NotImplementedError("Fiducials plugin has to provide buildFiducials")

class TextVariablePlugin:
    """
    This plugin provides text variables the user can use in text fields.
    """
    def __init__(self, board: pcbnew.BOARD) -> None:
        self.board = board

    def variables(self) -> Dict[str, Any]:
        """
        This function should return a dictionary from variable names to their
        values. The values don't have to be strings – it can be anything
        convertible to string. Especially, if calculating of the value is
        expensive, you can use kikit.text.Formatter to postpone the value
        computation to the moment when it is used from user text.
        """
        return {}
