import wx

from .repository import ApprovedEnrollmentRepository


class RegistrationDetailPanel(wx.Panel):
    def __init__(self, parent, on_close_callback, status_bar=None):
        super().__init__(parent)
        self.on_close_callback = on_close_callback
        self.status_bar = status_bar
        self.repository = ApprovedEnrollmentRepository()
        self.current_request_id = None

        self.init_ui()

    def init_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        top_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.info_label = wx.StaticText(self, label="")
        font = self.info_label.GetFont()
        font.PointSize = 10
        font = font.Bold()
        self.info_label.SetFont(font)
        top_sizer.Add(self.info_label, 1, wx.ALIGN_CENTER_VERTICAL)

        self.close_button = wx.Button(self, label="Close", size=wx.Size(80, -1))
        self.close_button.Bind(wx.EVT_BUTTON, self.on_close)
        top_sizer.Add(self.close_button, 0)

        main_sizer.Add(top_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)

        main_sizer.AddSpacer(15)

        line = wx.StaticLine(self, style=wx.LI_HORIZONTAL)
        main_sizer.Add(line, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)

        main_sizer.AddSpacer(15)

        details_grid = wx.FlexGridSizer(rows=0, cols=2, hgap=15, vgap=10)

        label_font = wx.Font(
            9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL
        )
        value_font = wx.Font(
            9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD
        )

        self.student_label = wx.StaticText(self, label="Student:")
        self.student_label.SetFont(label_font)
        self.student_value = wx.StaticText(self, label="")
        self.student_value.SetFont(value_font)
        details_grid.Add(
            self.student_label, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL
        )
        details_grid.Add(
            self.student_value, 0, wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL
        )

        self.sponsor_label = wx.StaticText(self, label="Sponsor:")
        self.sponsor_label.SetFont(label_font)
        self.sponsor_value = wx.StaticText(self, label="")
        self.sponsor_value.SetFont(value_font)
        details_grid.Add(
            self.sponsor_label, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL
        )
        details_grid.Add(
            self.sponsor_value, 0, wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL
        )

        self.term_label = wx.StaticText(self, label="Term:")
        self.term_label.SetFont(label_font)
        self.term_value = wx.StaticText(self, label="")
        self.term_value.SetFont(value_font)
        details_grid.Add(self.term_label, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        details_grid.Add(self.term_value, 0, wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL)

        self.semester_label = wx.StaticText(self, label="Semester:")
        self.semester_label.SetFont(label_font)
        self.semester_value = wx.StaticText(self, label="")
        self.semester_value.SetFont(value_font)
        details_grid.Add(
            self.semester_label, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL
        )
        details_grid.Add(
            self.semester_value, 0, wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL
        )

        self.status_label = wx.StaticText(self, label="Status:")
        self.status_label.SetFont(label_font)
        self.status_value = wx.StaticText(self, label="")
        self.status_value.SetFont(value_font)
        details_grid.Add(
            self.status_label, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL
        )
        details_grid.Add(self.status_value, 0, wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL)

        main_sizer.Add(details_grid, 0, wx.ALL, 20)

        main_sizer.AddSpacer(10)

        modules_header_sizer = wx.BoxSizer(wx.HORIZONTAL)

        modules_label = wx.StaticText(self, label="Requested Modules")
        font = modules_label.GetFont()
        font.PointSize = 10
        font = font.Bold()
        modules_label.SetFont(font)
        modules_header_sizer.Add(modules_label, 0, wx.ALIGN_CENTER_VERTICAL)

        main_sizer.Add(modules_header_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)

        main_sizer.AddSpacer(10)

        self.modules_list = wx.ListCtrl(
            self, style=wx.LC_REPORT | wx.BORDER_SIMPLE, size=wx.Size(-1, 400)
        )
        self.modules_list.AppendColumn("Module Code", width=120)
        self.modules_list.AppendColumn("Module Name", width=250)
        self.modules_list.AppendColumn("Credits", width=80)
        self.modules_list.AppendColumn("Module Status", width=120)
        self.modules_list.AppendColumn("Status", width=100)

        main_sizer.Add(self.modules_list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)

        main_sizer.AddSpacer(20)

        self.SetSizer(main_sizer)

    def load_registration_request(self, request_id: int):
        self.current_request_id = request_id

        try:
            details = self.repository.get_registration_request_details(request_id)

            if not details:
                wx.MessageBox(
                    "Registration request not found",
                    "Error",
                    wx.OK | wx.ICON_ERROR,
                )
                return

            student_info = f"{details['std_no']} - {details['student_name'] or 'N/A'}"
            self.info_label.SetLabel(f"Registration Request #{request_id}")
            self.student_value.SetLabel(student_info)
            self.sponsor_value.SetLabel(details["sponsor_name"] or "N/A")
            self.term_value.SetLabel(details["term_name"] or "N/A")
            self.semester_value.SetLabel(
                f"Semester {details['semester_number']} ({details['semester_status']})"
            )
            self.status_value.SetLabel(details["status"].upper())

            self.load_modules(request_id)

        except Exception as e:
            wx.MessageBox(
                f"Error loading registration request: {str(e)}",
                "Error",
                wx.OK | wx.ICON_ERROR,
            )

    def load_modules(self, request_id: int):
        self.modules_list.DeleteAllItems()

        try:
            modules = self.repository.get_requested_modules(request_id)

            for row, module in enumerate(modules):
                index = self.modules_list.InsertItem(row, module.module_code or "")
                self.modules_list.SetItem(index, 1, module.module_name or "")
                self.modules_list.SetItem(index, 2, str(module.credits or ""))
                self.modules_list.SetItem(index, 3, module.module_status or "")
                self.modules_list.SetItem(index, 4, module.status or "")

        except Exception as e:
            wx.MessageBox(
                f"Error loading modules: {str(e)}", "Error", wx.OK | wx.ICON_ERROR
            )

    def on_close(self, event):
        if self.on_close_callback:
            self.on_close_callback()
