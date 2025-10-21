import wx

from .fetch_module_dialog import FetchModuleDialog
from .repository import ModuleRepository
from .service import ModuleSyncService


class ModulesView(wx.Panel):
    def __init__(self, parent, status_bar=None):
        super().__init__(parent)
        self.status_bar = status_bar
        self.current_page = 1
        self.page_size = 30
        self.total_modules = 0
        self.search_query = None
        self.repository = ModuleRepository()
        self.service = ModuleSyncService(self.repository)

        self.init_ui()
        self.load_modules()

    def init_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(self, label="Modules")
        font = title.GetFont()
        font.PointSize = 18
        font = font.Bold()
        title.SetFont(font)
        main_sizer.AddSpacer(20)
        main_sizer.Add(title, 0, wx.LEFT | wx.RIGHT, 40)

        main_sizer.AddSpacer(25)
        line = wx.StaticLine(self)
        main_sizer.Add(line, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 40)

        main_sizer.AddSpacer(20)

        filters_label = wx.StaticText(self, label="Filters")
        font = filters_label.GetFont()
        font.PointSize = 12
        font = font.Bold()
        filters_label.SetFont(font)
        main_sizer.Add(filters_label, 0, wx.LEFT | wx.RIGHT, 40)

        main_sizer.AddSpacer(10)

        filters_sizer = wx.BoxSizer(wx.HORIZONTAL)

        search_label = wx.StaticText(self, label="Search:")
        filters_sizer.Add(search_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)

        self.search_text = wx.TextCtrl(self, size=wx.Size(300, -1))
        self.search_text.Bind(wx.EVT_TEXT, self.on_search_changed)
        filters_sizer.Add(self.search_text, 0, wx.RIGHT, 10)

        filters_sizer.AddStretchSpacer()

        self.fetch_button = wx.Button(self, label="Fetch")
        self.fetch_button.Bind(wx.EVT_BUTTON, self.on_fetch)
        filters_sizer.Add(self.fetch_button, 0, wx.RIGHT, 10)

        self.fetch_all_button = wx.Button(self, label="Fetch All")
        self.fetch_all_button.Bind(wx.EVT_BUTTON, self.on_fetch_all)
        filters_sizer.Add(self.fetch_all_button, 0)

        main_sizer.Add(filters_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 40)

        main_sizer.AddSpacer(15)

        line = wx.StaticLine(self)
        main_sizer.Add(line, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 40)

        main_sizer.AddSpacer(15)

        self.list_ctrl = wx.ListCtrl(self, style=wx.LC_REPORT | wx.BORDER_SIMPLE)
        self.list_ctrl.AppendColumn("Code", width=150)
        self.list_ctrl.AppendColumn("Name", width=400)
        self.list_ctrl.AppendColumn("Status", width=100)
        self.list_ctrl.AppendColumn("Timestamp", width=150)

        self.list_ctrl.Bind(wx.EVT_RIGHT_UP, self.on_list_right_click)

        main_sizer.Add(self.list_ctrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 40)

        main_sizer.AddSpacer(10)

        pagination_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.records_label = wx.StaticText(self, label="")
        pagination_sizer.Add(self.records_label, 0, wx.ALIGN_CENTER_VERTICAL)

        pagination_sizer.AddStretchSpacer()

        self.prev_button = wx.Button(self, label="Previous")
        self.prev_button.Bind(wx.EVT_BUTTON, self.previous_page)
        self.prev_button.Enable(False)
        pagination_sizer.Add(self.prev_button, 0, wx.RIGHT, 15)

        self.page_label = wx.StaticText(self, label="")
        pagination_sizer.Add(
            self.page_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 15
        )

        self.next_button = wx.Button(self, label="Next")
        self.next_button.Bind(wx.EVT_BUTTON, self.next_page)
        pagination_sizer.Add(self.next_button, 0)

        main_sizer.Add(pagination_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 40)

        main_sizer.AddSpacer(40)

        self.SetSizer(main_sizer)

    def on_list_right_click(self, event):
        item, flags, col = self.list_ctrl.HitTestSubItem(event.GetPosition())

        if item == wx.NOT_FOUND:
            return

        cell_value = self.list_ctrl.GetItemText(item, col)
        if not cell_value:
            return

        menu = wx.Menu()
        copy_item = menu.Append(
            wx.ID_ANY,
            f"Copy '{cell_value[:30]}{'...' if len(cell_value) > 30 else ''}'",
        )
        self.Bind(
            wx.EVT_MENU, lambda evt: self._copy_to_clipboard(cell_value), copy_item
        )

        self.PopupMenu(menu)
        menu.Destroy()

    def _copy_to_clipboard(self, text):
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(text))
            wx.TheClipboard.Close()

    def on_search_changed(self, event):
        self.search_query = self.search_text.GetValue().strip() or None
        self.current_page = 1
        self.load_modules()

    def load_modules(self):
        try:
            modules, total = self.repository.fetch_modules(
                search_query=self.search_query,
                page=self.current_page,
                page_size=self.page_size,
            )

            self.total_modules = total
            self.list_ctrl.DeleteAllItems()

            for row, module in enumerate(modules):
                index = self.list_ctrl.InsertItem(row, module.code or "")
                self.list_ctrl.SetItem(index, 1, module.name or "")
                self.list_ctrl.SetItem(index, 2, module.status or "")
                self.list_ctrl.SetItem(index, 3, module.timestamp or "")
                self.list_ctrl.SetItemData(index, module.id)

            self.update_pagination_controls()
            self.update_total_label()

        except Exception as e:
            print(f"Error loading modules: {str(e)}")
            self.list_ctrl.DeleteAllItems()
            self.page_label.SetLabel("No data available")
            self.records_label.SetLabel("")

    def update_total_label(self):
        plural = "s" if self.total_modules != 1 else ""
        self.records_label.SetLabel(f"{self.total_modules} Module{plural}")
        self.Layout()

    def update_pagination_controls(self):
        total_pages = max(
            (self.total_modules + self.page_size - 1) // self.page_size, 1
        )
        self.page_label.SetLabel(f"Page {self.current_page} of {total_pages}")

        self.prev_button.Enable(self.current_page > 1)
        self.next_button.Enable(self.current_page < total_pages)

    def previous_page(self, event):
        if self.current_page > 1:
            self.current_page -= 1
            self.load_modules()

    def next_page(self, event):
        total_pages = (self.total_modules + self.page_size - 1) // self.page_size
        if self.current_page < total_pages:
            self.current_page += 1
            self.load_modules()

    def on_fetch(self, event):
        dialog = FetchModuleDialog(self, self.service, self.status_bar)
        if dialog.ShowModal() == wx.ID_OK:
            self.load_modules()
        dialog.Destroy()

    def on_fetch_all(self, event):
        wx.MessageBox(
            "Fetch All functionality not yet implemented",
            "Coming Soon",
            wx.OK | wx.ICON_INFORMATION,
        )
