import wx


class UserDetailsDialog(wx.Dialog):
    def __init__(self, parent, user):
        super().__init__(parent, title="User Details", size=wx.Size(450, 300))

        self.user = user

        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        title_label = wx.StaticText(panel, label="Account Information")
        title_font = title_label.GetFont()
        title_font.PointSize += 2
        title_font = title_font.Bold()
        title_label.SetFont(title_font)
        main_sizer.Add(title_label, 0, wx.ALL, 15)

        separator = wx.StaticLine(panel, style=wx.LI_HORIZONTAL)
        main_sizer.Add(separator, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)

        main_sizer.AddSpacer(15)

        details_sizer = wx.FlexGridSizer(4, 2, 10, 15)
        details_sizer.AddGrowableCol(1, 1)

        name_label = wx.StaticText(panel, label="Name:")
        name_font = name_label.GetFont().Bold()
        name_label.SetFont(name_font)
        details_sizer.Add(name_label, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        details_sizer.Add(wx.StaticText(panel, label=user.name or "N/A"), 0, wx.EXPAND)

        email_label = wx.StaticText(panel, label="Email:")
        email_label.SetFont(name_font)
        details_sizer.Add(email_label, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        details_sizer.Add(wx.StaticText(panel, label=user.email or "N/A"), 0, wx.EXPAND)

        role_label = wx.StaticText(panel, label="Role:")
        role_label.SetFont(name_font)
        details_sizer.Add(role_label, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        role_value = user.role.upper() if user.role else "N/A"
        details_sizer.Add(wx.StaticText(panel, label=role_value), 0, wx.EXPAND)

        position_label = wx.StaticText(panel, label="Position:")
        position_label.SetFont(name_font)
        details_sizer.Add(position_label, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        details_sizer.Add(wx.StaticText(panel, label=user.position or "N/A"), 0, wx.EXPAND)

        main_sizer.Add(details_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 30)

        main_sizer.AddStretchSpacer()

        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.AddStretchSpacer()

        close_button = wx.Button(panel, wx.ID_CLOSE, "Close")
        close_button.Bind(wx.EVT_BUTTON, self._on_close)
        button_sizer.Add(close_button, 0, wx.ALL, 10)

        main_sizer.Add(button_sizer, 0, wx.EXPAND)

        panel.SetSizer(main_sizer)

        self.Centre()

    def _on_close(self, event):
        self.EndModal(wx.ID_CLOSE)
