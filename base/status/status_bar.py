import time

import wx


class StatusBar(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)
        self.SetMinSize(wx.Size(-1, 30))

        sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.message_text = wx.StaticText(self, label="")
        sizer.Add(self.message_text, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 10)

        sizer.AddStretchSpacer()

        self.time_remaining_text = wx.StaticText(self, label="")
        self.time_remaining_text.Hide()
        sizer.Add(self.time_remaining_text, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        self.progress_bar = wx.Gauge(self, range=100, size=wx.Size(200, 18))
        self.progress_bar.Hide()
        sizer.Add(self.progress_bar, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)

        self.percentage_text = wx.StaticText(self, label="")
        self.percentage_text.Hide()
        sizer.Add(self.percentage_text, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        self.SetSizer(sizer)
        self.Hide()

        self.start_time = None
        self.last_current = 0

    def show_progress(self, message: str, current: int, total: int):
        wx.CallAfter(self._show_progress_impl, message, current, total)

    def _show_progress_impl(self, message: str, current: int, total: int):
        self.message_text.SetLabel(message)

        if self.start_time is None:
            self.start_time = time.time()
            self.last_current = 0

        if total > 0:
            percentage = int((current / total) * 100)
            self.progress_bar.SetRange(100)
            self.progress_bar.SetValue(percentage)
            self.percentage_text.SetLabel(f"{percentage}%")

            if current > 0 and current != self.last_current:
                elapsed = time.time() - self.start_time
                rate = current / elapsed
                remaining_items = total - current

                if rate > 0:
                    estimated_seconds = remaining_items / rate
                    time_str = self._format_time(estimated_seconds)
                    self.time_remaining_text.SetLabel(f"~{time_str} remaining")
                    self.time_remaining_text.Show()

                self.last_current = current

        self.progress_bar.Show()
        self.percentage_text.Show()
        self.Show()
        self.GetParent().Layout()

    def _format_time(self, seconds: float) -> str:
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"{hours}h {minutes}m"
        else:
            days = int(seconds / 86400)
            hours = int((seconds % 86400) / 3600)
            return f"{days}d {hours}h"

    def show_message(self, message: str):
        wx.CallAfter(self._show_message_impl, message)

    def _show_message_impl(self, message: str):
        self.message_text.SetLabel(message)
        self.progress_bar.Hide()
        self.percentage_text.Hide()
        self.time_remaining_text.Hide()
        self.Show()
        self.GetParent().Layout()

    def clear(self):
        wx.CallAfter(self._clear_impl)

    def _clear_impl(self):
        self.message_text.SetLabel("")
        self.progress_bar.Hide()
        self.percentage_text.Hide()
        self.time_remaining_text.Hide()
        self.start_time = None
        self.last_current = 0
        self.Hide()
        self.GetParent().Layout()
