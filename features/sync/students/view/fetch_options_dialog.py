import wx


class FetchOptionsDialog(wx.Dialog):
    def __init__(self, parent, show_advanced_options: bool = True):
        super().__init__(
            parent,
            title="Fetch Options",
            size=wx.Size(500, 340 if show_advanced_options else 240),
            style=wx.DEFAULT_DIALOG_STYLE,
        )

        self.show_advanced_options = show_advanced_options
        self.init_ui()
        self.CenterOnParent()

    def init_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        main_sizer.AddSpacer(15)

        header_sizer = wx.BoxSizer(wx.HORIZONTAL)

        title_label = wx.StaticText(self, label="Data to Fetch")
        font = title_label.GetFont()
        font = font.Bold()
        title_label.SetFont(font)
        header_sizer.Add(title_label, 0, wx.ALIGN_CENTER_VERTICAL)

        header_sizer.AddStretchSpacer()

        self.select_all_checkbox = wx.CheckBox(
            self,
            label="Select All",
            style=wx.CHK_3STATE | wx.CHK_ALLOW_3RD_STATE_FOR_USER,
        )
        self.select_all_checkbox.Set3StateValue(wx.CHK_CHECKED)
        self.select_all_checkbox.Bind(wx.EVT_CHECKBOX, self.on_select_all_checkbox)
        header_sizer.Add(self.select_all_checkbox, 0, wx.ALIGN_CENTER_VERTICAL)

        main_sizer.Add(header_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)

        main_sizer.AddSpacer(5)

        separator_line = wx.StaticLine(self, style=wx.LI_HORIZONTAL)
        main_sizer.Add(separator_line, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)

        main_sizer.AddSpacer(10)

        checkbox_sizer = wx.BoxSizer(wx.VERTICAL)

        self.student_info_checkbox = wx.CheckBox(
            self, label="Student Info (Name, IC/Passport, Phones, Country, etc.)"
        )
        self.student_info_checkbox.SetValue(True)
        self.student_info_checkbox.Bind(wx.EVT_CHECKBOX, self.on_data_checkbox_changed)
        checkbox_sizer.Add(self.student_info_checkbox, 0, wx.BOTTOM, 5)

        self.personal_info_checkbox = wx.CheckBox(
            self, label="Personal Info (DOB, Gender, Marital Status, Religion, etc.)"
        )
        self.personal_info_checkbox.SetValue(True)
        self.personal_info_checkbox.Bind(wx.EVT_CHECKBOX, self.on_data_checkbox_changed)
        checkbox_sizer.Add(self.personal_info_checkbox, 0, wx.BOTTOM, 5)

        self.education_history_checkbox = wx.CheckBox(
            self, label="Educational History (Previous schools, qualifications, etc.)"
        )
        self.education_history_checkbox.SetValue(True)
        self.education_history_checkbox.Bind(
            wx.EVT_CHECKBOX, self.on_data_checkbox_changed
        )
        checkbox_sizer.Add(self.education_history_checkbox, 0, wx.BOTTOM, 5)

        self.enrollment_data_checkbox = wx.CheckBox(
            self, label="Enrollment Data (Programs, Semesters, Modules, etc.)"
        )
        self.enrollment_data_checkbox.SetValue(True)
        self.enrollment_data_checkbox.Bind(
            wx.EVT_CHECKBOX, self.on_data_checkbox_changed
        )
        checkbox_sizer.Add(self.enrollment_data_checkbox, 0)

        main_sizer.Add(checkbox_sizer, 0, wx.LEFT | wx.RIGHT, 15)

        if self.show_advanced_options:
            main_sizer.AddSpacer(15)

            separator_line2 = wx.StaticLine(self, style=wx.LI_HORIZONTAL)
            main_sizer.Add(separator_line2, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)

            main_sizer.AddSpacer(10)

            advanced_header = wx.StaticText(self, label="Advanced Options")
            font = advanced_header.GetFont()
            font = font.Bold()
            advanced_header.SetFont(font)
            main_sizer.Add(advanced_header, 0, wx.LEFT | wx.RIGHT, 15)

            main_sizer.AddSpacer(10)

            advanced_sizer = wx.BoxSizer(wx.VERTICAL)

            self.skip_active_term_checkbox = wx.CheckBox(
                self,
                label="Skip active term semester (don't import semester data for the active term)",
            )
            self.skip_active_term_checkbox.SetValue(True)
            advanced_sizer.Add(self.skip_active_term_checkbox, 0, wx.BOTTOM, 5)

            self.delete_programs_checkbox = wx.CheckBox(
                self,
                label="Delete existing program data before import (cascades to semesters & modules)",
            )
            self.delete_programs_checkbox.SetValue(False)
            advanced_sizer.Add(self.delete_programs_checkbox, 0)

            main_sizer.Add(advanced_sizer, 0, wx.LEFT | wx.RIGHT, 15)

        main_sizer.AddSpacer(20)

        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.AddStretchSpacer()

        cancel_button = wx.Button(self, wx.ID_CANCEL, label="Cancel")
        button_sizer.Add(cancel_button, 0, wx.RIGHT, 10)

        self.fetch_button = wx.Button(self, wx.ID_OK, label="Fetch")
        self.fetch_button.SetDefault()
        button_sizer.Add(self.fetch_button, 0)

        main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        self.SetSizer(main_sizer)
        self.update_fetch_button_state()

    def get_import_options(self):
        options = {
            "student_info": self.student_info_checkbox.GetValue(),
            "personal_info": self.personal_info_checkbox.GetValue(),
            "education_history": self.education_history_checkbox.GetValue(),
            "enrollment_data": self.enrollment_data_checkbox.GetValue(),
        }
        if self.show_advanced_options:
            options["skip_active_term"] = self.skip_active_term_checkbox.GetValue()
            options["delete_programs_before_import"] = (
                self.delete_programs_checkbox.GetValue()
            )
        else:
            options["skip_active_term"] = True
            options["delete_programs_before_import"] = False
        return options

    def on_select_all_checkbox(self, event):
        is_checked = self.select_all_checkbox.GetValue()
        self.student_info_checkbox.SetValue(is_checked)
        self.personal_info_checkbox.SetValue(is_checked)
        self.education_history_checkbox.SetValue(is_checked)
        self.enrollment_data_checkbox.SetValue(is_checked)
        self.update_fetch_button_state()

    def on_data_checkbox_changed(self, event):
        all_checked = all(
            [
                self.student_info_checkbox.GetValue(),
                self.personal_info_checkbox.GetValue(),
                self.education_history_checkbox.GetValue(),
                self.enrollment_data_checkbox.GetValue(),
            ]
        )
        any_checked = any(
            [
                self.student_info_checkbox.GetValue(),
                self.personal_info_checkbox.GetValue(),
                self.education_history_checkbox.GetValue(),
                self.enrollment_data_checkbox.GetValue(),
            ]
        )

        if all_checked:
            self.select_all_checkbox.Set3StateValue(wx.CHK_CHECKED)
        elif any_checked:
            self.select_all_checkbox.Set3StateValue(wx.CHK_UNDETERMINED)
        else:
            self.select_all_checkbox.Set3StateValue(wx.CHK_UNCHECKED)

        self.update_fetch_button_state()

    def update_fetch_button_state(self):
        has_checkboxes = any(
            [
                self.student_info_checkbox.GetValue(),
                self.personal_info_checkbox.GetValue(),
                self.education_history_checkbox.GetValue(),
                self.enrollment_data_checkbox.GetValue(),
            ]
        )
        self.fetch_button.Enable(has_checkboxes)
