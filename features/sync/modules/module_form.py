from datetime import date

import wx


class ModuleFormDialog(wx.Dialog):
    def __init__(self, module_data, parent=None, status_bar=None):
        super().__init__(
            parent,
            title=f"Update Module: {module_data.get('code', '')}",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self.module_data = module_data
        self.status_bar = status_bar
        self.SetSize(wx.Size(520, 420))
        self.init_ui()
        if parent is not None:
            self.CentreOnParent()
        else:
            self.Centre()

    def init_ui(self):
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        form_sizer = wx.FlexGridSizer(rows=6, cols=2, vgap=10, hgap=10)
        form_sizer.AddGrowableCol(1)

        # Module ID (read-only)
        form_sizer.Add(
            wx.StaticText(panel, label="Module ID:"),
            0,
            wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL,
        )
        module_id_text = wx.StaticText(
            panel, label=str(self.module_data.get("id", ""))
        )
        form_sizer.Add(module_id_text, 0, wx.EXPAND)

        # Module Code
        form_sizer.Add(
            wx.StaticText(panel, label="Code:"),
            0,
            wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL,
        )
        self.code_input = wx.TextCtrl(
            panel, value=self.module_data.get("code", "") or ""
        )
        form_sizer.Add(self.code_input, 0, wx.EXPAND)

        # Module Name
        form_sizer.Add(
            wx.StaticText(panel, label="Name:"),
            0,
            wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL,
        )
        self.name_input = wx.TextCtrl(
            panel, value=self.module_data.get("name", "") or ""
        )
        form_sizer.Add(self.name_input, 0, wx.EXPAND)

        # Status
        form_sizer.Add(
            wx.StaticText(panel, label="Status:"),
            0,
            wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL,
        )
        self.status_choice = wx.Choice(
            panel, choices=["Active", "Defunct"]
        )
        current_status = self.module_data.get("status", "").strip()
        if current_status.lower() == "active":
            self.status_choice.SetSelection(0)
        elif current_status.lower() == "defunct":
            self.status_choice.SetSelection(1)
        else:
            self.status_choice.SetSelection(0)
        form_sizer.Add(self.status_choice, 0, wx.EXPAND)

        form_sizer.Add(
            wx.StaticText(panel, label="Remark:"),
            0,
            wx.ALIGN_RIGHT | wx.ALIGN_TOP,
        )
        self.remark_input = wx.TextCtrl(
            panel,
            value=self.module_data.get("remark", "") or "",
            style=wx.TE_MULTILINE,
            size=wx.Size(-1, 90),
        )
        form_sizer.Add(self.remark_input, 0, wx.EXPAND)

        # Date Stamp
        form_sizer.Add(
            wx.StaticText(panel, label="Date Stamp:"),
            0,
            wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL,
        )
        current_timestamp = (self.module_data.get("timestamp") or "").strip()
        self.date_stamp_input = wx.TextCtrl(
            panel, value=current_timestamp or date.today().isoformat()
        )
        form_sizer.Add(self.date_stamp_input, 0, wx.EXPAND)

        main_sizer.Add(form_sizer, 0, wx.ALL | wx.EXPAND, 20)

        # Buttons
        button_sizer = wx.StdDialogButtonSizer()
        save_btn = wx.Button(panel, wx.ID_OK, "Save")
        save_btn.Bind(wx.EVT_BUTTON, self.on_save)
        button_sizer.AddButton(save_btn)

        cancel_btn = wx.Button(panel, wx.ID_CANCEL, "Cancel")
        button_sizer.AddButton(cancel_btn)
        button_sizer.Realize()

        main_sizer.Add(button_sizer, 0, wx.ALL | wx.ALIGN_RIGHT, 20)

        panel.SetSizer(main_sizer)

    def on_save(self, event):
        code = self.code_input.GetValue().strip()
        name = self.name_input.GetValue().strip()

        if not code:
            wx.MessageBox(
                "Code cannot be empty", "Validation Error", wx.OK | wx.ICON_WARNING
            )
            return

        if not name:
            wx.MessageBox(
                "Name cannot be empty", "Validation Error", wx.OK | wx.ICON_WARNING
            )
            return

        event.Skip()

    def get_updated_data(self):
        status_idx = self.status_choice.GetSelection()
        status = "Active" if status_idx == 0 else "Defunct"

        return {
            "id": self.module_data.get("id"),
            "code": self.code_input.GetValue().strip(),
            "name": self.name_input.GetValue().strip(),
            "status": status,
            "remark": self.remark_input.GetValue().strip() or None,
            "date_stamp": self.date_stamp_input.GetValue().strip(),
        }


class NewModuleFormDialog(wx.Dialog):
    def __init__(self, parent=None):
        super().__init__(
            parent,
            title="New Module",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self.SetSize(wx.Size(520, 380))
        self.init_ui()
        if parent is not None:
            self.CentreOnParent()
        else:
            self.Centre()

    def init_ui(self):
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        form_sizer = wx.FlexGridSizer(rows=4, cols=2, vgap=10, hgap=10)
        form_sizer.AddGrowableCol(1)

        form_sizer.Add(
            wx.StaticText(panel, label="Code:"),
            0,
            wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL,
        )
        self.code_input = wx.TextCtrl(panel)
        form_sizer.Add(self.code_input, 0, wx.EXPAND)

        form_sizer.Add(
            wx.StaticText(panel, label="Name:"),
            0,
            wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL,
        )
        self.name_input = wx.TextCtrl(panel)
        form_sizer.Add(self.name_input, 0, wx.EXPAND)

        form_sizer.Add(
            wx.StaticText(panel, label="Remark:"),
            0,
            wx.ALIGN_RIGHT | wx.ALIGN_TOP,
        )
        self.remark_input = wx.TextCtrl(panel, style=wx.TE_MULTILINE, size=wx.Size(-1, 90))
        form_sizer.Add(self.remark_input, 0, wx.EXPAND)

        form_sizer.Add(
            wx.StaticText(panel, label="Date Stamp:"),
            0,
            wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL,
        )
        self.date_stamp_input = wx.TextCtrl(panel, value=date.today().isoformat())
        form_sizer.Add(self.date_stamp_input, 0, wx.EXPAND)

        main_sizer.Add(form_sizer, 1, wx.ALL | wx.EXPAND, 20)

        button_sizer = wx.StdDialogButtonSizer()

        save_btn = wx.Button(panel, wx.ID_OK, "Save")
        save_btn.Bind(wx.EVT_BUTTON, self.on_save)
        button_sizer.AddButton(save_btn)

        cancel_btn = wx.Button(panel, wx.ID_CANCEL, "Cancel")
        button_sizer.AddButton(cancel_btn)

        button_sizer.Realize()
        main_sizer.Add(button_sizer, 0, wx.ALL | wx.ALIGN_RIGHT, 20)

        panel.SetSizer(main_sizer)

    def on_save(self, event):
        code = self.code_input.GetValue().strip()
        name = self.name_input.GetValue().strip()

        if not code:
            wx.MessageBox(
                "Code cannot be empty", "Validation Error", wx.OK | wx.ICON_WARNING
            )
            return

        if not name:
            wx.MessageBox(
                "Name cannot be empty", "Validation Error", wx.OK | wx.ICON_WARNING
            )
            return

        event.Skip()

    def get_new_data(self) -> dict:
        remark = self.remark_input.GetValue().strip() or None
        date_stamp = self.date_stamp_input.GetValue().strip() or None

        return {
            "code": self.code_input.GetValue().strip(),
            "name": self.name_input.GetValue().strip(),
            "remark": remark,
            "date_stamp": date_stamp,
            "status": "Active",
        }
