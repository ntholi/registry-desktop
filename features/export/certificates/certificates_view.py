import wx


class CertificatesView(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)

        label = wx.StaticText(self, label="Certificates Export View")
        sizer.Add(label, 1, wx.ALIGN_CENTER | wx.ALL, 40)

        self.SetSizer(sizer)
