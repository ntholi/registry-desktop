import wx


class AccessDeniedDialog(wx.Dialog):
    def __init__(self, parent, user_role: str):
        super().__init__(parent, title="Access Denied", size=wx.Size(450, 280))

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        icon_text = wx.StaticText(panel, label="⚠️")
        font = icon_text.GetFont()
        font.PointSize = 32
        icon_text.SetFont(font)
        sizer.Add(icon_text, 0, wx.ALIGN_CENTER | wx.TOP, 20)

        title = wx.StaticText(panel, label="Access Denied")
        font = title.GetFont()
        font.PointSize = 14
        font = font.Bold()
        title.SetFont(font)
        sizer.Add(title, 0, wx.ALIGN_CENTER | wx.TOP, 10)

        message = wx.StaticText(
            panel, label="Only Registry and Admin users can access this application."
        )
        sizer.Add(message, 0, wx.ALIGN_CENTER | wx.TOP, 10)

        role_text = wx.StaticText(panel, label=f"Your role: {user_role}")
        font = role_text.GetFont()
        font = font.Bold()
        role_text.SetFont(font)
        sizer.Add(role_text, 0, wx.ALIGN_CENTER | wx.TOP, 5)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        logout_btn = wx.Button(panel, wx.ID_OK, "Logout")
        logout_btn.SetDefault()
        btn_sizer.Add(logout_btn, 0, wx.RIGHT, 5)

        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.TOP | wx.BOTTOM, 20)

        panel.SetSizer(sizer)

        self.Centre()
