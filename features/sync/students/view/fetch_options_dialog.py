import wx


class FetchOptionsDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(
            parent,
            title="Fetch Options",
            size=wx.Size(500, 350),
            style=wx.DEFAULT_DIALOG_STYLE,
        )

        self.init_ui()
        self.CenterOnParent()

    def init_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        main_sizer.AddSpacer(15)

        title_label = wx.StaticText(
            self, label="Select the data you want to fetch from the CMS:"
        )
        main_sizer.Add(title_label, 0, wx.LEFT | wx.RIGHT, 15)

        main_sizer.AddSpacer(20)

        options_label = wx.StaticText(self, label="Data to Fetch")
        font = options_label.GetFont()
        font = font.Bold()
        options_label.SetFont(font)
        main_sizer.Add(options_label, 0, wx.LEFT | wx.RIGHT, 15)

        main_sizer.AddSpacer(10)

        select_buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)
        select_all_button = wx.Button(self, label="Select All", size=wx.Size(100, -1))
        select_all_button.Bind(wx.EVT_BUTTON, self.on_select_all)
        select_buttons_sizer.Add(select_all_button, 0, wx.RIGHT, 5)

        select_none_button = wx.Button(self, label="Select None", size=wx.Size(100, -1))
        select_none_button.Bind(wx.EVT_BUTTON, self.on_select_none)
        select_buttons_sizer.Add(select_none_button, 0)

        main_sizer.Add(select_buttons_sizer, 0, wx.LEFT | wx.RIGHT, 15)

        main_sizer.AddSpacer(10)

        checkbox_sizer = wx.BoxSizer(wx.VERTICAL)

        self.student_info_checkbox = wx.CheckBox(
            self, label="Student Info (Name, IC/Passport, Phones, Country, Semester)"
        )
        self.student_info_checkbox.SetValue(True)
        self.student_info_checkbox.Bind(wx.EVT_CHECKBOX, self.on_checkbox_changed)
        checkbox_sizer.Add(self.student_info_checkbox, 0, wx.BOTTOM, 5)

        self.personal_info_checkbox = wx.CheckBox(
            self, label="Personal Info (Date of Birth, Gender, Marital Status, Religion, Race, Nationality, Next of Kin)"
        )
        self.personal_info_checkbox.SetValue(True)
        self.personal_info_checkbox.Bind(wx.EVT_CHECKBOX, self.on_checkbox_changed)
        checkbox_sizer.Add(self.personal_info_checkbox, 0, wx.BOTTOM, 5)

        self.education_history_checkbox = wx.CheckBox(
            self, label="Educational History (Previous schools and qualifications)"
        )
        self.education_history_checkbox.SetValue(True)
        self.education_history_checkbox.Bind(wx.EVT_CHECKBOX, self.on_checkbox_changed)
        checkbox_sizer.Add(self.education_history_checkbox, 0, wx.BOTTOM, 5)

        self.enrollment_data_checkbox = wx.CheckBox(
            self, label="Enrollment Data (Programs, Semesters, Modules, Grades)"
        )
        self.enrollment_data_checkbox.SetValue(True)
        self.enrollment_data_checkbox.Bind(wx.EVT_CHECKBOX, self.on_checkbox_changed)
        checkbox_sizer.Add(self.enrollment_data_checkbox, 0)

        main_sizer.Add(checkbox_sizer, 0, wx.LEFT | wx.RIGHT, 15)

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
        return {
            "student_info": self.student_info_checkbox.GetValue(),
            "personal_info": self.personal_info_checkbox.GetValue(),
            "education_history": self.education_history_checkbox.GetValue(),
            "enrollment_data": self.enrollment_data_checkbox.GetValue(),
        }

    def on_select_all(self, event):
        self.student_info_checkbox.SetValue(True)
        self.personal_info_checkbox.SetValue(True)
        self.education_history_checkbox.SetValue(True)
        self.enrollment_data_checkbox.SetValue(True)
        self.update_fetch_button_state()

    def on_select_none(self, event):
        self.student_info_checkbox.SetValue(False)
        self.personal_info_checkbox.SetValue(False)
        self.education_history_checkbox.SetValue(False)
        self.enrollment_data_checkbox.SetValue(False)
        self.update_fetch_button_state()

    def on_checkbox_changed(self, event):
        self.update_fetch_button_state()

    def update_fetch_button_state(self):
        has_checkboxes = any([
            self.student_info_checkbox.GetValue(),
            self.personal_info_checkbox.GetValue(),
            self.education_history_checkbox.GetValue(),
            self.enrollment_data_checkbox.GetValue(),
        ])
        self.fetch_button.Enable(has_checkboxes)
