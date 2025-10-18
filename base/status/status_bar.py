import wx


class StatusBar(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)
        self.SetMinSize((-1, 30))

        sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.message_text = wx.StaticText(self, label="")
        sizer.Add(self.message_text, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 10)

        sizer.AddStretchSpacer()

        self.progress_bar = wx.Gauge(self, range=100, size=(200, 18))
        self.progress_bar.Hide()
        sizer.Add(self.progress_bar, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        self.SetSizer(sizer)
        self.Hide()

    def show_progress(self, message: str, current: int, total: int):
        wx.CallAfter(self._show_progress_impl, message, current, total)

    def _show_progress_impl(self, message: str, current: int, total: int):
        self.message_text.SetLabel(message)
        if total > 0:
            percentage = int((current / total) * 100)
            self.progress_bar.SetRange(100)
            self.progress_bar.SetValue(percentage)
        self.progress_bar.Show()
        self.Show()
        self.GetParent().Layout()

    def show_message(self, message: str):
        wx.CallAfter(self._show_message_impl, message)

    def _show_message_impl(self, message: str):
        self.message_text.SetLabel(message)
        self.progress_bar.Hide()
        self.Show()
        self.GetParent().Layout()

    def clear(self):
        wx.CallAfter(self._clear_impl)

    def _clear_impl(self):
        self.message_text.SetLabel("")
        self.progress_bar.Hide()
        self.Hide()
        self.GetParent().Layout()
