from typing import Iterable
from kikit.panelize import Panel
from kikit.plugin import HookPlugin, LayoutPlugin
from kikit.substrate import Substrate
from pcbnewTransition import pcbnew

class MyPlugin(HookPlugin):
    def prePanelSetup(self, panel: Panel) -> None:
        print(f"Pre panel: {self.userArg}")

    def afterPanelSetup(self, panel: Panel) -> None:
        print(f"after panel: {self.userArg}")

    def afterLayout(self, panel: Panel, substrates: Iterable[Substrate]) -> None:
        print(f"after Layout: {self.userArg}")

    def afterTabs(self, panel: Panel, tabCuts, backboneCuts) -> None:
        print(f"After tabs: {self.userArg}")

    def afterFraming(self, panel: Panel, frameCuts) -> None:
        print(f"After tabs: {self.userArg}")

    def afterCuts(self, panel: Panel) -> None:
        print(f"After cuts: {self.userArg}")

    def finish(self, panel: Panel) -> None:
        print(f"After finish: {self.userArg}")


class MyLayout(LayoutPlugin):
    def buildLayout(self, panel, inputFile, sourceArea):
        panel.appendBoard(inputFile, pcbnew.wxPointMM(0, 0), sourceArea)
        panel.appendBoard(inputFile, pcbnew.wxPointMM(100, 100), sourceArea)
        return panel.substrates
