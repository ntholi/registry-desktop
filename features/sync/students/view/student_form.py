from datetime import datetime

import wx
import wx.adv


class StudentFormDialog(wx.Dialog):
    def __init__(self, student_data, parent=None, status_bar=None):
        super().__init__(
            parent,
            title=f"Update Student: {student_data.get('std_no', '')}",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self.student_data = student_data
        self.status_bar = status_bar
        self.SetSize(wx.Size(450, 300))
        self.init_ui()

    def init_ui(self):
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Form fields
        form_sizer = wx.FlexGridSizer(rows=5, cols=2, vgap=10, hgap=10)
        form_sizer.AddGrowableCol(1)

        # Student Number (read-only)
        form_sizer.Add(
            wx.StaticText(panel, label="Student Number:"),
            0,
            wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL,
        )
        student_no_text = wx.StaticText(
            panel, label=str(self.student_data.get("std_no", ""))
        )
        form_sizer.Add(student_no_text, 0, wx.EXPAND)

        # Name
        form_sizer.Add(
            wx.StaticText(panel, label="Name:"),
            0,
            wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL,
        )
        self.name_input = wx.TextCtrl(
            panel, value=self.student_data.get("name", "") or ""
        )
        form_sizer.Add(self.name_input, 0, wx.EXPAND)

        # Gender
        form_sizer.Add(
            wx.StaticText(panel, label="Gender:"),
            0,
            wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL,
        )
        self.gender_input = wx.TextCtrl(
            panel, value=self.student_data.get("gender", "") or ""
        )
        form_sizer.Add(self.gender_input, 0, wx.EXPAND)

        # Date of Birth
        form_sizer.Add(
            wx.StaticText(panel, label="Date of Birth:"),
            0,
            wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL,
        )
        self.dob_input = wx.adv.DatePickerCtrl(
            panel, style=wx.adv.DP_DROPDOWN | wx.adv.DP_SHOWCENTURY
        )
        date_of_birth = self.student_data.get("date_of_birth")
        if date_of_birth:
            if isinstance(date_of_birth, str):
                dt = datetime.fromisoformat(date_of_birth)
            else:
                dt = date_of_birth
            self.dob_input.SetValue(wx.DateTime.FromDMY(dt.day, dt.month - 1, dt.year))
        form_sizer.Add(self.dob_input, 0, wx.EXPAND)

        # Email
        form_sizer.Add(
            wx.StaticText(panel, label="Email:"),
            0,
            wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL,
        )
        self.email_input = wx.TextCtrl(
            panel,
            value=self.student_data.get("email", "") or "",
        )
        form_sizer.Add(self.email_input, 0, wx.EXPAND)

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
        name = self.name_input.GetValue().strip()
        gender = self.gender_input.GetValue().strip()
        email = self.email_input.GetValue().strip()

        if not name:
            wx.MessageBox(
                "Name cannot be empty", "Validation Error", wx.OK | wx.ICON_WARNING
            )
            return

        if email and "@" not in email:
            wx.MessageBox(
                "Please enter a valid email",
                "Validation Error",
                wx.OK | wx.ICON_WARNING,
            )
            return

        event.Skip()

    def get_updated_data(self):
        wx_date = self.dob_input.GetValue()
        dob = datetime(
            wx_date.GetYear(), wx_date.GetMonth() + 1, wx_date.GetDay()
        ).date()

        return {
            "std_no": self.student_data.get("std_no"),
            "name": self.name_input.GetValue().strip(),
            "gender": self.gender_input.GetValue().strip(),
            "date_of_birth": dob,
            "email": self.email_input.GetValue().strip(),
        }
