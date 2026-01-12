import math
import threading
from typing import Any, Callable

import wx


class LoaderPanel(wx.Panel):
    def __init__(self, parent: wx.Window, message: str = "Loading..."):
        super().__init__(parent)
        self.message = message
        self.timer: wx.Timer | None = None
        self.spinner_angle = 0
        self.use_activity_indicator = False
        self.spinner: wx.ActivityIndicator | wx.Panel
        self.message_text: wx.StaticText
        self.init_ui()

    def init_ui(self) -> None:
        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.AddStretchSpacer()

        content_sizer = wx.BoxSizer(wx.HORIZONTAL)
        content_sizer.AddStretchSpacer()

        inner_sizer = wx.BoxSizer(wx.VERTICAL)

        try:
            self.spinner = wx.ActivityIndicator(self, size=wx.Size(48, 48))
            self.spinner.Start()
            self.use_activity_indicator = True
        except AttributeError:
            self.spinner = wx.Panel(self, size=wx.Size(48, 48))
            self.spinner.Bind(wx.EVT_PAINT, self.on_paint_spinner)
            self.use_activity_indicator = False
            self.timer = wx.Timer(self)
            self.Bind(wx.EVT_TIMER, self.on_timer)
            self.timer.Start(50)

        inner_sizer.Add(self.spinner, 0, wx.ALIGN_CENTER)

        inner_sizer.AddSpacer(15)

        self.message_text = wx.StaticText(self, label=self.message)
        font = self.message_text.GetFont()
        font.PointSize = 10
        self.message_text.SetFont(font)
        self.message_text.SetForegroundColour(wx.Colour(100, 100, 100))
        inner_sizer.Add(self.message_text, 0, wx.ALIGN_CENTER)

        content_sizer.Add(inner_sizer, 0, wx.ALIGN_CENTER)
        content_sizer.AddStretchSpacer()

        sizer.Add(content_sizer, 1, wx.EXPAND)
        sizer.AddStretchSpacer()

        self.SetSizer(sizer)

    def on_timer(self, event: wx.TimerEvent) -> None:
        self.spinner_angle = (self.spinner_angle + 10) % 360
        if isinstance(self.spinner, wx.Panel):
            self.spinner.Refresh()

    def on_paint_spinner(self, event: wx.PaintEvent) -> None:
        if not isinstance(self.spinner, wx.Panel):
            return

        dc = wx.PaintDC(self.spinner)
        dc.Clear()

        width, height = self.spinner.GetSize()
        center_x, center_y = width // 2, height // 2
        radius = min(width, height) // 2 - 5

        dc.SetPen(wx.Pen(wx.Colour(200, 200, 200), 3))

        for i in range(8):
            angle = (self.spinner_angle + i * 45) % 360

            x = center_x + int(radius * math.cos(math.radians(angle)))
            y = center_y + int(radius * math.sin(math.radians(angle)))
            opacity = int(255 * (i / 8.0))
            dc.SetPen(wx.Pen(wx.Colour(0, 120, 215, opacity), 3))
            dc.DrawCircle(x, y, 3)

    def set_message(self, message: str) -> None:
        self.message = message
        self.message_text.SetLabel(message)
        self.Layout()

    def stop(self) -> None:
        if self.use_activity_indicator and isinstance(
            self.spinner, wx.ActivityIndicator
        ):
            self.spinner.Stop()
        elif self.timer and self.timer.IsRunning():
            self.timer.Stop()


class DataLoader(threading.Thread):
    def __init__(
        self,
        load_func: Callable[..., Any],
        callback: Callable[[str, Any], None],
        *args: Any,
        **kwargs: Any,
    ):
        super().__init__(daemon=True)
        self.load_func = load_func
        self.callback = callback
        self.args = args
        self.kwargs = kwargs
        self.should_stop = False

    def run(self) -> None:
        try:
            if self.should_stop:
                return
            result = self.load_func(*self.args, **self.kwargs)
            if not self.should_stop:
                wx.CallAfter(lambda r=result: self.callback("success", r))
        except Exception as e:
            if not self.should_stop:
                error_msg = str(e)
                wx.CallAfter(lambda msg=error_msg: self.callback("error", msg))

    def stop(self) -> None:
        self.should_stop = True


class LoadableControl:
    def __init__(
        self, parent: wx.Window, on_load_complete: Callable[[bool, Any], None]
    ):
        self.parent = parent
        self.on_load_complete = on_load_complete
        self.loader_panel: LoaderPanel | None = None
        self.content_panel: wx.Window | None = None
        self.loader_thread: DataLoader | None = None
        self.container = wx.Panel(parent)
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.container.SetSizer(self.sizer)

    def get_container(self) -> wx.Panel:
        return self.container

    def show_loader(self, message: str = "Loading...") -> None:
        if self.content_panel and self.content_panel.IsShown():
            self.content_panel.Hide()

        if not self.loader_panel:
            self.loader_panel = LoaderPanel(self.container, message)
            self.sizer.Add(self.loader_panel, 1, wx.EXPAND)
        else:
            self.loader_panel.set_message(message)

        self.loader_panel.Show()
        self.container.Layout()

    def hide_loader(self) -> None:
        if self.loader_panel and self.loader_panel.IsShown():
            self.loader_panel.Hide()

        if self.content_panel:
            self.content_panel.Show()

        self.container.Layout()

    def set_content_panel(self, panel: wx.Window) -> None:
        if self.content_panel:
            self.sizer.Detach(self.content_panel)
            self.content_panel.Destroy()

        self.content_panel = panel
        self.sizer.Add(self.content_panel, 1, wx.EXPAND)
        self.content_panel.Hide()

    def load_async(
        self,
        load_func: Callable[..., Any],
        message: str = "Loading...",
        *args: Any,
        **kwargs: Any,
    ) -> None:
        self.show_loader(message)

        if self.loader_thread and self.loader_thread.is_alive():
            self.loader_thread.stop()

        self.loader_thread = DataLoader(
            load_func, self._on_load_callback, *args, **kwargs
        )
        self.loader_thread.start()

    def _on_load_callback(self, status: str, data: Any) -> None:
        self.hide_loader()
        if status == "success":
            self.on_load_complete(True, data)
        else:
            self.on_load_complete(False, data)

    def cleanup(self) -> None:
        if self.loader_thread and self.loader_thread.is_alive():
            self.loader_thread.stop()
        if self.loader_panel:
            self.loader_panel.stop()
