import wx


class NewSemesterDialog(wx.Dialog):
    def __init__(
        self,
        parent: wx.Window,
        *,
        program_name: str,
        structure_code: str,
    ):
        super().__init__(
            parent,
            title="Add Semester",
            size=wx.Size(620, 360),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self._program_name = program_name
        self._structure_code = structure_code

        self.semester_choice: wx.Choice
        self.credits_input: wx.TextCtrl

        self._init_ui()
        self.CenterOnScreen()

    def _init_ui(self) -> None:
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        header = wx.StaticText(self, label="Create a new semester in the CMS")
        font = header.GetFont()
        font.PointSize = 12
        font = font.Bold()
        header.SetFont(font)
        main_sizer.Add(header, 0, wx.ALL, 15)

        main_sizer.Add(
            wx.StaticText(self, label=f"Program: {self._program_name}"),
            0,
            wx.LEFT | wx.RIGHT | wx.BOTTOM,
            10,
        )
        main_sizer.Add(
            wx.StaticText(self, label=f"Version: {self._structure_code}"),
            0,
            wx.LEFT | wx.RIGHT | wx.BOTTOM,
            15,
        )

        form_sizer = wx.FlexGridSizer(cols=2, vgap=10, hgap=12)
        form_sizer.AddGrowableCol(1, 1)

        form_sizer.Add(
            wx.StaticText(self, label="Semester"),
            0,
            wx.ALIGN_CENTER_VERTICAL,
        )

        self.semester_choice = wx.Choice(self)
        for code, label in self._semester_options():
            self.semester_choice.Append(label, code)
        if self.semester_choice.GetCount() > 0:
            self.semester_choice.SetSelection(0)
        form_sizer.Add(self.semester_choice, 1, wx.EXPAND)

        form_sizer.Add(
            wx.StaticText(self, label="Credits"),
            0,
            wx.ALIGN_CENTER_VERTICAL,
        )
        self.credits_input = wx.TextCtrl(self)
        self.credits_input.SetHint("e.g. 18")
        form_sizer.Add(self.credits_input, 1, wx.EXPAND)

        main_sizer.Add(form_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)
        main_sizer.AddSpacer(15)

        buttons = wx.BoxSizer(wx.HORIZONTAL)
        buttons.AddStretchSpacer()

        create_btn = wx.Button(self, wx.ID_OK, "Add")
        create_btn.Bind(wx.EVT_BUTTON, self._on_submit)
        buttons.Add(create_btn, 0, wx.RIGHT, 10)

        cancel_btn = wx.Button(self, wx.ID_CANCEL, "Cancel")
        buttons.Add(cancel_btn, 0)

        main_sizer.Add(buttons, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)
        self.SetSizer(main_sizer)

    def _on_submit(self, event: wx.CommandEvent) -> None:
        if self.semester_choice.GetSelection() == wx.NOT_FOUND:
            wx.MessageBox(
                "Please select a semester.",
                "Validation",
                wx.OK | wx.ICON_WARNING,
            )
            return

        credits_raw = self.credits_input.GetValue().strip()
        if credits_raw:
            try:
                float(credits_raw)
            except ValueError:
                wx.MessageBox(
                    "Credits must be a number.",
                    "Validation",
                    wx.OK | wx.ICON_WARNING,
                )
                return

        event.Skip()

    def get_data(self) -> dict:
        selection = self.semester_choice.GetSelection()
        semester_code = None
        semester_label = None
        if selection != wx.NOT_FOUND:
            semester_code = self.semester_choice.GetClientData(selection)
            semester_label = self.semester_choice.GetString(selection)

        credits_raw = self.credits_input.GetValue().strip()
        credits = float(credits_raw) if credits_raw else None

        return {
            "semester_code": str(semester_code) if semester_code is not None else "",
            "semester_label": str(semester_label) if semester_label is not None else "",
            "credits": credits,
        }

    @staticmethod
    def _semester_options() -> list[tuple[str, str]]:
        return [
            ("", "?"),
            ("01", "01 Year 1 Sem 1"),
            ("02", "02 Year 1 Sem 2"),
            ("03", "03 Year 2 Sem 1"),
            ("04", "04 Year 2 Sem 2"),
            ("05", "05 Year 3 Sem 1"),
            ("06", "06 Year 3 Sem 2"),
            ("07", "07 Year 4 Sem 1"),
            ("08", "08 Year 4 Sem 2"),
            ("09", "09 Year 5 Sem 1"),
            ("10", "10 Year 5 Sem 2"),
            ("11", "11 Year 6 Sem 1"),
            ("12", "12 Year 6 Sem 2"),
            ("B1", "B1 Bridging Semester 1"),
            ("F1", "F1 Foundation Semester 1"),
            ("F2", "F2 Foundation Semester 2"),
        ]
