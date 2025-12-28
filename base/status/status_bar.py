import time
from collections import deque
from typing import Deque, Tuple

import wx


class StatusBar(wx.Panel):
    RATE_SAMPLE_WINDOW = 50
    MIN_SAMPLES_FOR_ESTIMATE = 3
    RATE_UPDATE_INTERVAL = 0.5

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

        self._reset_progress_state()

    def _reset_progress_state(self):
        self.start_time: float | None = None
        self.last_current = 0
        self.last_update_time = 0.0
        self.rate_samples: Deque[Tuple[float, int]] = deque(
            maxlen=self.RATE_SAMPLE_WINDOW
        )
        self.smoothed_rate: float | None = None

    def show_progress(self, message: str, current: int, total: int):
        wx.CallAfter(self._show_progress_impl, message, current, total)

    def _calculate_rate(self, current: int, now: float) -> float | None:
        if len(self.rate_samples) < self.MIN_SAMPLES_FOR_ESTIMATE:
            return None

        oldest_time, oldest_count = self.rate_samples[0]
        time_span = now - oldest_time
        items_processed = current - oldest_count

        if time_span <= 0 or items_processed <= 0:
            return None

        current_rate = items_processed / time_span

        if self.smoothed_rate is None:
            self.smoothed_rate = current_rate
        else:
            alpha = 0.3
            self.smoothed_rate = alpha * current_rate + (1 - alpha) * self.smoothed_rate

        return self.smoothed_rate

    def _show_progress_impl(self, message: str, current: int, total: int):
        self.message_text.SetLabel(message)
        now = time.time()

        if self.start_time is None:
            self.start_time = now
            self.last_current = 0
            self.last_update_time = now
            self.rate_samples.clear()
            self.smoothed_rate = None

        if total > 0:
            percentage = int((current / total) * 100)
            self.progress_bar.SetRange(100)
            self.progress_bar.SetValue(percentage)
            self.percentage_text.SetLabel(f"{percentage}%")

            if current > self.last_current:
                time_since_last_sample = now - self.last_update_time
                if (
                    time_since_last_sample >= self.RATE_UPDATE_INTERVAL
                    or len(self.rate_samples) == 0
                ):
                    self.rate_samples.append((now, current))
                    self.last_update_time = now

                rate = self._calculate_rate(current, now)
                remaining_items = total - current

                if rate is not None and rate > 0:
                    estimated_seconds = remaining_items / rate
                    time_str = self._format_time(estimated_seconds)
                    self.time_remaining_text.SetLabel(f"~{time_str} remaining")
                    self.time_remaining_text.Show()
                elif self.start_time is not None and current > 0:
                    elapsed = now - self.start_time
                    if elapsed > 0:
                        fallback_rate = current / elapsed
                        if fallback_rate > 0:
                            estimated_seconds = remaining_items / fallback_rate
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
        self._reset_progress_state()
        self.Hide()
        self.GetParent().Layout()
