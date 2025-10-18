import wx


class StudentView(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)

        label = wx.StaticText(self, label="Student Enrollment View")
        sizer.Add(label, 1, wx.ALIGN_CENTER | wx.ALL, 40)

        self.SetSizer(sizer)
