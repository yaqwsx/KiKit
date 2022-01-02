from sys import stderr
from numpy.core.fromnumeric import std
from numpy.lib.utils import source
from pcbnewTransition import pcbnew, isV6
from kikit.panelize_ui_impl import loadPresetChain, obtainPreset
from kikit import panelize_ui
from kikit.panelize import appendItem
from kikit.common import PKG_BASE
import kikit.panelize_ui_sections
import wx
import json
import tempfile
import shutil
import os
from threading import Thread
from itertools import chain


class ExceptionThread(Thread):
    def run(self):
        self.exception = None
        try:
            super().run()
        except Exception as e:
            self.exception = e

def pcbnewPythonPath():
    return os.path.dirname(pcbnew.__file__)

def presetDifferential(source, target):
    result = {}
    for sectionName, section in target.items():
        if sectionName not in source:
            result[sectionName] = section
            continue
        updateKeys = {}
        sourceSection = source[sectionName]
        for key, value in section.items():
            if key not in sourceSection or str(sourceSection[key]).lower() != str(value).lower():
                updateKeys[key] = value
        if len(updateKeys) > 0:
            result[sectionName] = updateKeys
    return result


def transplateBoard(source, target):
    items = chain(
        list(target.GetDrawings()),
        list(target.GetFootprints()),
        list(target.GetTracks()),
        list(target.Zones()))
    for x in items:
        target.Remove(x)

    targetNetinfo = target.GetNetInfo()
    targetNetinfo.RemoveUnusedNets()

    for x in source.GetDrawings():
        appendItem(target, x)
    for x in source.GetFootprints():
        appendItem(target, x)
    for x in source.GetTracks():
        appendItem(target, x)
    for x in source.Zones():
        appendItem(target, x)
    for n in [n for _, n in source.GetNetInfo().NetsByNetcode().items()]:
        targetNetinfo.AppendNet(n)

    if isV6():
        d = target.GetDesignSettings()
        d.CloneFrom(source.GetDesignSettings())
    else:
        target.SetDesignSettings(source.GetDesignSettings())
    target.SetProperties(source.GetProperties())
    target.SetPageSettings(source.GetPageSettings())
    target.SetTitleBlock(source.GetTitleBlock())
    target.SetZoneSettings(source.GetZoneSettings())


class SFile():
    def __init__(self, nameFilter):
        self.nameFilter = nameFilter
        self.description = ""
        self.isGuiRelevant = lambda section: True

    def validate(self, x):
        return x


class ParameterWidgetBase:
    def __init__(self, parent, name, parameter):
        self.name = name
        self.parameter = parameter
        self.label = wx.StaticText(parent,
                                   label=name,
                                   size=wx.Size(150, -1),
                                   style=wx.ALIGN_RIGHT)
        self.label.SetToolTip(parameter.description)

    def showIfRelevant(self, preset):
        relevant = self.parameter.isGuiRelevant(preset)
        self.label.Show(relevant)
        self.widget.Show(relevant)


class TextWidget(ParameterWidgetBase):
    def __init__(self, parent, name, parameter, onChange):
        super().__init__(parent, name, parameter)
        self.widget = wx.TextCtrl(
            parent, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize, 0)
        self.widget.Bind(wx.EVT_TEXT, onChange)

    def setValue(self, value):
        self.widget.ChangeValue(str(value))

    def getValue(self):
        return self.widget.GetValue()


class ChoiceWidget(ParameterWidgetBase):
    def __init__(self, parent, name, parameter, onChange):
        super().__init__(parent, name, parameter)
        self.widget = wx.Choice(parent, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize,
                                parameter.vals, 0)
        self.widget.SetSelection(0)
        self.widget.Bind(wx.EVT_CHOICE, onChange)

    def setValue(self, value):
        for i, option in enumerate(self.parameter.vals):
            if option.lower() == str(value).lower():
                self.widget.SetSelection(i)
                break

    def getValue(self):
        return self.parameter.vals[self.widget.GetSelection()]


class InputFileWidget(ParameterWidgetBase):
    def __init__(self, parent, name, parameter, onChange):
        super().__init__(parent, name, parameter)
        self.widget = wx.FilePickerCtrl(
            parent, wx.ID_ANY, wx.EmptyString, name,
            parameter.nameFilter, wx.DefaultPosition, wx.DefaultSize, wx.FLP_DEFAULT_STYLE)
        self.widget.Bind(wx.EVT_FILEPICKER_CHANGED, onChange)

    def getValue(self):
        return self.widget.GetPath()


def obtainParameterWidget(parameter):
    if isinstance(parameter, kikit.panelize_ui_sections.SChoiceBase):
        return ChoiceWidget
    if isinstance(parameter, SFile):
        return InputFileWidget
    return TextWidget


class SectionGui():
    def __init__(self, parent, name, section, onResize, onChange):
        self.name = name
        self.container = wx.CollapsiblePane(
            parent, wx.ID_ANY, name, wx.DefaultPosition, wx.DefaultSize,
            wx.CP_DEFAULT_STYLE)
        self.container.Collapse(False)

        self.container.Bind(wx.EVT_COLLAPSIBLEPANE_CHANGED, onResize)
        self.container.SetSizeHints(wx.DefaultSize, wx.DefaultSize)
        self.container.GetPane().SetSizeHints(wx.DefaultSize, wx.DefaultSize)

        self.itemGrid = wx.FlexGridSizer(0, 2, 2, 2)
        self.itemGrid.AddGrowableCol(1)
        self.itemGrid.SetFlexibleDirection(wx.BOTH)
        self.itemGrid.SetNonFlexibleGrowMode(wx.FLEX_GROWMODE_SPECIFIED)

        self.items = {
            name: obtainParameterWidget(param)(
                self.container.GetPane(), name, param, onChange)
            for name, param in section.items()
        }
        for widget in self.items.values():
            self.itemGrid.Add(widget.label, 0,  wx.ALL |
                              wx.ALIGN_CENTER_VERTICAL | wx.EXPAND | wx.RIGHT, 5)
            self.itemGrid.Add(widget.widget, 0,  wx.ALL |
                              wx.ALIGN_CENTER_VERTICAL | wx.EXPAND | wx.RIGHT, 5)

        self.container.GetPane().SetSizer(self.itemGrid)
        self.onResize()

    def onResize(self):
        self.itemGrid.Layout()
        self.container.GetPane().Fit()
        self.container.Fit()

    def populateInitialValue(self, values):
        for name, widget in self.items.items():
            if name not in values:
                continue
            widget.setValue(values[name])

    def collectPreset(self):
        return {name: widget.getValue() for name, widget in self.items.items()}

    def showOnlyRelevantFields(self):
        preset = self.collectPreset()
        for name, widget in self.items.items():
            if name not in preset:
                continue
            widget.showIfRelevant(preset)
        self.onResize()

    def collectReleventPreset(self):
        preset = self.collectPreset()
        return {name: widget.getValue()
                for name, widget in self.items.items()
                if widget.parameter.isGuiRelevant(preset)}


class PanelizeDialog(wx.Dialog):
    def __init__(self, parent=None, board=None):
        wx.Dialog.__init__(
            self, parent, title=f'Panelize a board  (version {kikit.__version__})',
            style=wx.DEFAULT_DIALOG_STYLE)
        self.Bind(wx.EVT_CLOSE, self.OnClose, id=self.GetId())

        topMostBoxSizer = wx.BoxSizer(wx.VERTICAL)

        middleSizer = wx.BoxSizer(wx.HORIZONTAL)

        maxDisplayArea = wx.Display().GetClientArea()
        self.maxDialogSize = wx.Size(
            min(500, maxDisplayArea.Width),
            min(800, maxDisplayArea.Height - 200))

        self.scrollWindow = wx.ScrolledWindow(
            self, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.VSCROLL)
        self.scrollWindow.SetSizeHints(self.maxDialogSize, wx.Size(self.maxDialogSize.width, -1))
        self.scrollWindow.SetScrollRate(5, 5)
        self._buildSections(self.scrollWindow)
        middleSizer.Add(self.scrollWindow, 0, wx.EXPAND | wx.ALL, 5)

        self._buildOutputSections(middleSizer)

        topMostBoxSizer.Add(middleSizer, 1, wx.EXPAND | wx.ALL, 5)
        self._buildBottomButtons(topMostBoxSizer)

        self.SetSizer(topMostBoxSizer)
        self.populateInitialValue()
        self.buildOutputSections()
        self.showOnlyRelevantFields()
        self.OnResize()

    def _buildOutputSections(self, sizer):
        internalSizer = wx.BoxSizer(wx.VERTICAL)

        cliLabel = wx.StaticText(self, label="KiKit CLI command:",
                                 size=wx.DefaultSize, style=wx.ALIGN_LEFT)
        internalSizer.Add(cliLabel, 0, wx.EXPAND | wx.ALL, 2)

        self.kikitCmdWidget = wx.TextCtrl(
            self, wx.ID_ANY, "KiKit Command", wx.DefaultPosition, wx.DefaultSize,
            wx.TE_MULTILINE | wx.TE_READONLY)
        self.kikitCmdWidget.SetSizeHints(
            wx.Size(self.maxDialogSize.width,
                    self.maxDialogSize.height // 2),
            wx.Size(self.maxDialogSize.width, -1))
        cmdFont = self.kikitCmdWidget.GetFont()
        cmdFont.SetFamily(wx.FONTFAMILY_TELETYPE)
        self.kikitCmdWidget.SetFont(cmdFont)
        internalSizer.Add(self.kikitCmdWidget, 0, wx.EXPAND | wx.ALL, 2)

        jsonLabel = wx.StaticText(self, label="KiKit JSON preset (contains only changed keys):",
                                  size=wx.DefaultSize, style=wx.ALIGN_LEFT)
        internalSizer.Add(jsonLabel, 0, wx.EXPAND | wx.ALL, 2)

        self.kikitJsonWidget = wx.TextCtrl(
            self, wx.ID_ANY, "KiKit JSON", wx.DefaultPosition, wx.DefaultSize,
            wx.TE_MULTILINE | wx.TE_READONLY)
        self.kikitJsonWidget.SetSizeHints(
            wx.Size(self.maxDialogSize.width,
                    self.maxDialogSize.height // 2),
            wx.Size(self.maxDialogSize.width, -1))
        cmdFont = self.kikitJsonWidget.GetFont()
        cmdFont.SetFamily(wx.FONTFAMILY_TELETYPE)
        self.kikitJsonWidget.SetFont(cmdFont)
        internalSizer.Add(self.kikitJsonWidget, 0, wx.EXPAND | wx.ALL, 2)

        sizer.Add(internalSizer, 0, wx.EXPAND | wx.ALL, 2)

    def _buildSections(self, parentWindow):
        sectionsSizer = wx.BoxSizer(wx.VERTICAL)

        sections = {
            "Input": {
                "Input file": SFile("*.kicad_pcb")
            }
        }
        sections.update(kikit.panelize_ui_sections.availableSections)

        self.sections = {
            name: SectionGui(parentWindow, name, section,
                             lambda evt: self.OnResize(), lambda evt: self.OnChange())
            for name, section in sections.items()
        }
        for section in self.sections.values():
            sectionsSizer.Add(section.container, 0, wx.ALL | wx.EXPAND, 5)

        parentWindow.SetSizer(sectionsSizer)

    def _buildBottomButtons(self, parentSizer):
        button_box = wx.BoxSizer(wx.HORIZONTAL)
        closeButton = wx.Button(self, label='Close')
        self.Bind(wx.EVT_BUTTON, self.OnClose, id=closeButton.GetId())
        button_box.Add(closeButton, 1, wx.RIGHT, 10)
        self.okButton = wx.Button(self, label='Panelize')
        self.Bind(wx.EVT_BUTTON, self.OnPanelize, id=self.okButton.GetId())
        button_box.Add(self.okButton, 1)

        parentSizer.Add(button_box, 0, wx.ALIGN_RIGHT |
                        wx.LEFT | wx.RIGHT | wx.BOTTOM, 20)

    def OnResize(self):
        for section in self.sections.values():
            section.onResize()
        self.scrollWindow.GetSizer().Layout()
        self.scrollWindow.FitInside()
        self.scrollWindow.Fit()
        self.GetSizer().Layout()
        self.Fit()

    def OnClose(self, event):
        self.EndModal(0)

    def OnPanelize(self, event):
        # You might be wondering, why we specify delete=False. The reason is
        # Windows - the file cannot be opened for the second time. So we use
        # this only to get a valid temporary name. This is why we close the file
        # ASAP and only use its name
        with tempfile.NamedTemporaryFile(suffix=".kicad_pcb", delete=False) as f:
            try:
                fname = f.name
                f.close()

                progressDlg = wx.ProgressDialog(
                    "Running kikit", "Running kikit, please wait")
                progressDlg.Show()
                progressDlg.Pulse()

                args = self.kikitArgs()
                preset = obtainPreset([], **args)
                input = self.sections["Input"].items["Input file"].getValue()
                if len(input) == 0:
                    dlg = wx.MessageDialog(
                        None, f"No input file specified", "Error", wx.OK)
                    dlg.ShowModal()
                    dlg.Destroy()
                    return
                output = fname
                thread = ExceptionThread(target=panelize_ui.doPanelization,
                                         args=(input, output, preset))
                thread.daemon = True
                thread.start()
                while True:
                    progressDlg.Pulse()
                    thread.join(timeout=1)
                    if not thread.is_alive():
                        break
                if thread.exception:
                    raise thread.exception
                # KiCAD 6 does something strange here, so we will load
                # an empty file if we read it directly, but we can always make
                # a copy and read that:
                with tempfile.NamedTemporaryFile(suffix=".kicad_pcb", delete=False) as tp:
                    tpname = tp.name
                    tp.close()
                    shutil.copy(f.name, tpname)
                    panel = pcbnew.LoadBoard(tpname)
                transplateBoard(panel, self.board)
            except Exception as e:
                dlg = wx.MessageDialog(
                    None, f"Cannot perform:\n\n{e}", "Error", wx.OK)
                dlg.ShowModal()
                dlg.Destroy()
            finally:
                progressDlg.Hide()
                progressDlg.Destroy()
                try:
                    os.remove(fname)
                    os.remove(tpname)
                except Exception:
                    pass
        pcbnew.Refresh()

    def populateInitialValue(self):
        preset = loadPresetChain([":default"])
        for name, section in self.sections.items():
            if name.lower() not in preset:
                continue
            section.populateInitialValue(preset[name.lower()])

    def showOnlyRelevantFields(self):
        for section in self.sections.values():
            section.showOnlyRelevantFields()

    def collectPreset(self):
        preset = loadPresetChain([":default"])
        for name, section in self.sections.items():
            if name.lower() not in preset:
                continue
            preset[name.lower()].update(section.collectPreset())
        return preset

    def collectReleventPreset(self):
        preset = {}
        for name, section in self.sections.items():
            preset[name.lower()] = section.collectReleventPreset()
        del preset["input"]
        return preset

    def OnChange(self):
        self.showOnlyRelevantFields()
        self.OnResize()
        self.buildOutputSections()

    def buildOutputSections(self):
        defaultPreset = loadPresetChain([":default"])
        preset = self.collectReleventPreset()
        presetUpdates = presetDifferential(defaultPreset, preset)

        self.kikitJsonWidget.ChangeValue(json.dumps(presetUpdates, indent=4))

        kikitCommand = "kikit panelize \\\n"
        for section, values in presetUpdates.items():
            if len(values) == 0:
                continue
            attrs = "; ".join(
                [f"{key}: {value}" for key, value in values.items()])
            kikitCommand += f"    --{section} '{attrs}' \\\n"
        inputFilename = self.sections["Input"].items["Input file"].getValue()
        if len(inputFilename) == 0:
            inputFilename = "<missingInput>"
        kikitCommand += f"    {inputFilename} panel.kicad_pcb"
        self.kikitCmdWidget.ChangeValue(kikitCommand)

    def kikitArgs(self):
        defaultPreset = loadPresetChain([":default"])
        preset = self.collectReleventPreset()
        presetUpdates = presetDifferential(defaultPreset, preset)

        args = {}
        for section, values in presetUpdates.items():
            if len(values) == 0:
                continue
            args[section] = values
        return args


class PanelizePlugin(pcbnew.ActionPlugin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dialog = None

    def defaults(self):
        self.name = "KiKit: Panelize PCB"
        self.category = "KiKit"
        self.description = "Create a panel"
        self.icon_file_name = os.path.join(PKG_BASE, "resources", "graphics", "panelizeIcon_24x24.png")
        self.show_toolbar_button = True

    def Run(self):
        try:
            if self.dialog is None:
                self.dialog = PanelizeDialog()
            board = pcbnew.GetBoard()
            self.dialog.board = board
            self.dialog.ShowModal()
        except Exception as e:
            dlg = wx.MessageDialog(
                None, f"Cannot perform: {e}", "Error", wx.OK)
            dlg.ShowModal()
            dlg.Destroy()


plugin = PanelizePlugin

if __name__ == "__main__":
    # Run test dialog
    app = wx.App()

    dialog = PanelizeDialog()
    dialog.ShowModal()

    app.MainLoop()
