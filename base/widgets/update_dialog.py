import logging
import threading

import wx

from base.auto_update import AutoUpdater

logger = logging.getLogger(__name__)


class UpdateDialog(wx.Dialog):
    def __init__(self, parent, updater: AutoUpdater):
        super().__init__(
            parent,
            title="Update Available",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
            size=wx.Size(500, 400),
        )

        self.updater = updater
        self.is_downloading = False

        panel = wx.Panel(self)
        self.panel = panel
        sizer = wx.BoxSizer(wx.VERTICAL)

        title_font = wx.Font(
            14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD
        )
        title = wx.StaticText(
            panel, label=f"New Version Available: {updater.get_latest_version()}"
        )
        title.SetFont(title_font)
        sizer.Add(title, 0, wx.ALL, 10)

        current_version = wx.StaticText(
            panel, label=f"Current Version: {updater.current_version}"
        )
        sizer.Add(current_version, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        sizer.Add(
            wx.StaticLine(panel, style=wx.LI_HORIZONTAL), 0, wx.EXPAND | wx.ALL, 5
        )

        notes_label = wx.StaticText(panel, label="Release Notes:")
        notes_label_font = notes_label.GetFont()
        notes_label_font = notes_label_font.Bold()
        notes_label.SetFont(notes_label_font)
        sizer.Add(notes_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

        self.release_notes = wx.TextCtrl(
            panel,
            value=updater.get_release_notes() or "No release notes available.",
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_WORDWRAP,
        )
        sizer.Add(self.release_notes, 1, wx.EXPAND | wx.ALL, 10)

        self.progress_panel = wx.Panel(panel)
        progress_sizer = wx.BoxSizer(wx.VERTICAL)

        self.progress_label = wx.StaticText(self.progress_panel, label="")
        progress_sizer.Add(
            self.progress_label, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 5
        )

        self.progress_bar = wx.Gauge(self.progress_panel, range=100)
        self.progress_bar.SetMinSize(wx.Size(-1, 18))
        progress_sizer.Add(
            self.progress_bar, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5
        )

        self.progress_panel.SetSizer(progress_sizer)
        self.progress_panel.Hide()
        sizer.Add(
            self.progress_panel, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10
        )

        button_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.update_button = wx.Button(panel, label="Download and Install")
        self.update_button.Bind(wx.EVT_BUTTON, self.on_update)
        button_sizer.Add(self.update_button, 0, wx.ALL, 5)

        self.later_button = wx.Button(panel, label="Remind Me Later")
        self.later_button.Bind(wx.EVT_BUTTON, self.on_later)
        button_sizer.Add(self.later_button, 0, wx.ALL, 5)

        self.skip_button = wx.Button(panel, label="Skip This Version")
        self.skip_button.Bind(wx.EVT_BUTTON, self.on_skip)
        button_sizer.Add(self.skip_button, 0, wx.ALL, 5)

        sizer.Add(button_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        panel.SetSizer(sizer)
        self.Centre()

    def on_update(self, event):
        if self.is_downloading:
            return

        self.is_downloading = True
        self.update_button.Enable(False)
        self.later_button.Enable(False)
        self.skip_button.Enable(False)

        self.progress_panel.Show()
        self.panel.Layout()
        self.Layout()

        download_thread = threading.Thread(target=self._download_update, daemon=True)
        download_thread.start()

    def _download_update(self):
        def progress_callback(progress, downloaded, total):
            wx.CallAfter(self._update_progress, progress, downloaded, total)

        success = self.updater.download_and_install_update(progress_callback)

        if not success:
            wx.CallAfter(self._show_error)

    def _update_progress(self, progress, downloaded, total):
        mb_downloaded = downloaded / (1024 * 1024)
        mb_total = total / (1024 * 1024)
        self.progress_label.SetLabel(
            f"Downloading update... {mb_downloaded:.1f} MB / {mb_total:.1f} MB"
        )
        self.progress_bar.SetValue(progress)

    def _show_error(self):
        self.is_downloading = False
        self.update_button.Enable(True)
        self.later_button.Enable(True)
        self.skip_button.Enable(True)
        self.progress_panel.Hide()
        self.Layout()

        wx.MessageBox(
            "Failed to download or install the update. Please try again later.",
            "Update Error",
            wx.OK | wx.ICON_ERROR,
        )

    def on_later(self, event):
        self.EndModal(wx.ID_CANCEL)

    def on_skip(self, event):
        self.EndModal(wx.ID_IGNORE)


class UpdateCheckDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(
            parent,
            title="Checking for Updates",
            style=wx.DEFAULT_DIALOG_STYLE,
            size=wx.Size(300, 120),
        )

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        label = wx.StaticText(panel, label="Checking for updates...")
        sizer.Add(label, 0, wx.ALL | wx.ALIGN_CENTER, 20)

        self.gauge = wx.Gauge(panel, range=100, style=wx.GA_HORIZONTAL)
        self.gauge.Pulse()
        sizer.Add(self.gauge, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 20)

        panel.SetSizer(sizer)
        self.Centre()

        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_timer)
        self.timer.Start(50)

    def on_timer(self, event):
        self.gauge.Pulse()

    def close_dialog(self):
        self.timer.Stop()
        self.EndModal(wx.ID_OK)
