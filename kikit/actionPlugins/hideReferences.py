from pcbnewTransition import pcbnew
import wx
import re
import os
import kikit
from kikit import modify
from kikit.defs import Layer
from kikit.common import PKG_BASE
from .common import initDialog, destroyDialog

class HideReferencesDialog(wx.Dialog):
    def __init__(self, state, parent=None, board=None, action=None, updateState=None):
        wx.Dialog.__init__(self,
            parent,
            title=f'Specify which components to hide (version {kikit.__version__})',
            style=wx.RESIZE_BORDER | wx.DEFAULT_DIALOG_STYLE)
        self.board = board
        self.actionCallback = action
        self.updateStatusCallback = updateState
        self.text = ""
        self.selectedItemOnly = False

        self.Bind(wx.EVT_CLOSE, self.OnCancel, id=self.GetId())
        self.Bind(wx.EVT_SIZE, self.OnSize)

        self.SetMinSize(wx.Size(520, 620))

        panel = self

        vbox = wx.BoxSizer(wx.VERTICAL)
        self.item_grid = wx.FlexGridSizer(0, 2, 3, 5)
        self.item_grid.AddGrowableCol(1)

        label = wx.StaticText(panel,
            label="Apply to labels pattern:\n(regular expression)",
            size=wx.Size(200, -1),
            style=wx.ALIGN_RIGHT)
        label.Wrap(200)
        self.item_grid.Add(label, 1, wx.ALIGN_CENTRE_VERTICAL)
        self.pattern = wx.TextCtrl(panel, style=wx.TE_LEFT, value=state.get("pattern", ".*"),
            size=wx.Size(350, -1))
        self.Bind(wx.EVT_TEXT, self.OnPatternChange, id=self.pattern.GetId())
        self.item_grid.Add(self.pattern, 0, wx.EXPAND)

        label = wx.StaticText(panel, label="Only Selected items:",
            size=wx.Size(200, -1),
            style=wx.ALIGN_RIGHT)
        label.Wrap(200)
        self.item_grid.Add(label, 1, wx.ALIGN_CENTRE_VERTICAL)
        self.selected_only = wx.CheckBox(panel, style=wx.CHK_2STATE)
        self.Bind(wx.EVT_CHECKBOX, self.OnselectedItemOnlyChange)
        self.selected_only.SetValue(self.selectedItemOnly)
        self.item_grid.Add(self.selected_only, 0, wx.EXPAND)

        label = wx.StaticText(panel, label="What to do:",
            size=wx.Size(200, -1),
            style=wx.ALIGN_RIGHT)
        label.Wrap(200)
        self.item_grid.Add(label, 1, wx.ALIGN_CENTRE_VERTICAL)
        self.action = wx.Choice(panel, style=wx.CB_DROPDOWN,
            choices=["Show", "Hide"])
        self.action.SetSelection(state.get("action", 1))
        self.item_grid.Add(self.action, 0, wx.EXPAND)

        label = wx.StaticText(panel, label="Apply to:",
            size=wx.Size(200, -1),
            style=wx.ALIGN_RIGHT)
        label.Wrap(200)
        self.item_grid.Add(label, 1, wx.ALIGN_CENTRE_VERTICAL)
        self.scope = wx.Choice(panel, style=wx.CB_DROPDOWN,
            choices=["References only", "Values only", "References and values"])
        self.scope.SetSelection(state.get("scope", 2))
        self.item_grid.Add(self.scope, 0, wx.EXPAND)

        label = wx.StaticText(panel, label="Layers to include:",
            size=wx.Size(200, -1),
            style=wx.ALIGN_RIGHT | wx.ALIGN_TOP)
        label.Wrap(200)
        self.item_grid.Add(label, 0, wx.ALIGN_CENTRE_VERTICAL)

        self.layers = wx.CheckListBox(panel, choices=[str(Layer(l).name) for l in Layer.all()])
        layerCheckState = state.get("layers", [True for _ in Layer.all()])
        for l, checked in zip(Layer.all(), layerCheckState):
            self.layers.Check(l, checked)
        self.item_grid.Add(self.layers, 0, wx.EXPAND)

        label = wx.StaticText(panel, label="Select layers:",
            size=wx.Size(200, -1),
            style=wx.ALIGN_RIGHT | wx.ALIGN_TOP)
        label.Wrap(200)
        self.item_grid.Add(label, 0, wx.ALIGN_CENTRE_VERTICAL)

        buttonGrid = wx.FlexGridSizer(0, 2, 3, 5)
        buttonGrid.AddGrowableCol(0)
        buttonGrid.AddGrowableCol(1)
        self.item_grid.Add(buttonGrid, 0, wx.EXPAND)

        allLayersBtn = wx.Button(panel, label='All layers')
        self.Bind(wx.EVT_BUTTON, self.OnAllLayers, id=allLayersBtn.GetId())
        buttonGrid.Add(allLayersBtn, 1, wx.EXPAND)

        noLayersBtn = wx.Button(panel, label='No layers')
        self.Bind(wx.EVT_BUTTON, self.OnNoLayers, id=noLayersBtn.GetId())
        buttonGrid.Add(noLayersBtn, 1, wx.EXPAND)

        techLayersBtn = wx.Button(panel, label='Toggle technical layers')
        self.Bind(wx.EVT_BUTTON, self.OnTechnicalLayers, id=techLayersBtn.GetId())
        buttonGrid.Add(techLayersBtn, 1, wx.EXPAND)

        silkLayersBtn = wx.Button(panel, label='Toggle silkscreen layers')
        self.Bind(wx.EVT_BUTTON, self.OnSilkscreenLayers, id=silkLayersBtn.GetId())
        buttonGrid.Add(silkLayersBtn, 1, wx.EXPAND)


        label = wx.StaticText(panel,
            label="Matching references:",
            size=wx.Size(200, -1),
            style=wx.ALIGN_RIGHT)
        label.Wrap(200)
        self.item_grid.Add(label, 1, wx.ALIGN_TOP)
        self.matchingText = wx.StaticText(panel,
            label="Matching references:",
            size=wx.Size(350, 80),
            style=wx.ALIGN_LEFT | wx.ST_ELLIPSIZE_END)
        self.item_grid.Add(self.matchingText, 1, wx.EXPAND)
        self.item_grid.AddGrowableRow(5)

        button_box = wx.BoxSizer(wx.HORIZONTAL)

        cancelButton = wx.Button(panel, label='Close')
        self.Bind(wx.EVT_BUTTON, self.OnCancel, id=cancelButton.GetId())
        button_box.Add(cancelButton, 1, wx.RIGHT, 10)

        self.applyButton = wx.Button(panel, label='Apply')
        self.Bind(wx.EVT_BUTTON, self.OnApply, id=self.applyButton.GetId())
        button_box.Add(self.applyButton, 1)

        vbox.Add(self.item_grid, 1, wx.EXPAND | wx.ALL, 10)
        vbox.Add(button_box, 0, wx.ALIGN_RIGHT | wx.LEFT | wx.RIGHT | wx.BOTTOM, 20)

        panel.SetSizer(vbox)
        vbox.Fit(self)
        self.Centre()
        self.OnPatternChange(None)

    def SetTextPreview(self, text = None):
        if text is not None:
            self.text = text
        self.matchingText.SetLabel(self.text)
        self.matchingText.Wrap(self.item_grid.GetColWidths()[1])

    def Show(self):
        self.OnPatternChange(None)
        super().Show()

    def OnSize(self, event):
        self.SetTextPreview()
        if event is not None:
            event.Skip()

    def OnCancel(self, event):
        if self.updateStatusCallback is not None:
            selectedLayers = self.GetActiveLayers()
            self.updateStatusCallback({
                "pattern": self.GetPattern(),
                "scope": self.scope.GetSelection(),
                "action": self.action.GetSelection(),
                "layers": [l in selectedLayers for l in Layer.all()]
            })
        destroyDialog(self)

    def OnApply(self, event):
        if self.actionCallback is not None:
            self.actionCallback(self)

    def OnAllLayers(self, event):
        for l in Layer.all():
            self.layers.Check(l)

    def OnNoLayers(self, event):
        for l in Layer.all():
            self.layers.Check(l, False)

    def OnTechnicalLayers(self, event):
        checked = set(self.layers.GetCheckedItems())
        enable = not all(x in checked for x in Layer.allTech())
        for l in Layer.allTech():
            self.layers.Check(l, enable)

    def OnSilkscreenLayers(self, event):
        checked = set(self.layers.GetCheckedItems())
        enable = not all(x in checked for x in Layer.allSilk())
        for l in Layer.allSilk():
            self.layers.Check(l, enable)

    def GetShowLabels(self):
        return self.action.GetSelection() == 0

    def GetPattern(self):
        return self.pattern.GetValue()

    def GetActiveLayers(self):
        return set(self.layers.GetCheckedItems())

    def GetSelectedItemOnly(self):
        return self.selectedItemOnly

    def ModifyReferences(self):
        return self.scope.GetSelection() in [0, 2]

    def ModifyValues(self):
        return self.scope.GetSelection() in [1, 2]

    def OnselectedItemOnlyChange(self, event):
        self.selectedItemOnly = not self.selectedItemOnly
        self.OnPatternChange(None)

    def OnPatternChange(self, event):
        try:
            regex = re.compile(self.pattern.GetValue())
            self.applyButton.Enable()
            if not self.board:
                self.SetTextPreview("")
            else:
                refs = []
                for footprint in self.board.GetFootprints():
                    if self.selectedItemOnly and not footprint.IsSelected():
                        continue

                    if regex.match(footprint.GetReference()):
                        refs.append(footprint.GetReference())
                if len(refs) > 0:
                    self.SetTextPreview(", ".join(refs))
                else:
                    self.SetTextPreview("None")
        except re.error as e:
            self.applyButton.Disable()
            self.SetTextPreview(f"Invalid regular expression: {e}")
        finally:
            self.SendSizeEvent()


class HideReferencesPlugin(pcbnew.ActionPlugin):
    def defaults(self):
        self.name = "KiKit: Show/hide references"
        self.category = "KiKit"
        self.description = "Show/hide references in the board based on regular expression"
        self.icon_file_name = os.path.join(PKG_BASE, "resources", "graphics", "removeRefIcon_24x24.png")
        self.show_toolbar_button = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._dialogState = {}

    def error(self, msg):
        wx.MessageBox(msg, "Error", wx.OK | wx.ICON_ERROR)

    def action(self, dialog):
        try:
            if dialog.ModifyReferences():
                modify.references(dialog.board, dialog.GetShowLabels(),
                     dialog.GetPattern(), dialog.GetActiveLayers(),
                     dialog.GetSelectedItemOnly())
            if dialog.ModifyValues():
                modify.values(dialog.board, dialog.GetShowLabels(),
                    dialog.GetPattern(), dialog.GetActiveLayers(),
                    dialog.GetSelectedItemOnly())
            pcbnew.Refresh()
        except Exception as e:
            self.error(f"Cannot perform: {e}")

    def updateState(self, newState):
        self._dialogState = newState

    def Run(self):
        # Find the pcbnew main window
        pcbnew_window = wx.FindWindowByName("PcbFrame")
        if pcbnew_window is None:
            # Something failed, abort
            self.error("Failed to find pcbnew main window")
            return
        try:
            dialog = initDialog(lambda: HideReferencesDialog(
                                    state=self._dialogState,
                                    board=pcbnew.GetBoard(),
                                    action=lambda d: self.action(d),
                                    updateState=lambda s: self.updateState(s),
                                    parent=pcbnew_window))
            dialog.Show()
        except Exception as e:
            self.error(f"Cannot perform: {e}")

plugin = HideReferencesPlugin

if __name__ == "__main__":
    import sys

    dialog = initDialog(lambda: HideReferencesDialog(
                            {},
                            board=pcbnew.LoadBoard(sys.argv[1]),
                            updateState=print))
    dialog.ShowModal()
