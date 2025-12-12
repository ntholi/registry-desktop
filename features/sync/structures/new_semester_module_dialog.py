import wx
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import Module, get_engine
from database.models import ModuleType


class NewSemesterModuleDialog(wx.Dialog):
    def __init__(
        self,
        parent: wx.Window,
        *,
        semester_id: int,
        semester_name: str,
        existing_semester_modules: list,
    ):
        super().__init__(
            parent,
            title="New Semester Module",
            size=wx.Size(760, 620),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self._engine = get_engine()
        self._semester_id = semester_id
        self._semester_name = semester_name
        self._existing_semester_modules = existing_semester_modules

        self._selected_module_id: int | None = None
        self._selected_module_code: str | None = None
        self._selected_module_name: str | None = None

        self.search_input: wx.TextCtrl
        self.results_list: wx.ListCtrl

        self.selected_module_label: wx.StaticText

        self.type_choice: wx.Choice
        self.credits_choice: wx.Choice
        self.optional_checkbox: wx.CheckBox
        self.remark_input: wx.TextCtrl
        self.prereq_choice: wx.Choice

        self._init_ui()
        self.CenterOnScreen()

    def _init_ui(self) -> None:
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        header = wx.StaticText(self, label="Add a new module to this semester")
        font = header.GetFont()
        font.PointSize = 12
        font = font.Bold()
        header.SetFont(font)
        main_sizer.Add(header, 0, wx.ALL, 15)

        main_sizer.Add(
            wx.StaticText(self, label=f"Semester: {self._semester_name} (ID: {self._semester_id})"),
            0,
            wx.LEFT | wx.RIGHT | wx.BOTTOM,
            10,
        )

        main_sizer.Add(wx.StaticLine(self), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)
        main_sizer.AddSpacer(10)

        search_row = wx.BoxSizer(wx.HORIZONTAL)
        search_row.Add(
            wx.StaticText(self, label="Search module:"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            8,
        )

        self.search_input = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
        self.search_input.SetHint("Enter module code or name...")
        self.search_input.Bind(wx.EVT_TEXT_ENTER, self._on_search)
        search_row.Add(self.search_input, 1, wx.EXPAND | wx.RIGHT, 8)

        search_btn = wx.Button(self, label="Search")
        search_btn.Bind(wx.EVT_BUTTON, self._on_search)
        search_row.Add(search_btn, 0)

        main_sizer.Add(search_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)
        main_sizer.AddSpacer(10)

        self.results_list = wx.ListCtrl(
            self,
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SIMPLE,
            size=wx.Size(-1, 220),
        )
        self.results_list.AppendColumn("Code", width=140)
        self.results_list.AppendColumn("Name", width=460)
        self.results_list.AppendColumn("Status", width=100)
        self.results_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_result_selected)
        self.results_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._on_result_activated)
        main_sizer.Add(self.results_list, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)

        main_sizer.AddSpacer(10)

        self.selected_module_label = wx.StaticText(self, label="Selected module: (none)")
        font = self.selected_module_label.GetFont()
        font = font.Bold()
        self.selected_module_label.SetFont(font)
        main_sizer.Add(self.selected_module_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        main_sizer.Add(wx.StaticLine(self), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)
        main_sizer.AddSpacer(15)

        form_sizer = wx.FlexGridSizer(cols=2, vgap=10, hgap=12)
        form_sizer.AddGrowableCol(1, 1)

        form_sizer.Add(wx.StaticText(self, label="Type"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.type_choice = wx.Choice(self)
        for t in self._type_options():
            self.type_choice.Append(t)
        if self.type_choice.GetCount() > 0:
            self.type_choice.SetSelection(0)
        form_sizer.Add(self.type_choice, 1, wx.EXPAND)

        form_sizer.Add(wx.StaticText(self, label="Credits"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.credits_choice = wx.Choice(self)
        for value, label in self._credit_options():
            self.credits_choice.Append(label, value)
        if self.credits_choice.GetCount() > 0:
            self.credits_choice.SetSelection(0)
        form_sizer.Add(self.credits_choice, 1, wx.EXPAND)

        form_sizer.Add(wx.StaticText(self, label="Optional"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.optional_checkbox = wx.CheckBox(self, label="Mark as optional")
        form_sizer.Add(self.optional_checkbox, 1, wx.EXPAND)

        form_sizer.Add(wx.StaticText(self, label="Remark"), 0, wx.ALIGN_TOP)
        self.remark_input = wx.TextCtrl(self, style=wx.TE_MULTILINE, size=wx.Size(-1, 70))
        form_sizer.Add(self.remark_input, 1, wx.EXPAND)

        form_sizer.Add(wx.StaticText(self, label="Prerequisite"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.prereq_choice = wx.Choice(self)
        self.prereq_choice.Append("(none)", None)
        for existing in self._existing_semester_modules:
            label = f"{getattr(existing, 'module_code', '')} - {getattr(existing, 'module_name', '')}".strip(
                " -"
            )
            self.prereq_choice.Append(label, getattr(existing, "id", None))
        self.prereq_choice.SetSelection(0)
        form_sizer.Add(self.prereq_choice, 1, wx.EXPAND)

        main_sizer.Add(form_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)
        main_sizer.AddSpacer(20)

        buttons = wx.BoxSizer(wx.HORIZONTAL)
        buttons.AddStretchSpacer()

        ok_btn = wx.Button(self, wx.ID_OK, "Create")
        ok_btn.Bind(wx.EVT_BUTTON, self._on_submit)
        buttons.Add(ok_btn, 0, wx.RIGHT, 10)

        cancel_btn = wx.Button(self, wx.ID_CANCEL, "Cancel")
        buttons.Add(cancel_btn, 0)

        main_sizer.Add(buttons, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        self.SetSizer(main_sizer)

    def _on_search(self, event: wx.CommandEvent) -> None:
        query = self.search_input.GetValue().strip()
        if not query:
            wx.MessageBox(
                "Please enter a search term.",
                "Search",
                wx.OK | wx.ICON_INFORMATION,
            )
            return

        self.results_list.DeleteAllItems()
        self._selected_module_id = None
        self._selected_module_code = None
        self._selected_module_name = None
        self.selected_module_label.SetLabel("Selected module: (none)")

        with Session(self._engine) as session:
            pattern = f"%{query.lower()}%"
            results = (
                session.query(Module)
                .filter(
                    (func.lower(Module.code).like(pattern))
                    | (func.lower(Module.name).like(pattern))
                )
                .order_by(Module.code)
                .limit(100)
                .all()
            )

        for idx, module in enumerate(results):
            self.results_list.InsertItem(idx, str(getattr(module, "code", "")))
            self.results_list.SetItem(idx, 1, str(getattr(module, "name", "")))
            self.results_list.SetItem(idx, 2, str(getattr(module, "status", "")))
            self.results_list.SetItemData(idx, int(getattr(module, "id")))

        if not results:
            wx.MessageBox(
                "No modules found.",
                "Search",
                wx.OK | wx.ICON_INFORMATION,
            )

    def _on_result_selected(self, event: wx.ListEvent) -> None:
        selected_idx = self.results_list.GetFirstSelected()
        if selected_idx == wx.NOT_FOUND:
            return

        self._selected_module_id = int(self.results_list.GetItemData(selected_idx))
        self._selected_module_code = self.results_list.GetItemText(selected_idx, 0)
        self._selected_module_name = self.results_list.GetItemText(selected_idx, 1)

        label = f"Selected module: {self._selected_module_code} - {self._selected_module_name}"
        self.selected_module_label.SetLabel(label)

    def _on_result_activated(self, event: wx.ListEvent) -> None:
        self._on_result_selected(event)
        self._on_submit(event)

    def _on_submit(self, event: wx.CommandEvent) -> None:
        if self._selected_module_id is None:
            wx.MessageBox(
                "Please select a module.",
                "Validation",
                wx.OK | wx.ICON_WARNING,
            )
            return

        if self.type_choice.GetSelection() == wx.NOT_FOUND:
            wx.MessageBox(
                "Please select a type.",
                "Validation",
                wx.OK | wx.ICON_WARNING,
            )
            return

        if self.credits_choice.GetSelection() == wx.NOT_FOUND:
            wx.MessageBox(
                "Please select credits.",
                "Validation",
                wx.OK | wx.ICON_WARNING,
            )
            return

        credits = self.credits_choice.GetClientData(self.credits_choice.GetSelection())
        if credits in (None, ""):
            wx.MessageBox(
                "Please select credits.",
                "Validation",
                wx.OK | wx.ICON_WARNING,
            )
            return

        event.Skip()

    def get_data(self) -> dict:
        module_type = None
        if self.type_choice.GetSelection() != wx.NOT_FOUND:
            module_type = self.type_choice.GetString(self.type_choice.GetSelection())

        credits = None
        if self.credits_choice.GetSelection() != wx.NOT_FOUND:
            credits = self.credits_choice.GetClientData(self.credits_choice.GetSelection())

        prereq_id = None
        if self.prereq_choice.GetSelection() != wx.NOT_FOUND:
            prereq_id = self.prereq_choice.GetClientData(self.prereq_choice.GetSelection())

        return {
            "module_id": self._selected_module_id,
            "module_code": self._selected_module_code,
            "module_name": self._selected_module_name,
            "module_type": module_type,
            "optional": bool(self.optional_checkbox.GetValue()),
            "credits": str(credits) if credits is not None else "",
            "remark": self.remark_input.GetValue().strip(),
            "prerequisite_id": prereq_id,
        }

    @staticmethod
    def _type_options() -> list[str]:
        base = list(ModuleType.__args__)
        if "Standard" not in base:
            base.append("Standard")
        return base

    @staticmethod
    def _credit_options() -> list[tuple[str | None, str]]:
        values: list[tuple[str | None, str]] = [(None, "?")]
        current = 1.0
        while current <= 12.0:
            raw = str(int(current)) if current.is_integer() else str(current)
            values.append((raw, f"{current:.1f}"))
            current += 0.5
        return values
