import wx

from base.runtime_config import (
    CountryConfig,
    get_available_countries,
    get_country_config,
)


class CountrySelectionDialog(wx.Dialog):
    def __init__(self, parent: wx.Window | None, selected_country_code: str) -> None:
        super().__init__(parent, title="Select Configuration")

        self._countries = get_available_countries()
        self._country_index = {
            config.code: index for index, config in enumerate(self._countries)
        }

        panel = wx.Panel(self)
        dialog_sizer = wx.BoxSizer(wx.VERTICAL)
        panel_sizer = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(panel, label="Choose a country configuration")
        title_font = title.GetFont()
        title_font.PointSize = 12
        title_font = title_font.Bold()
        title.SetFont(title_font)
        panel_sizer.Add(title, 0, wx.LEFT | wx.TOP | wx.RIGHT, 20)

        description = wx.StaticText(
            panel,
            label=(
                "This selection controls the CMS site, the database name, and the "
                "window label for this session."
            ),
        )
        description.Wrap(420)
        panel_sizer.Add(description, 0, wx.ALL, 20)

        self.country_choice = wx.RadioBox(
            panel,
            label="Country",
            choices=[config.label for config in self._countries],
            majorDimension=1,
            style=wx.RA_SPECIFY_ROWS,
        )
        self.country_choice.SetSelection(
            self._country_index.get(
                get_country_config(selected_country_code).code,
                0,
            )
        )
        self.country_choice.Bind(wx.EVT_RADIOBOX, self._on_country_changed)
        panel_sizer.Add(self.country_choice, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 20)

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

        panel_sizer.Add(details, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 20)

        button_sizer = self.CreateSeparatedButtonSizer(wx.OK | wx.CANCEL)
        ok_button = self.FindWindow(wx.ID_OK)
        if isinstance(ok_button, wx.Button):
            ok_button.SetLabel("Continue")
            ok_button.SetDefault()

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

        self._refresh_details()

    def _on_country_changed(self, _event: wx.CommandEvent) -> None:
        self._refresh_details()

    def _refresh_details(self) -> None:
        selected = self.get_selected_country_config()
        self.cms_value.SetLabel(selected.cms_base_url)
        self.database_value.SetLabel(selected.database_name)
        self.Layout()
        self.Fit()

    def get_selected_country_config(self) -> CountryConfig:
        return self._countries[self.country_choice.GetSelection()]

    def get_selected_country_code(self) -> str:
        return self.get_selected_country_config().code
