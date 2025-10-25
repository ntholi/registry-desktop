import wx


class StudentView(wx.Panel):
    def __init__(self, parent, status_bar):
        super().__init__(parent)
        self.status_bar = status_bar
        sizer = wx.BoxSizer(wx.VERTICAL)

        label = wx.StaticText(self, label="Student Enrollment View")
        sizer.Add(label, 1, wx.ALIGN_CENTER | wx.ALL, 40)

        self.SetSizer(sizer)
