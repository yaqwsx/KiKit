import wx
import threading

app = None

def initDialog(initFn):
    global app
    try:
        return initFn()
    except Exception:
        try:
            # Some Linux distributions ship incompatible wxPhoenix version.
            # So we start a custom wxApp loop
            app = wx.App()
            app.InitLocale()
            t = threading.Thread(target=app.MainLoop)
            t.daemon = True
            t.start()
            return initFn()
        except Exception as e:
            raise e from None

def destroyDialog(dialog):
    if dialog is not None:
        dialog.Destroy()
