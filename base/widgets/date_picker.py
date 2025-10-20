from datetime import date, datetime

import wx
import wx.adv


class DatePickerCtrl(wx.Panel):
    """
    Custom date picker component that displays a calendar for date selection
    and shows the selected date in YYYY-MM-DD format.
    """

    def __init__(self, parent, value="", size=wx.DefaultSize):
        super().__init__(parent, size=size)

        self.selected_date = None
        self.init_ui(value)

    def init_ui(self, value):
        sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Date display text control (read-only)
        self.date_text = wx.TextCtrl(
            self, value=value, style=wx.TE_READONLY | wx.TE_CENTER
        )
        sizer.Add(self.date_text, 1, wx.EXPAND | wx.RIGHT, 5)

        # Button to open calendar
        self.picker_btn = wx.Button(self, label="📅", size=wx.Size(35, 25))
        self.picker_btn.Bind(wx.EVT_BUTTON, self.on_picker_click)
        sizer.Add(self.picker_btn, 0, wx.EXPAND)

        self.SetSizer(sizer)

        # Parse initial value if provided
        if value:
            try:
                if isinstance(value, str):
                    normalized = value.replace("Z", "+00:00")
                    dt = datetime.fromisoformat(normalized)
                    self.selected_date = dt.date()
                else:
                    self.selected_date = (
                        value.date() if hasattr(value, "date") else value
                    )
            except (ValueError, AttributeError):
                pass

    def on_picker_click(self, event):
        dlg = DatePickerDialog(self, self.selected_date)
        if dlg.ShowModal() == wx.ID_OK:
            selected_date = dlg.GetValue()
            if selected_date:
                self.selected_date = selected_date
                date_str = selected_date.strftime("%Y-%m-%d")
                self.date_text.SetValue(date_str)
        dlg.Destroy()

    def GetValue(self):
        """Returns the selected date as YYYY-MM-DD string, or empty string if not set."""
        date_str = self.date_text.GetValue().strip()
        return date_str

    def SetValue(self, value):
        """Set the date value. Accepts string (YYYY-MM-DD) or date object."""
        if not value:
            self.date_text.SetValue("")
            self.selected_date = None
            return

        try:
            if isinstance(value, str):
                normalized = value.replace("Z", "+00:00")
                dt = datetime.fromisoformat(normalized)
                self.selected_date = dt.date()
                self.date_text.SetValue(dt.strftime("%Y-%m-%d"))
            else:
                self.selected_date = value.date() if hasattr(value, "date") else value
                self.date_text.SetValue(self.selected_date.strftime("%Y-%m-%d"))
        except (ValueError, AttributeError):
            self.date_text.SetValue("")
            self.selected_date = None

    def Clear(self):
        """Clear the selected date."""
        self.date_text.SetValue("")
        self.selected_date = None


class DatePickerDialog(wx.Dialog):
    """Dialog containing a calendar for date selection."""

    def __init__(self, parent, initial_date=None):
        super().__init__(
            parent,
            title="Select Date",
            style=wx.DEFAULT_DIALOG_STYLE,
            size=wx.Size(350, 320),
        )

        self.selected_date = initial_date
        self.init_ui(initial_date)

    def init_ui(self, initial_date):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Calendar control
        self.calendar = wx.adv.CalendarCtrl(panel)

        if initial_date:
            wx_date = wx.DateTime(
                initial_date.day, initial_date.month - 1, initial_date.year
            )
            self.calendar.SetDate(wx_date)

        self.calendar.Bind(wx.adv.EVT_CALENDAR_SEL_CHANGED, self.on_date_selected)
        sizer.Add(self.calendar, 1, wx.ALL | wx.EXPAND, 10)

        # Selected date display
        date_info_sizer = wx.BoxSizer(wx.HORIZONTAL)
        date_info_sizer.Add(
            wx.StaticText(panel, label="Selected:"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        self.selected_date_text = wx.StaticText(panel, label="")
        date_info_sizer.Add(self.selected_date_text, 1, wx.EXPAND)
        sizer.Add(date_info_sizer, 0, wx.ALL | wx.EXPAND, 10)

        # Buttons
        button_sizer = wx.StdDialogButtonSizer()
        ok_btn = wx.Button(panel, wx.ID_OK, "Select")
        ok_btn.Bind(wx.EVT_BUTTON, self.on_ok)
        button_sizer.AddButton(ok_btn)

        cancel_btn = wx.Button(panel, wx.ID_CANCEL, "Cancel")
        button_sizer.AddButton(cancel_btn)
        button_sizer.Realize()

        sizer.Add(button_sizer, 0, wx.ALL | wx.ALIGN_RIGHT, 10)

        panel.SetSizer(sizer)
        self.update_selected_date_display()

    def on_date_selected(self, event):
        self.update_selected_date_display()

    def update_selected_date_display(self):
        wx_date = self.calendar.GetDate()
        self.selected_date = date(
            wx_date.GetYear(), wx_date.GetMonth() + 1, wx_date.GetDay()
        )
        date_str = f"{self.selected_date.year:04d}-{self.selected_date.month:02d}-{self.selected_date.day:02d}"
        self.selected_date_text.SetLabel(date_str)

    def on_ok(self, event):
        event.Skip()

    def GetValue(self):
        """Returns the selected date as a Python date object."""
        return self.selected_date
