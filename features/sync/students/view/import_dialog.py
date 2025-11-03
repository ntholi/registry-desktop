import wx


class ImportStudentsDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(
            parent,
            title="Import Students",
            size=wx.Size(500, 600),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self.student_numbers = []
        self.init_ui()
        self.CenterOnParent()

    def init_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        main_sizer.AddSpacer(15)

        range_label = wx.StaticText(self, label="Range")
        font = range_label.GetFont()
        font = font.Bold()
        range_label.SetFont(font)
        main_sizer.Add(range_label, 0, wx.LEFT | wx.RIGHT, 15)

        main_sizer.AddSpacer(10)

        range_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.range_from = wx.TextCtrl(self)
        range_sizer.Add(self.range_from, 1, wx.EXPAND | wx.RIGHT, 10)

        range_sizer.Add(
            wx.StaticText(self, label="to"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10
        )

        self.range_to = wx.TextCtrl(self)
        range_sizer.Add(self.range_to, 1, wx.EXPAND | wx.RIGHT, 10)

        self.populate_button = wx.Button(self, label="Populate")
        self.populate_button.Bind(wx.EVT_BUTTON, self.on_populate)
        range_sizer.Add(self.populate_button, 0)

        main_sizer.Add(range_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)

        main_sizer.AddSpacer(20)

        self.select_all_checkbox = wx.CheckBox(self, label="Select All", style=wx.CHK_3STATE | wx.CHK_ALLOW_3RD_STATE_FOR_USER)
        self.select_all_checkbox.Set3StateValue(wx.CHK_CHECKED)
        self.select_all_checkbox.Bind(wx.EVT_CHECKBOX, self.on_select_all_checkbox)
        main_sizer.Add(self.select_all_checkbox, 0, wx.LEFT | wx.RIGHT, 15)

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
        self.education_history_checkbox.Bind(wx.EVT_CHECKBOX, self.on_data_checkbox_changed)
        checkbox_sizer.Add(self.education_history_checkbox, 0, wx.BOTTOM, 5)

        self.enrollment_data_checkbox = wx.CheckBox(
            self, label="Enrollment Data (Programs, Semesters, Modules, etc.)"
        )
        self.enrollment_data_checkbox.SetValue(True)
        self.enrollment_data_checkbox.Bind(wx.EVT_CHECKBOX, self.on_data_checkbox_changed)
        checkbox_sizer.Add(self.enrollment_data_checkbox, 0)

        main_sizer.Add(checkbox_sizer, 0, wx.LEFT | wx.RIGHT, 15)

        main_sizer.AddSpacer(20)

        list_label = wx.StaticText(self, label="Student Numbers")
        font = list_label.GetFont()
        font = font.Bold()
        list_label.SetFont(font)
        main_sizer.Add(list_label, 0, wx.LEFT | wx.RIGHT, 15)

        main_sizer.AddSpacer(10)

        self.student_list = wx.TextCtrl(
            self,
            style=wx.TE_MULTILINE | wx.TE_WORDWRAP,
            size=wx.Size(-1, 250),
        )
        self.student_list.Bind(wx.EVT_TEXT, self.on_student_list_changed)
        main_sizer.Add(self.student_list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)

        main_sizer.AddSpacer(10)

        self.status_text = wx.StaticText(self, label="0 Students to import")
        font = self.status_text.GetFont()
        font.SetPointSize(9)
        self.status_text.SetFont(font)
        main_sizer.Add(self.status_text, 0, wx.LEFT | wx.RIGHT, 15)

        main_sizer.AddSpacer(15)

        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.AddStretchSpacer()

        clear_button = wx.Button(self, label="Clear")
        clear_button.Bind(wx.EVT_BUTTON, self.on_clear)
        button_sizer.Add(clear_button, 0, wx.RIGHT, 10)

        cancel_button = wx.Button(self, wx.ID_CANCEL, label="Cancel")
        button_sizer.Add(cancel_button, 0, wx.RIGHT, 10)

        self.import_button = wx.Button(self, wx.ID_OK, label="Import")
        self.import_button.SetDefault()
        button_sizer.Add(self.import_button, 0)

        main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        self.SetSizer(main_sizer)
        self.update_import_button_state()

    def on_populate(self, event):
        start_num = self.range_from.GetValue().strip()
        end_num = self.range_to.GetValue().strip()

        if not start_num or not end_num:
            wx.MessageBox(
                "Please enter both start and end student numbers.",
                "Missing Input",
                wx.OK | wx.ICON_WARNING,
            )
            return

        try:
            if not start_num.isdigit() or not end_num.isdigit():
                wx.MessageBox(
                    "Student numbers must be numeric.",
                    "Invalid Input",
                    wx.OK | wx.ICON_WARNING,
                )
                return

            if len(start_num) != 9 or len(end_num) != 9:
                wx.MessageBox(
                    "Student numbers must be exactly 9 digits.",
                    "Invalid Input",
                    wx.OK | wx.ICON_WARNING,
                )
                return

            start = int(start_num)
            end = int(end_num)

            if start > end:
                wx.MessageBox(
                    "Start number must be less than or equal to end number.",
                    "Invalid Range",
                    wx.OK | wx.ICON_WARNING,
                )
                return

            if end - start > 10000:
                wx.MessageBox(
                    "Range is too large. Maximum 10,000 students at a time.",
                    "Range Too Large",
                    wx.OK | wx.ICON_WARNING,
                )
                return

            generated_numbers = []

            for num in range(start, end + 1):
                generated_numbers.append(str(num).zfill(9))

            current_text = self.student_list.GetValue().strip()
            if current_text:
                existing_numbers = [
                    line.strip() for line in current_text.split("\n") if line.strip()
                ]
                all_numbers = list(set(existing_numbers + generated_numbers))
                all_numbers.sort()
                self.student_list.SetValue("\n".join(all_numbers))
            else:
                self.student_list.SetValue("\n".join(generated_numbers))

        except Exception as e:
            wx.MessageBox(
                f"Error generating range: {str(e)}",
                "Error",
                wx.OK | wx.ICON_ERROR,
            )

    def on_student_list_changed(self, event):
        valid_numbers = self.get_student_numbers()
        count = len(valid_numbers)
        self.status_text.SetLabel(f"{count} Students to import")
        self.update_import_button_state()

    def on_clear(self, event):
        self.student_list.SetValue("")
        self.range_from.SetValue("")
        self.range_to.SetValue("")

    def get_student_numbers(self):
        text = self.student_list.GetValue().strip()
        if not text:
            return []

        import re

        tokens = re.split(r"[\s\n]+", text)
        numbers = [
            token for token in tokens if token and len(token) == 9 and token.isdigit()
        ]
        return numbers

    def get_import_options(self):
        return {
            "student_info": self.student_info_checkbox.GetValue(),
            "personal_info": self.personal_info_checkbox.GetValue(),
            "education_history": self.education_history_checkbox.GetValue(),
            "enrollment_data": self.enrollment_data_checkbox.GetValue(),
        }

    def on_select_all_checkbox(self, event):
        is_checked = self.select_all_checkbox.GetValue()
        self.student_info_checkbox.SetValue(is_checked)
        self.personal_info_checkbox.SetValue(is_checked)
        self.education_history_checkbox.SetValue(is_checked)
        self.enrollment_data_checkbox.SetValue(is_checked)
        self.update_import_button_state()

    def on_data_checkbox_changed(self, event):
        all_checked = all([
            self.student_info_checkbox.GetValue(),
            self.personal_info_checkbox.GetValue(),
            self.education_history_checkbox.GetValue(),
            self.enrollment_data_checkbox.GetValue(),
        ])
        any_checked = any([
            self.student_info_checkbox.GetValue(),
            self.personal_info_checkbox.GetValue(),
            self.education_history_checkbox.GetValue(),
            self.enrollment_data_checkbox.GetValue(),
        ])

        if all_checked:
            self.select_all_checkbox.Set3StateValue(wx.CHK_CHECKED)
        elif any_checked:
            self.select_all_checkbox.Set3StateValue(wx.CHK_UNDETERMINED)
        else:
            self.select_all_checkbox.Set3StateValue(wx.CHK_UNCHECKED)

        self.update_import_button_state()

    def update_import_button_state(self):
        has_students = len(self.get_student_numbers()) > 0
        has_checkboxes = any([
            self.student_info_checkbox.GetValue(),
            self.personal_info_checkbox.GetValue(),
            self.education_history_checkbox.GetValue(),
            self.enrollment_data_checkbox.GetValue(),
        ])
        self.import_button.Enable(has_students and has_checkboxes)
