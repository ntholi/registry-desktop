from datetime import datetime

import wx


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

        form_sizer = wx.FlexGridSizer(rows=5, cols=2, vgap=10, hgap=10)
        form_sizer.AddGrowableCol(1)

        form_sizer.Add(
            wx.StaticText(panel, label="Student Number:"),
            0,
            wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL,
        )
        student_no_text = wx.StaticText(
            panel, label=str(self.student_data.get("std_no", ""))
        )
        form_sizer.Add(student_no_text, 0, wx.EXPAND)

        form_sizer.Add(
            wx.StaticText(panel, label="Name:"),
            0,
            wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL,
        )
        self.name_input = wx.TextCtrl(
            panel, value=self.student_data.get("name", "") or ""
        )
        form_sizer.Add(self.name_input, 0, wx.EXPAND)

        form_sizer.Add(
            wx.StaticText(panel, label="Gender:"),
            0,
            wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL,
        )
        gender_panel = wx.Panel(panel)
        gender_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.gender_male = wx.RadioButton(gender_panel, label="Male")
        self.gender_female = wx.RadioButton(gender_panel, label="Female")
        gender_sizer.Add(self.gender_male, 0, wx.RIGHT, 20)
        gender_sizer.Add(self.gender_female, 0)
        gender_panel.SetSizer(gender_sizer)

        gender_value = self.student_data.get("gender", "").strip().lower()
        if gender_value == "male":
            self.gender_male.SetValue(True)
        elif gender_value == "female":
            self.gender_female.SetValue(True)

        form_sizer.Add(gender_panel, 0, wx.EXPAND)

        form_sizer.Add(
            wx.StaticText(panel, label="Date of Birth (YYYY-MM-DD):"),
            0,
            wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL,
        )
        date_of_birth = self.student_data.get("date_of_birth")
        dob_value = ""
        if isinstance(date_of_birth, str):
            normalized_dob = date_of_birth.replace("Z", "+00:00")
            try:
                dob_value = datetime.fromisoformat(normalized_dob).strftime("%Y-%m-%d")
            except ValueError:
                dob_value = date_of_birth
        elif date_of_birth:
            dob_value = date_of_birth.strftime("%Y-%m-%d")
        self.dob_input = wx.TextCtrl(panel, value=dob_value)
        form_sizer.Add(self.dob_input, 0, wx.EXPAND)

        form_sizer.Add(
            wx.StaticText(panel, label="Phone Number:"),
            0,
            wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL,
        )
        self.phone_input = wx.TextCtrl(
            panel,
            value=self.student_data.get("phone1", "") or "",
        )
        form_sizer.Add(self.phone_input, 0, wx.EXPAND)

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
        name = self.name_input.GetValue().strip()
        dob_value = self.dob_input.GetValue().strip()
        phone = self.phone_input.GetValue().strip()

        if not name:
            wx.MessageBox(
                "Name cannot be empty", "Validation Error", wx.OK | wx.ICON_WARNING
            )
            return

        if (
            phone
            and not phone.replace("+", "")
            .replace("-", "")
            .replace(" ", "")
            .replace("(", "")
            .replace(")", "")
            .isdigit()
        ):
            wx.MessageBox(
                "Please enter a valid phone number",
                "Validation Error",
                wx.OK | wx.ICON_WARNING,
            )
            return

        if dob_value:
            try:
                datetime.strptime(dob_value, "%Y-%m-%d")
            except ValueError:
                wx.MessageBox(
                    "Date of Birth must be in YYYY-MM-DD format",
                    "Validation Error",
                    wx.OK | wx.ICON_WARNING,
                )
                return

        event.Skip()

    def get_updated_data(self):
        dob_value = self.dob_input.GetValue().strip()

        if self.gender_male.GetValue():
            gender = "Male"
        elif self.gender_female.GetValue():
            gender = "Female"
        else:
            gender = ""

        return {
            "std_no": self.student_data.get("std_no"),
            "name": self.name_input.GetValue().strip(),
            "gender": gender,
            "date_of_birth": dob_value,
            "phone1": self.phone_input.GetValue().strip(),
        }
