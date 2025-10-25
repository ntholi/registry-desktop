import wx


class LoadingPanel(wx.Panel):
    def __init__(self, parent: wx.Window, message: str = "Loading...") -> None:
        super().__init__(parent)
        self._indicator: wx.ActivityIndicator | None = None
        self._message: wx.StaticText | None = None
        self._setup_ui(parent, message)

    def _setup_ui(self, parent: wx.Window, message: str) -> None:
        background = parent.GetBackgroundColour()
        self.SetBackgroundColour(background)

        outer_sizer = wx.BoxSizer(wx.VERTICAL)
        outer_sizer.AddStretchSpacer()

        container = wx.Panel(self)
        container.SetBackgroundColour(background)
        container_sizer = wx.BoxSizer(wx.VERTICAL)
        container.SetSizer(container_sizer)

        self._indicator = wx.ActivityIndicator(container)
        self._indicator.SetMinSize(wx.Size(32, 32))

        self._message = wx.StaticText(container, label=message)
        font = self._message.GetFont()
        font.PointSize = 12
        self._message.SetFont(font)

        container_sizer.AddStretchSpacer()

        indicator_sizer = wx.BoxSizer(wx.HORIZONTAL)
        indicator_sizer.AddStretchSpacer()
        indicator_sizer.Add(self._indicator, 0, wx.ALL, 12)
        indicator_sizer.AddStretchSpacer()
        container_sizer.Add(indicator_sizer, 0, wx.EXPAND)

        message_sizer = wx.BoxSizer(wx.HORIZONTAL)
        message_sizer.AddStretchSpacer()
        message_sizer.Add(self._message, 0, wx.ALL, 6)
        message_sizer.AddStretchSpacer()
        container_sizer.Add(message_sizer, 0, wx.EXPAND)

        container_sizer.AddStretchSpacer()

        outer_sizer.Add(container, 0, wx.ALIGN_CENTER | wx.ALL, 24)
        outer_sizer.AddStretchSpacer()

        self.SetSizer(outer_sizer)
        self._indicator.Start()

    def set_message(self, message: str) -> None:
        if self._message:
            self._message.SetLabel(message)
            self.Layout()

    def start(self) -> None:
        if self._indicator and not self._indicator.IsRunning():
            self._indicator.Start()

    def stop(self) -> None:
        if self._indicator and self._indicator.IsRunning():
            self._indicator.Stop()
