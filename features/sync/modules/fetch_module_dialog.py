import threading

import wx


class FetchModuleDialog(wx.Dialog):
    def __init__(self, parent, service, status_bar=None):
        super().__init__(
            parent,
            title="Fetch Module",
            size=wx.Size(500, 200),
            style=wx.DEFAULT_DIALOG_STYLE,
        )
        self.service = service
        self.status_bar = status_bar
        self.worker = None

        self.init_ui()
        self.Centre()

    def init_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        main_sizer.AddSpacer(20)

        label = wx.StaticText(
            self,
            label="Enter the module code to fetch from the CMS:",
        )
        main_sizer.Add(label, 0, wx.LEFT | wx.RIGHT, 20)

        main_sizer.AddSpacer(10)

        self.code_text = wx.TextCtrl(self, size=wx.Size(-1, 30))
        main_sizer.Add(self.code_text, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)

        main_sizer.AddSpacer(20)

        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.AddStretchSpacer()

        cancel_button = wx.Button(self, wx.ID_CANCEL, "Cancel")
        button_sizer.Add(cancel_button, 0, wx.RIGHT, 10)

        self.fetch_button = wx.Button(self, wx.ID_OK, "Fetch")
        self.fetch_button.Bind(wx.EVT_BUTTON, self.on_fetch)
        button_sizer.Add(self.fetch_button, 0)

        main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)

        main_sizer.AddSpacer(20)

        self.SetSizer(main_sizer)

    def on_fetch(self, event):
        module_code = self.code_text.GetValue().strip()

        if not module_code:
            wx.MessageBox(
                "Please enter a module code",
                "Validation Error",
                wx.OK | wx.ICON_WARNING,
            )
            return

        self.fetch_button.Enable(False)
        self.code_text.Enable(False)

        self.worker = FetchModuleWorker(
            module_code,
            self.service,
            self.on_fetch_complete,
            self.on_progress,
        )
        self.worker.start()

    def on_progress(self, message, current, total):
        if self.status_bar:
            wx.CallAfter(self.status_bar.show_progress, message, current, total)

    def on_fetch_complete(self, success, message, saved_count=0):
        wx.CallAfter(self._handle_fetch_complete, success, message, saved_count)

    def _handle_fetch_complete(self, success, message, saved_count):
        if self.status_bar:
            self.status_bar.clear()

        self.fetch_button.Enable(True)
        self.code_text.Enable(True)

        if success:
            wx.MessageBox(
                f"Successfully fetched and saved {saved_count} module(s)!",
                "Success",
                wx.OK | wx.ICON_INFORMATION,
            )
            self.EndModal(wx.ID_OK)
        else:
            wx.MessageBox(
                f"Failed to fetch modules:\n{message}",
                "Error",
                wx.OK | wx.ICON_ERROR,
            )


class FetchModuleWorker(threading.Thread):
    def __init__(self, module_code, service, callback, progress_callback):
        super().__init__(daemon=True)
        self.module_code = module_code
        self.service = service
        self.callback = callback
        self.progress_callback = progress_callback

    def run(self):
        try:
            saved_count = self.service.fetch_and_save_modules(
                self.module_code,
                self.progress_callback,
            )
            self.callback(True, "Success", saved_count)
        except Exception as e:
            self.callback(False, str(e))
