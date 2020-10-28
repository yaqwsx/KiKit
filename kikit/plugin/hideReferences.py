import pcbnew
import wx
from kikit import modify

class HideReferencesDialog(wx.Dialog):
    def __init__(self, parent=None):
        wx.Dialog.__init__(self, parent, title='Specify which components to hide')
        self.Bind(wx.EVT_CLOSE, self.OnCancel, id=self.GetId())

        panel = wx.Panel(self)

        vbox = wx.BoxSizer(wx.VERTICAL)
        item_grid = wx.FlexGridSizer(0, 2, 3, 5)
        item_grid.AddGrowableCol(1)

        label = wx.StaticText(panel,
            label="Apply to labels pattern:\n(regular expression)",
            size=wx.Size(200, -1),
            style=wx.ALIGN_RIGHT)
        label.Wrap(200)
        item_grid.Add(label, 1, wx.ALIGN_CENTRE_VERTICAL)
        self.pattern = wx.TextCtrl(panel, style=wx.TE_LEFT, value='.*',
            size=wx.Size(250, -1))
        item_grid.Add(self.pattern, 1, wx.EXPAND)

        label = wx.StaticText(panel, label="What to do:",
            size=wx.Size(200, -1),
            style=wx.ALIGN_RIGHT)
        label.Wrap(200)
        item_grid.Add(label, 1, wx.ALIGN_CENTRE_VERTICAL)
        self.action = wx.Choice(panel, style=wx.CB_DROPDOWN,
            choices=["Show", "Hide"])
        self.action.SetSelection(1)
        item_grid.Add(self.action, 1, wx.EXPAND)

        button_box = wx.BoxSizer(wx.HORIZONTAL)
        btn_cancel = wx.Button(panel, label='Cancel')
        self.Bind(wx.EVT_BUTTON, self.OnCancel, id=btn_cancel.GetId())
        button_box.Add(btn_cancel, 1, wx.RIGHT, 10)
        btn_create = wx.Button(panel, label='Apply')
        self.Bind(wx.EVT_BUTTON, self.OnCreate, id=btn_create.GetId())
        button_box.Add(btn_create, 1)

        vbox.Add(item_grid, 1, wx.EXPAND | wx.ALIGN_CENTRE | wx.ALL, 10)
        vbox.Add(button_box, 0, wx.ALIGN_RIGHT | wx.LEFT | wx.RIGHT | wx.BOTTOM, 20)
        panel.SetSizer(vbox)
        vbox.Fit(self)
        self.Centre()

    def OnCancel(self, event):
        self.EndModal(0)

    def OnCreate(self, event):
        self.EndModal(1)

    def GetShowLabels(self):
        return self.action.GetSelection() == 0

    def GetPattern(self):
        return self.pattern.GetValue()

class HideReferencesPlugin(pcbnew.ActionPlugin):
    def defaults(self):
        self.name = "Show/hide references"
        self.category = "Modify PCB"
        self.description = "Show/hide references in the board based on regular expression"

    def Run(self):
        try:
            dialog = HideReferencesDialog()
            ok = dialog.ShowModal()
            if not ok:
                return

            board = pcbnew.GetBoard()
            modify.references(board, dialog.GetShowLabels(), dialog.GetPattern())
        except Exception as e:
            dlg = wx.MessageDialog(None, f"Cannot perform: {e}", "Error", wx.OK)
            dlg.ShowModal()
            dlg.Destroy()

if __name__ == "__main__":
    # Run test dialog
    app = wx.App()

    dialog = HideReferencesDialog()
    dialog.ShowModal()

    app.MainLoop()