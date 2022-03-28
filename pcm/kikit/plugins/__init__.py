import wx
import wx.adv

class MissingKiKitDialog(wx.Dialog):
    def __init__(self, parent=None):
        wx.Dialog.__init__(self, parent, id=wx.ID_ANY, title=u"KiKit installation not found!",
                           pos=wx.DefaultPosition, size=wx.Size(500, 300), style=wx.DEFAULT_DIALOG_STYLE)

        self.SetSizeHints(wx.DefaultSize, wx.DefaultSize)

        bSizer1 = wx.BoxSizer(wx.VERTICAL)

        self.staticText = wx.StaticText(
            self, wx.ID_ANY, u"No KiKit backend found! You probably installed KiKit only via PCM.\n\nPlease follow the installation guite at the link below. Until you finish the installation no KiKit funcitons will be available. After finishing the intallation, please restart KiCAD.", wx.DefaultPosition, wx.DefaultSize, 0)
        self.staticText.Wrap(-1)

        bSizer1.Add(self.staticText, 1, wx.ALL | wx.EXPAND, 5)

        self.hyperlink = wx.adv.HyperlinkCtrl(self, wx.ID_ANY, u"https://github.com/yaqwsx/KiKit/blob/master/doc/installation.md",
                                              u"https://github.com/yaqwsx/KiKit/blob/master/doc/installation.md", wx.DefaultPosition, wx.DefaultSize, wx.adv.HL_ALIGN_CENTRE | wx.adv.HL_DEFAULT_STYLE)
        bSizer1.Add(self.hyperlink, 0, wx.ALL | wx.EXPAND, 5)

        self.okButton = wx.Button(
            self, wx.ID_ANY, u"OK", wx.DefaultPosition, wx.DefaultSize, 0)
        bSizer1.Add(self.okButton, 0, wx.ALL | wx.EXPAND, 5)

        self.SetSizer(bSizer1)
        self.Layout()

        self.Centre(wx.BOTH)

        self.okButton.Bind(wx.EVT_BUTTON, self.OnOK)

    def OnOK(self, event):
        if self.IsModal():
            self.EndModal(0)
        else:
            self.Close(True)


try:
    from kikit.plugin import importAllPlugins

    importAllPlugins()
except ImportError:
    dialog = MissingKiKitDialog()
    dialog.Show()
    dialog.Destroy()

if __name__ == "__main__":
    # Run test dialog
    app = wx.App()

    dialog = MissingKiKitDialog()
    dialog.ShowModal()
    dialog.Destroy()
