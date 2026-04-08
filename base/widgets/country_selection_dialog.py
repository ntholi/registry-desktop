import wx

from base.runtime_config import CountryConfig, get_app_settings, get_available_countries


class CountrySelectionDialog(wx.Dialog):
    def __init__(
        self, parent: wx.Window | None, selected_country_code: str | None = None
    ) -> None:
        super().__init__(parent, title="Select Configuration")

        settings = get_app_settings()
        self._countries = get_available_countries()
        self._country_index = {
            config.code: index for index, config in enumerate(self._countries)
        }

        panel = wx.Panel(self)
        dialog_sizer = wx.BoxSizer(wx.VERTICAL)
        panel_sizer = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(panel, label="Choose a country and database connection")
        title_font = title.GetFont()
        title_font.PointSize = 12
        title_font = title_font.Bold()
        title.SetFont(title_font)
        panel_sizer.Add(title, 0, wx.LEFT | wx.TOP | wx.RIGHT, 20)

        description = wx.StaticText(
            panel,
            label=(
                "This selection controls the CMS site, the database name, the saved "
                "connection details, and the window label for future sessions."
            ),
        )
        description.Wrap(500)
        panel_sizer.Add(description, 0, wx.ALL, 20)

        country_box = wx.StaticBoxSizer(wx.VERTICAL, panel, "Country configuration")
        self.country_choice = wx.ListBox(
            panel,
            choices=[config.label for config in self._countries],
            size=wx.Size(250, 110),
        )
        initial_country_code = (
            (selected_country_code or settings.country_code or "").strip().lower()
        )
        initial_selection = self._country_index.get(initial_country_code, wx.NOT_FOUND)
        if initial_selection != wx.NOT_FOUND:
            self.country_choice.SetSelection(initial_selection)
        self.country_choice.Bind(wx.EVT_LISTBOX, self._on_country_changed)
        country_box.Add(self.country_choice, 0, wx.EXPAND | wx.ALL, 12)

        details = wx.FlexGridSizer(2, 2, 10, 12)
        details.AddGrowableCol(1, 1)

        details.Add(wx.StaticText(panel, label="CMS"), 0, wx.ALIGN_TOP)
        self.cms_value = wx.StaticText(panel, label="")
        self.cms_value.Wrap(320)
        details.Add(self.cms_value, 1, wx.EXPAND)

        details.Add(wx.StaticText(panel, label="Database"), 0, wx.ALIGN_TOP)
        self.database_value = wx.StaticText(panel, label="")
        self.database_value.Wrap(320)
        details.Add(self.database_value, 1, wx.EXPAND)

        country_box.Add(details, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)
        panel_sizer.Add(country_box, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 20)

        connection_box = wx.StaticBoxSizer(wx.VERTICAL, panel, "Database connection")
        connection_description = wx.StaticText(
            panel,
            label="The saved host, port, user, and password will be reused the next time the app starts.",
        )
        connection_description.Wrap(500)
        connection_box.Add(connection_description, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)

        connection_form = wx.FlexGridSizer(4, 2, 10, 12)
        connection_form.AddGrowableCol(1, 1)

        connection_form.Add(
            wx.StaticText(panel, label="Host / URL"), 0, wx.ALIGN_CENTER_VERTICAL
        )
        self.host_ctrl = wx.TextCtrl(panel, value=settings.database_host)
        connection_form.Add(self.host_ctrl, 1, wx.EXPAND)

        connection_form.Add(
            wx.StaticText(panel, label="Port"), 0, wx.ALIGN_CENTER_VERTICAL
        )
        self.port_ctrl = wx.TextCtrl(panel, value=str(settings.database_port))
        connection_form.Add(self.port_ctrl, 1, wx.EXPAND)

        connection_form.Add(
            wx.StaticText(panel, label="User"), 0, wx.ALIGN_CENTER_VERTICAL
        )
        self.user_ctrl = wx.TextCtrl(panel, value=settings.database_user)
        connection_form.Add(self.user_ctrl, 1, wx.EXPAND)

        connection_form.Add(
            wx.StaticText(panel, label="Password"), 0, wx.ALIGN_CENTER_VERTICAL
        )
        self.password_ctrl = wx.TextCtrl(
            panel,
            value=settings.database_password,
            style=wx.TE_PASSWORD,
        )
        connection_form.Add(self.password_ctrl, 1, wx.EXPAND)

        connection_box.Add(connection_form, 0, wx.ALL | wx.EXPAND, 12)
        panel_sizer.Add(
            connection_box, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 20
        )

        self.validation_message = wx.StaticText(panel, label="")
        panel_sizer.Add(
            self.validation_message,
            0,
            wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND,
            20,
        )

        button_sizer = self.CreateSeparatedButtonSizer(wx.OK | wx.CANCEL)
        ok_button = self.FindWindow(wx.ID_OK)
        if isinstance(ok_button, wx.Button):
            ok_button.SetLabel("Continue")
            ok_button.SetDefault()
            self.ok_button = ok_button
        else:
            self.ok_button = None

        self.host_ctrl.Bind(wx.EVT_TEXT, self._on_form_changed)
        self.port_ctrl.Bind(wx.EVT_TEXT, self._on_form_changed)
        self.user_ctrl.Bind(wx.EVT_TEXT, self._on_form_changed)
        self.password_ctrl.Bind(wx.EVT_TEXT, self._on_form_changed)

        panel.SetSizer(panel_sizer)
        dialog_sizer.Add(panel, 1, wx.EXPAND)
        if button_sizer:
            dialog_sizer.Add(
                button_sizer,
                0,
                wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND,
                12,
            )
        self.SetSizerAndFit(dialog_sizer)
        self.CentreOnScreen()

        self._refresh_dialog_state()

    def _on_country_changed(self, _event: wx.CommandEvent) -> None:
        self._refresh_dialog_state()

    def _on_form_changed(self, _event: wx.CommandEvent) -> None:
        self._refresh_dialog_state()

    def _refresh_dialog_state(self) -> None:
        selected = self.get_selected_country_config()
        if selected is None:
            self.cms_value.SetLabel("")
            self.database_value.SetLabel("")
        else:
            self.cms_value.SetLabel(selected.cms_base_url)
            self.database_value.SetLabel(selected.database_name)

        validation_message = self._get_validation_message(selected)
        self.validation_message.SetLabel(validation_message)

        if self.ok_button is not None:
            self.ok_button.Enable(validation_message == "")

        self.Layout()

    def _get_validation_message(self, selected: CountryConfig | None = None) -> str:
        active_country = selected or self.get_selected_country_config()
        if active_country is None:
            return "Select a country to continue."
        if not self.host_ctrl.GetValue().strip():
            return "Enter the database host or server address."
        if self._get_port_value() is None:
            return "Enter a valid port from 1 to 65535."
        if not self.user_ctrl.GetValue().strip():
            return "Enter the database user."
        return ""

    def _get_port_value(self) -> int | None:
        raw_value = self.port_ctrl.GetValue().strip()
        if not raw_value:
            return None

        try:
            port = int(raw_value)
        except ValueError:
            return None

        if 1 <= port <= 65535:
            return port

        return None

    def get_selected_country_config(self) -> CountryConfig | None:
        selection = self.country_choice.GetSelection()
        if selection == wx.NOT_FOUND:
            return None
        return self._countries[selection]

    def get_selected_country_code(self) -> str | None:
        selected = self.get_selected_country_config()
        if selected is None:
            return None
        return selected.code

    def get_database_host(self) -> str:
        return self.host_ctrl.GetValue().strip()

    def get_database_port(self) -> int:
        port = self._get_port_value()
        if port is None:
            raise ValueError("Invalid database port")
        return port

    def get_database_user(self) -> str:
        return self.user_ctrl.GetValue().strip()

    def get_database_password(self) -> str:
        return self.password_ctrl.GetValue()
