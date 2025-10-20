import wx

from .repository import StructureRepository
from .structure_detail_panel import StructureDetailPanel


class StructuresView(wx.Panel):
    def __init__(self, parent, status_bar=None):
        super().__init__(parent)
        self.status_bar = status_bar
        self.current_page = 1
        self.page_size = 30
        self.total_structures = 0
        self.selected_school_id = None
        self.selected_program_id = None
        self.repository = StructureRepository()
        self.selected_structure_id = None

        self.init_ui()
        self.load_filter_options()
        self.load_structures()

    def init_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(self, label="Program Structures")
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

        self.school_filter = wx.Choice(self)
        self.school_filter.Append("All Schools", None)
        self.school_filter.SetSelection(0)
        self.school_filter.Bind(wx.EVT_CHOICE, self.on_school_changed)
        filters_sizer.Add(self.school_filter, 0, wx.RIGHT, 10)

        self.program_filter = wx.Choice(self)
        self.program_filter.Append("All Programs", None)
        self.program_filter.SetSelection(0)
        self.program_filter.Bind(wx.EVT_CHOICE, self.on_filter_changed)
        filters_sizer.Add(self.program_filter, 0, wx.RIGHT, 10)

        filters_sizer.AddStretchSpacer()

        main_sizer.Add(filters_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 40)

        main_sizer.AddSpacer(15)

        line = wx.StaticLine(self)
        main_sizer.Add(line, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 40)

        main_sizer.AddSpacer(15)

        content_sizer = wx.BoxSizer(wx.HORIZONTAL)

        left_panel = wx.Panel(self)
        left_sizer = wx.BoxSizer(wx.VERTICAL)

        self.list_ctrl = wx.ListCtrl(left_panel, style=wx.LC_REPORT | wx.BORDER_SIMPLE)
        self.list_ctrl.AppendColumn("Code", width=120)
        self.list_ctrl.AppendColumn("Description", width=200)
        self.list_ctrl.AppendColumn("School", width=100)
        self.list_ctrl.AppendColumn("Program", width=280)

        self.list_ctrl.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_structure_selected)
        self.list_ctrl.Bind(wx.EVT_RIGHT_UP, self.on_list_right_click)

        left_sizer.Add(self.list_ctrl, 1, wx.EXPAND)

        pagination_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.records_label = wx.StaticText(left_panel, label="")
        pagination_sizer.Add(self.records_label, 0, wx.ALIGN_CENTER_VERTICAL)

        pagination_sizer.AddStretchSpacer()

        self.prev_button = wx.Button(left_panel, label="Previous")
        self.prev_button.Bind(wx.EVT_BUTTON, self.previous_page)
        self.prev_button.Enable(False)
        pagination_sizer.Add(self.prev_button, 0, wx.RIGHT, 15)

        self.page_label = wx.StaticText(left_panel, label="")
        pagination_sizer.Add(
            self.page_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 15
        )

        self.next_button = wx.Button(left_panel, label="Next")
        self.next_button.Bind(wx.EVT_BUTTON, self.next_page)
        pagination_sizer.Add(self.next_button, 0)

        left_sizer.AddSpacer(10)
        left_sizer.Add(pagination_sizer, 0, wx.EXPAND)

        left_panel.SetSizer(left_sizer)
        content_sizer.Add(left_panel, 2, wx.EXPAND | wx.LEFT, 40)

        content_sizer.AddSpacer(20)

        separator = wx.StaticLine(self, style=wx.LI_VERTICAL)
        content_sizer.Add(separator, 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 0)

        content_sizer.AddSpacer(20)

        self.detail_panel = StructureDetailPanel(self, self.repository)
        content_sizer.Add(self.detail_panel, 1, wx.EXPAND | wx.RIGHT, 40)

        main_sizer.Add(content_sizer, 1, wx.EXPAND)

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

    def load_filter_options(self):
        try:
            schools = self.repository.list_active_schools()
            for school in schools:
                self.school_filter.Append(str(school.name), school.id)

            self.load_programs_for_school(None)

        except Exception as e:
            print(f"Error loading filter options: {str(e)}")

    def load_programs_for_school(self, school_id):
        try:
            while self.program_filter.GetCount() > 1:
                self.program_filter.Delete(1)

            programs = self.repository.list_programs(school_id)

            for program in programs:
                self.program_filter.Append(str(program.name), program.id)
        except Exception as e:
            print(f"Error loading programs: {str(e)}")

    def on_school_changed(self, event):
        sel = self.school_filter.GetSelection()
        self.selected_school_id = (
            self.school_filter.GetClientData(sel) if sel != wx.NOT_FOUND else None
        )
        self.load_programs_for_school(self.selected_school_id)
        self.selected_program_id = None
        self.current_page = 1
        self.load_structures()

    def on_filter_changed(self, event):
        sel = self.school_filter.GetSelection()
        self.selected_school_id = (
            self.school_filter.GetClientData(sel) if sel != wx.NOT_FOUND else None
        )

        sel = self.program_filter.GetSelection()
        self.selected_program_id = (
            self.program_filter.GetClientData(sel) if sel != wx.NOT_FOUND else None
        )

        self.current_page = 1
        self.load_structures()

    def load_structures(self):
        try:
            structures, total = self.repository.fetch_structures(
                school_id=self.selected_school_id,
                program_id=self.selected_program_id,
                page=self.current_page,
                page_size=self.page_size,
            )

            self.total_structures = total
            self.list_ctrl.DeleteAllItems()

            for row, structure in enumerate(structures):
                index = self.list_ctrl.InsertItem(row, structure.code or "")
                self.list_ctrl.SetItem(index, 1, structure.desc or "")
                self.list_ctrl.SetItem(index, 2, structure.school_code or "")
                self.list_ctrl.SetItem(index, 3, structure.program_name or "")
                self.list_ctrl.SetItemData(index, structure.id)

            self.update_pagination_controls()
            self.update_total_label()
            self.clear_detail_panel()

        except Exception as e:
            print(f"Error loading structures: {str(e)}")
            self.list_ctrl.DeleteAllItems()
            self.page_label.SetLabel("No data available")
            self.records_label.SetLabel("")
            self.clear_detail_panel()

    def update_total_label(self):
        plural = "s" if self.total_structures != 1 else ""
        self.records_label.SetLabel(f"{self.total_structures} Structure{plural}")
        self.Layout()

    def update_pagination_controls(self):
        total_pages = max(
            (self.total_structures + self.page_size - 1) // self.page_size, 1
        )
        self.page_label.SetLabel(f"Page {self.current_page} of {total_pages}")

        self.prev_button.Enable(self.current_page > 1)
        self.next_button.Enable(self.current_page < total_pages)

    def previous_page(self, event):
        if self.current_page > 1:
            self.current_page -= 1
            self.load_structures()

    def next_page(self, event):
        total_pages = (self.total_structures + self.page_size - 1) // self.page_size
        if self.current_page < total_pages:
            self.current_page += 1
            self.load_structures()

    def on_structure_selected(self, event):
        item = event.GetIndex()
        structure_id = self.list_ctrl.GetItemData(item)
        structure_code = self.list_ctrl.GetItemText(item, 0)
        structure_desc = self.list_ctrl.GetItemText(item, 1)
        structure_program = self.list_ctrl.GetItemText(item, 3)

        self.selected_structure_id = structure_id
        self.detail_panel.load_structure_details(
            structure_id, structure_code, structure_desc, structure_program
        )

    def clear_detail_panel(self):
        self.detail_panel.clear()
