import wx

from ..repository import BulkStudentProgramsRepository, StructureOption


class UpdateStructureDialog(wx.Dialog):
    def __init__(
        self,
        selected_count: int,
        program_id: int,
        repository: BulkStudentProgramsRepository,
        parent=None,
    ):
        super().__init__(
            parent,
            title="Update Structure Version",
            size=wx.Size(500, 350),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self.selected_count = selected_count
        self.program_id = program_id
        self.repository = repository
        self.selected_structure: StructureOption | None = None
        self.structures: list[StructureOption] = []

        self.init_ui()
        self.load_structures()
        self.CenterOnParent()

    def init_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        info_label = wx.StaticText(
            self,
            label=f"Select a structure version to apply to {self.selected_count} "
            f"selected student(s):",
        )
        main_sizer.Add(info_label, 0, wx.ALL | wx.EXPAND, 15)

        list_label = wx.StaticText(self, label="Available Versions:")
        font = list_label.GetFont()
        font = font.Bold()
        list_label.SetFont(font)
        main_sizer.Add(list_label, 0, wx.LEFT | wx.RIGHT, 15)

        main_sizer.AddSpacer(5)

        self.structure_list = wx.ListCtrl(
            self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SIMPLE
        )
        self.structure_list.AppendColumn("Version Code", width=150)
        self.structure_list.AppendColumn("Description", width=300)
        self.structure_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_structure_selected)
        self.structure_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.on_structure_double_click)

        main_sizer.Add(self.structure_list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)

        main_sizer.AddSpacer(10)

        details_panel = wx.Panel(self)
        details_sizer = wx.BoxSizer(wx.VERTICAL)

        self.details_label = wx.StaticText(details_panel, label="No version selected")
        details_sizer.Add(self.details_label, 0, wx.ALL, 5)

        details_panel.SetSizer(details_sizer)
        details_panel.SetBackgroundColour(wx.Colour(245, 245, 245))

        main_sizer.Add(details_panel, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)

        main_sizer.AddSpacer(15)

        button_sizer = wx.BoxSizer(wx.HORIZONTAL)

        cancel_btn = wx.Button(self, wx.ID_CANCEL, "Cancel")
        button_sizer.Add(cancel_btn, 0)

        button_sizer.AddSpacer(10)

        self.update_btn = wx.Button(self, wx.ID_OK, "Update")
        self.update_btn.Enable(False)
        button_sizer.Add(self.update_btn, 0)

        main_sizer.Add(button_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 15)

        self.SetSizer(main_sizer)

    def load_structures(self):
        self.structures = self.repository.list_structures_for_program(self.program_id)

        self.structure_list.DeleteAllItems()

        for idx, structure in enumerate(self.structures):
            index = self.structure_list.InsertItem(idx, structure.code)
            self.structure_list.SetItem(index, 1, structure.desc or "")
            self.structure_list.SetItemData(index, idx)

    def on_structure_selected(self, event):
        item_idx = event.GetIndex()
        data_idx = self.structure_list.GetItemData(item_idx)

        if 0 <= data_idx < len(self.structures):
            self.selected_structure = self.structures[data_idx]
            self.details_label.SetLabel(
                f"Selected: {self.selected_structure.code}"
                + (f" - {self.selected_structure.desc}" if self.selected_structure.desc else "")
            )
            self.update_btn.Enable(True)

    def on_structure_double_click(self, event):
        if self.selected_structure:
            self.EndModal(wx.ID_OK)

    def get_selected_structure(self) -> StructureOption | None:
        return self.selected_structure
