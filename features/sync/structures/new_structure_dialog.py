import wx


class NewStructureDialog(wx.Dialog):
    def __init__(
        self,
        parent: wx.Window,
        *,
        program_name: str,
        default_code: str = "",
        default_desc: str = "",
    ):
        super().__init__(
            parent,
            title="New Structure",
            size=wx.Size(620, 420),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self._program_name = program_name

        self.code_input: wx.TextCtrl
        self.desc_input: wx.TextCtrl
        self.active_checkbox: wx.CheckBox
        self.remark_input: wx.TextCtrl
        self.locked_checkbox: wx.CheckBox

        self._init_ui(default_code=default_code, default_desc=default_desc)
        self.Centre()

    def _init_ui(self, *, default_code: str, default_desc: str) -> None:
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        header = wx.StaticText(self, label="Create a new structure in the CMS")
        font = header.GetFont()
        font.PointSize = 12
        font = font.Bold()
        header.SetFont(font)
        main_sizer.Add(header, 0, wx.ALL, 15)

        program_label = wx.StaticText(self, label=f"Program: {self._program_name}")
        main_sizer.Add(program_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        form_sizer = wx.FlexGridSizer(cols=2, vgap=10, hgap=12)
        form_sizer.AddGrowableCol(1, 1)

        form_sizer.Add(wx.StaticText(self, label="Code"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.code_input = wx.TextCtrl(self)
        self.code_input.SetValue(default_code)
        form_sizer.Add(self.code_input, 1, wx.EXPAND)

        form_sizer.Add(wx.StaticText(self, label="Desc"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.desc_input = wx.TextCtrl(self)
        self.desc_input.SetValue(default_desc)
        form_sizer.Add(self.desc_input, 1, wx.EXPAND)

        form_sizer.Add(
            wx.StaticText(self, label="Active?"),
            0,
            wx.ALIGN_CENTER_VERTICAL,
        )
        self.active_checkbox = wx.CheckBox(self)
        self.active_checkbox.SetValue(True)
        form_sizer.Add(self.active_checkbox, 0)

        form_sizer.Add(
            wx.StaticText(self, label="Structure Locked"),
            0,
            wx.ALIGN_CENTER_VERTICAL,
        )
        self.locked_checkbox = wx.CheckBox(self)
        self.locked_checkbox.SetValue(False)
        form_sizer.Add(self.locked_checkbox, 0)

        form_sizer.Add(wx.StaticText(self, label="Remark"), 0)
        self.remark_input = wx.TextCtrl(self, style=wx.TE_MULTILINE, size=wx.Size(-1, 90))
        form_sizer.Add(self.remark_input, 1, wx.EXPAND)

        main_sizer.Add(form_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)

        main_sizer.AddSpacer(15)

        buttons = wx.BoxSizer(wx.HORIZONTAL)
        buttons.AddStretchSpacer()

        create_btn = wx.Button(self, wx.ID_OK, "Create")
        buttons.Add(create_btn, 0, wx.RIGHT, 10)

        cancel_btn = wx.Button(self, wx.ID_CANCEL, "Cancel")
        buttons.Add(cancel_btn, 0)

        main_sizer.Add(buttons, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        self.SetSizer(main_sizer)

    def get_data(self) -> dict:
        return {
            "code": self.code_input.GetValue().strip(),
            "desc": self.desc_input.GetValue().strip(),
            "active": self.active_checkbox.GetValue(),
            "locked": self.locked_checkbox.GetValue(),
            "remark": self.remark_input.GetValue().strip(),
        }
