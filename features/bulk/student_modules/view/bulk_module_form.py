import threading

import wx

from database.models import Grade, StudentModuleStatus
from features.sync.students.repository import StudentRepository
from utils.formatters import format_semester
from utils.permissions import can_edit_grades


class BulkModuleFormDialog(wx.Dialog):
    """Dialog for bulk editing module data - similar to module_form.py but for bulk operations."""

    def __init__(self, module_info, parent=None, status_bar=None):
        super().__init__(
            parent,
            title=f"Bulk Update Module: {module_info.get('module_code', '')}",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self.module_info = module_info
        self.status_bar = status_bar
        self.repository = StudentRepository()
        self.selected_semester_module_id = None
        self.semester_module_changed = False
        # Store original values to detect changes
        self.original_status = module_info.get("status", "")
        self.original_credits = (
            str(module_info.get("credits", "")) if module_info.get("credits") else ""
        )
        self.SetSize(wx.Size(650, 500))
        self.CenterOnScreen()
        self.init_ui()

    def init_ui(self):
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        notebook = wx.Notebook(panel)

        basic_panel = self.create_basic_panel(notebook)
        advanced_panel = self.create_advanced_panel(notebook)

        notebook.AddPage(basic_panel, "Basic")
        notebook.AddPage(advanced_panel, "Advanced")

        main_sizer.Add(notebook, 1, wx.ALL | wx.EXPAND, 10)

        button_sizer = wx.StdDialogButtonSizer()
        save_btn = wx.Button(panel, wx.ID_OK, "Apply to Selected")
        save_btn.Bind(wx.EVT_BUTTON, self.on_save)
        button_sizer.AddButton(save_btn)

        cancel_btn = wx.Button(panel, wx.ID_CANCEL, "Cancel")
        button_sizer.AddButton(cancel_btn)
        button_sizer.Realize()

        main_sizer.Add(button_sizer, 0, wx.ALL | wx.ALIGN_RIGHT, 10)

        panel.SetSizer(main_sizer)

    def create_basic_panel(self, parent):
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)

        info_label = wx.StaticText(
            panel,
            label="Changes made here will be applied to ALL selected students.\n"
            "Values shown are from the first selected student.",
        )
        font = info_label.GetFont()
        font.PointSize = 9
        info_label.SetFont(font)
        sizer.Add(info_label, 0, wx.ALL | wx.EXPAND, 10)

        sizer.Add(
            wx.StaticLine(panel, style=wx.LI_HORIZONTAL), 0, wx.EXPAND | wx.ALL, 5
        )

        form_sizer = wx.FlexGridSizer(rows=4, cols=2, vgap=10, hgap=10)
        form_sizer.AddGrowableCol(1)

        form_sizer.Add(
            wx.StaticText(panel, label="Module Code:"),
            0,
            wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL,
        )
        module_code_text = wx.StaticText(
            panel, label=str(self.module_info.get("module_code", ""))
        )
        form_sizer.Add(module_code_text, 0, wx.EXPAND)

        form_sizer.Add(
            wx.StaticText(panel, label="Module Name:"),
            0,
            wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL,
        )
        module_name_text = wx.StaticText(
            panel, label=str(self.module_info.get("module_name", ""))
        )
        form_sizer.Add(module_name_text, 0, wx.EXPAND)

        # Status - pre-selected with existing value
        form_sizer.Add(
            wx.StaticText(panel, label="Status:"),
            0,
            wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL,
        )
        self.status_combobox = wx.ComboBox(
            panel, style=wx.CB_READONLY, choices=list(StudentModuleStatus.__args__)
        )
        # Set to existing value if valid
        current_status = self.module_info.get("status", "")
        if current_status in StudentModuleStatus.__args__:
            self.status_combobox.SetStringSelection(current_status)
        form_sizer.Add(self.status_combobox, 0, wx.EXPAND)

        # Credits - pre-filled with existing value
        form_sizer.Add(
            wx.StaticText(panel, label="Credits:"),
            0,
            wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL,
        )
        current_credits = (
            str(self.module_info.get("credits", ""))
            if self.module_info.get("credits")
            else ""
        )
        self.credits_input = wx.TextCtrl(panel, value=current_credits)
        form_sizer.Add(self.credits_input, 0, wx.EXPAND)

        sizer.Add(form_sizer, 0, wx.ALL | wx.EXPAND, 20)

        panel.SetSizer(sizer)
        return panel

    def create_advanced_panel(self, parent):
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)

        info_label = wx.StaticText(
            panel,
            label="Change the semester module association for all selected students.\n"
            "This is an advanced operation - use with caution.",
        )
        font = info_label.GetFont()
        font.PointSize = 9
        info_label.SetFont(font)
        sizer.Add(info_label, 0, wx.ALL | wx.EXPAND, 10)

        sizer.Add(
            wx.StaticLine(panel, style=wx.LI_HORIZONTAL), 0, wx.EXPAND | wx.ALL, 5
        )

        search_sizer = wx.BoxSizer(wx.HORIZONTAL)
        search_sizer.Add(
            wx.StaticText(panel, label="Search Module:"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            5,
        )
        self.search_input = wx.TextCtrl(panel)
        self.search_input.SetHint("Enter module code or name...")
        search_sizer.Add(self.search_input, 1, wx.EXPAND | wx.RIGHT, 5)

        search_btn = wx.Button(panel, label="Search")
        search_btn.Bind(wx.EVT_BUTTON, self.on_search_modules)
        search_sizer.Add(search_btn, 0)

        sizer.Add(search_sizer, 0, wx.ALL | wx.EXPAND, 10)

        self.results_list = wx.ListCtrl(
            panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SUNKEN
        )
        self.results_list.AppendColumn("Code", width=80)
        self.results_list.AppendColumn("Name", width=200)
        self.results_list.AppendColumn("Program", width=200)
        self.results_list.AppendColumn("Semester", width=100)
        self.results_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_module_selected)

        sizer.Add(self.results_list, 1, wx.ALL | wx.EXPAND, 10)

        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.select_btn = wx.Button(panel, label="Select This Module")
        self.select_btn.Enable(False)
        self.select_btn.Bind(wx.EVT_BUTTON, self.on_confirm_selection)
        button_sizer.Add(self.select_btn, 0)

        sizer.Add(button_sizer, 0, wx.ALL | wx.ALIGN_LEFT, 10)

        self.selection_label = wx.StaticText(panel, label="")
        font = self.selection_label.GetFont()
        font = font.Bold()
        self.selection_label.SetFont(font)
        sizer.Add(self.selection_label, 0, wx.ALL | wx.ALIGN_LEFT, 10)

        panel.SetSizer(sizer)
        return panel

    def on_search_modules(self, event):
        search_query = self.search_input.GetValue().strip()
        if not search_query:
            wx.MessageBox(
                "Please enter a search term",
                "Search Required",
                wx.OK | wx.ICON_INFORMATION,
            )
            return

        self.results_list.DeleteAllItems()
        self.select_btn.Enable(False)

        if self.status_bar:
            wx.CallAfter(
                self.status_bar.show_message, f"Searching for modules: {search_query}"
            )

        worker = SearchModulesWorker(
            search_query, self.repository, self.on_search_complete
        )
        worker.start()

    def on_search_complete(self, results):
        wx.CallAfter(self._display_search_results, results)

    def _display_search_results(self, results):
        self.results_list.DeleteAllItems()

        if not results:
            wx.MessageBox(
                "No modules found matching your search",
                "No Results",
                wx.OK | wx.ICON_INFORMATION,
            )
            if self.status_bar:
                self.status_bar.clear()
            return

        for idx, result in enumerate(results):
            self.results_list.InsertItem(idx, result["module_code"])
            self.results_list.SetItem(idx, 1, result["module_name"])
            self.results_list.SetItem(idx, 2, result["program_name"])
            self.results_list.SetItem(
                idx, 3, format_semester(result.get("semester_number"), type="short")
            )
            self.results_list.SetItemData(idx, result["semester_module_id"])

        if self.status_bar:
            self.status_bar.clear()

    def on_module_selected(self, event):
        self.select_btn.Enable(True)

    def on_confirm_selection(self, event):
        selected_idx = self.results_list.GetFirstSelected()
        if selected_idx == -1:
            return

        module_code = self.results_list.GetItemText(selected_idx, 0)
        module_name = self.results_list.GetItemText(selected_idx, 1)
        program_name = self.results_list.GetItemText(selected_idx, 2)
        semester_module_id = self.results_list.GetItemData(selected_idx)

        message = (
            f"Are you sure you want to change the semester module to:\n\n"
            f"Module: {module_code} - {module_name}\n"
            f"Program: {program_name}\n\n"
            f"This change will be applied to ALL selected students."
        )

        dlg = wx.MessageDialog(
            self,
            message,
            "Confirm Semester Module Change",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
        )

        if dlg.ShowModal() == wx.ID_YES:
            self.selected_semester_module_id = semester_module_id
            self.semester_module_changed = True
            self.selection_label.SetLabel(
                f"✓ Selected: {module_code} - {module_name} ({program_name})"
            )
            self.selection_label.SetForegroundColour(wx.Colour(0, 128, 0))

        dlg.Destroy()

    def on_save(self, event):
        status = self.status_combobox.GetValue().strip()
        credits = self.credits_input.GetValue().strip()

        if credits:
            try:
                float(credits)
            except ValueError:
                wx.MessageBox(
                    "Credits must be a valid number",
                    "Validation Error",
                    wx.OK | wx.ICON_WARNING,
                )
                return

        # Check if any changes were made compared to original values
        has_status_change = status != self.original_status
        has_credits_change = credits != self.original_credits
        has_module_change = self.semester_module_changed

        if not has_status_change and not has_credits_change and not has_module_change:
            wx.MessageBox(
                "No changes have been made. Please modify at least one field.",
                "No Changes",
                wx.OK | wx.ICON_INFORMATION,
            )
            return

        if self.semester_module_changed:
            message = (
                "You are about to apply changes including a semester module change.\n"
                "This is a significant modification. Do you want to proceed?"
            )
            dlg = wx.MessageDialog(
                self, message, "Confirm Save", wx.YES_NO | wx.ICON_WARNING
            )

            if dlg.ShowModal() != wx.ID_YES:
                dlg.Destroy()
                return
            dlg.Destroy()

        event.Skip()

    def get_updated_data(self):
        """Return all field values - CMS requires all fields to be sent."""
        data = {}

        # Always include status - CMS requires it
        status = self.status_combobox.GetValue().strip()
        if status:
            data["status"] = status

        # Always include credits - CMS requires it
        credits_value = self.credits_input.GetValue().strip()
        if credits_value:
            data["credits"] = credits_value

        if self.semester_module_changed and self.selected_semester_module_id:
            data["semester_module_id"] = self.selected_semester_module_id

        return data


class SearchModulesWorker(threading.Thread):
    def __init__(self, search_query, repository, callback):
        super().__init__(daemon=True)
        self.search_query = search_query
        self.repository = repository
        self.callback = callback

    def run(self):
        results = self.repository.search_semester_modules(self.search_query)
        self.callback(results)
