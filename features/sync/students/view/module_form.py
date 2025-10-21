import wx


class ModuleFormDialog(wx.Dialog):
    def __init__(self, module_data, parent=None, status_bar=None):
        super().__init__(
            parent,
            title=f"Edit Module: {module_data.get('module_code', '')}",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self.module_data = module_data
        self.status_bar = status_bar
        self.SetSize(wx.Size(450, 350))
        self.init_ui()

    def init_ui(self):
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        form_sizer = wx.FlexGridSizer(rows=6, cols=2, vgap=10, hgap=10)
        form_sizer.AddGrowableCol(1)

        form_sizer.Add(
            wx.StaticText(panel, label="Module Code:"),
            0,
            wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL,
        )
        module_code_text = wx.StaticText(
            panel, label=str(self.module_data.get("module_code", ""))
        )
        form_sizer.Add(module_code_text, 0, wx.EXPAND)

        form_sizer.Add(
            wx.StaticText(panel, label="Module Name:"),
            0,
            wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL,
        )
        module_name_text = wx.StaticText(
            panel, label=str(self.module_data.get("module_name", ""))
        )
        form_sizer.Add(module_name_text, 0, wx.EXPAND)

        form_sizer.Add(
            wx.StaticText(panel, label="Status:"),
            0,
            wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL,
        )
        self.status_combobox = wx.ComboBox(
            panel, style=wx.CB_READONLY, choices=["Compulsory", "Elective", "Optional"]
        )
        current_status = self.module_data.get("status", "")
        if current_status in ["Compulsory", "Elective", "Optional"]:
            self.status_combobox.SetStringSelection(current_status)
        form_sizer.Add(self.status_combobox, 0, wx.EXPAND)

        form_sizer.Add(
            wx.StaticText(panel, label="Credits:"),
            0,
            wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL,
        )
        self.credits_input = wx.TextCtrl(
            panel, value=str(self.module_data.get("credits", ""))
        )
        form_sizer.Add(self.credits_input, 0, wx.EXPAND)

        form_sizer.Add(
            wx.StaticText(panel, label="Marks:"),
            0,
            wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL,
        )
        self.marks_input = wx.TextCtrl(
            panel, value=str(self.module_data.get("marks", ""))
        )
        form_sizer.Add(self.marks_input, 0, wx.EXPAND)

        form_sizer.Add(
            wx.StaticText(panel, label="Grade:"),
            0,
            wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL,
        )
        self.grade_input = wx.TextCtrl(
            panel, value=str(self.module_data.get("grade", ""))
        )
        form_sizer.Add(self.grade_input, 0, wx.EXPAND)

        main_sizer.Add(form_sizer, 0, wx.ALL | wx.EXPAND, 20)

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
        status = self.status_combobox.GetValue().strip()
        credits = self.credits_input.GetValue().strip()
        marks = self.marks_input.GetValue().strip()
        grade = self.grade_input.GetValue().strip()

        if not status:
            wx.MessageBox(
                "Please select a module status",
                "Validation Error",
                wx.OK | wx.ICON_WARNING,
            )
            return

        if credits:
            try:
                float(credits)
            except ValueError:
                wx.MessageBox(
                    "Credits must be a valid number",
                    "Validation Error",
                    wx.OK | wx.ICON_WARNING,
                )
                return

        event.Skip()

    def get_updated_data(self):
        credits_value = self.credits_input.GetValue().strip()

        return {
            "id": self.module_data.get("id"),
            "module_code": self.module_data.get("module_code"),
            "module_name": self.module_data.get("module_name"),
            "status": self.status_combobox.GetValue().strip(),
            "credits": credits_value if credits_value else None,
            "marks": self.marks_input.GetValue().strip(),
            "grade": self.grade_input.GetValue().strip(),
        }
