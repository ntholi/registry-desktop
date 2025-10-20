import wx

from .repository import StructureRepository


class StructureDetailPanel(wx.Panel):
    def __init__(self, parent, repository):
        super().__init__(parent)
        self.repository = repository
        self.selected_structure_id = None

        self.init_ui()

    def init_ui(self):
        sizer = wx.BoxSizer(wx.VERTICAL)

        self.detail_title = wx.StaticText(self, label="Structure Details")
        font = self.detail_title.GetFont()
        font.PointSize = 14
        font = font.Bold()
        self.detail_title.SetFont(font)
        sizer.Add(self.detail_title, 0, wx.BOTTOM, 10)

        self.detail_info = wx.StaticText(
            self, label="Select a structure to view details"
        )
        sizer.Add(self.detail_info, 0, wx.BOTTOM, 20)

        line = wx.StaticLine(self)
        sizer.Add(line, 0, wx.EXPAND | wx.BOTTOM, 15)

        self.semesters_list = wx.ListCtrl(
            self, style=wx.LC_REPORT | wx.BORDER_SIMPLE | wx.LC_SINGLE_SEL
        )
        self.semesters_list.AppendColumn("Semester", width=200)
        self.semesters_list.AppendColumn("Credits", width=80)
        self.semesters_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_semester_selected)
        sizer.Add(self.semesters_list, 4, wx.EXPAND | wx.BOTTOM, 15)

        modules_label = wx.StaticText(self, label="Modules")
        font = modules_label.GetFont()
        font.PointSize = 11
        font = font.Bold()
        modules_label.SetFont(font)
        sizer.Add(modules_label, 0, wx.BOTTOM, 5)

        self.modules_list = wx.ListCtrl(self, style=wx.LC_REPORT | wx.BORDER_SIMPLE)
        self.modules_list.AppendColumn("Code", width=100)
        self.modules_list.AppendColumn("Name", width=250)
        self.modules_list.AppendColumn("Type", width=100)
        self.modules_list.AppendColumn("Credits", width=70)
        sizer.Add(self.modules_list, 5, wx.EXPAND)

        self.SetSizer(sizer)

    def load_structure_details(self, structure_id, code, desc, program):
        try:
            self.selected_structure_id = structure_id
            self.detail_title.SetLabel(f"Structure: {code}")
            info_text = f"{desc}\n{program}"
            self.detail_info.SetLabel(info_text)

            semesters = self.repository.get_structure_semesters(structure_id)
            self.semesters_list.DeleteAllItems()

            for row, semester in enumerate(semesters):
                index = self.semesters_list.InsertItem(row, semester.name)
                self.semesters_list.SetItem(index, 1, f"{semester.total_credits:.1f}")
                self.semesters_list.SetItemData(index, semester.id)

            self.modules_list.DeleteAllItems()

            self.Layout()

        except Exception as e:
            print(f"Error loading structure details: {str(e)}")

    def on_semester_selected(self, event):
        item = event.GetIndex()
        semester_id = self.semesters_list.GetItemData(item)
        self.load_semester_modules(semester_id)

    def load_semester_modules(self, semester_id):
        try:
            modules = self.repository.get_semester_modules(semester_id)
            self.modules_list.DeleteAllItems()

            for row, module in enumerate(modules):
                if module.hidden:
                    continue

                index = self.modules_list.InsertItem(row, module.module_code)
                self.modules_list.SetItem(index, 1, module.module_name)
                self.modules_list.SetItem(index, 2, module.type)
                self.modules_list.SetItem(index, 3, f"{module.credits:.1f}")

            self.Layout()

        except Exception as e:
            print(f"Error loading semester modules: {str(e)}")

    def clear(self):
        self.selected_structure_id = None
        self.detail_title.SetLabel("Structure Details")
        self.detail_info.SetLabel("Select a structure to view details")
        self.semesters_list.DeleteAllItems()
        self.modules_list.DeleteAllItems()
        self.Layout()
