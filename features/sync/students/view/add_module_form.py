import threading

import wx

from base import get_logger
from database.models import StudentModuleStatus
from features.sync.students.repository import StudentRepository
from features.sync.students.service import StudentSyncService
from utils.formatters import format_semester

logger = get_logger(__name__)


class AddModuleFormDialog(wx.Dialog):
    def __init__(self, student_semester_id, parent=None, status_bar=None):
        super().__init__(
            parent,
            title="Add Module",
            size=wx.Size(700, 600),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self.student_semester_id = student_semester_id
        self.status_bar = status_bar
        self.repository = StudentRepository()
        self.service = None
        self.push_worker = None
        self.selected_semester_module_id = None
        self.selected_module_data = None
        self.stored_results = []

        self.CenterOnScreen()
        self.init_ui()

    def init_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        info_label = wx.StaticText(
            self,
            label="Search for a module by code or name, then select it to add to this semester.",
        )
        font = info_label.GetFont()
        font.PointSize = 9
        info_label.SetFont(font)
        main_sizer.Add(info_label, 0, wx.ALL | wx.EXPAND, 10)

        main_sizer.Add(
            wx.StaticLine(self, style=wx.LI_HORIZONTAL), 0, wx.EXPAND | wx.ALL, 5
        )

        search_sizer = wx.BoxSizer(wx.HORIZONTAL)
        search_sizer.Add(
            wx.StaticText(self, label="Search Module:"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            5,
        )
        self.search_input = wx.TextCtrl(
            self, style=wx.TE_PROCESS_ENTER, size=wx.Size(-1, -1)
        )
        self.search_input.SetHint("Enter module code or name...")
        self.search_input.Bind(wx.EVT_TEXT_ENTER, self.on_search_modules)
        search_sizer.Add(self.search_input, 1, wx.EXPAND | wx.RIGHT, 5)

        search_btn = wx.Button(self, label="Search")
        search_btn.Bind(wx.EVT_BUTTON, self.on_search_modules)
        search_sizer.Add(search_btn, 0)

        main_sizer.Add(search_sizer, 0, wx.ALL | wx.EXPAND, 10)

        self.results_list = wx.ListCtrl(
            self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SUNKEN
        )
        self.results_list.AppendColumn("Code", width=100)
        self.results_list.AppendColumn("Name", width=250)
        self.results_list.AppendColumn("Program", width=200)
        self.results_list.AppendColumn("Semester", width=80)
        self.results_list.AppendColumn("Credits", width=60)
        self.results_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_module_selected)
        self.results_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.on_module_activated)

        main_sizer.Add(self.results_list, 1, wx.ALL | wx.EXPAND, 10)

        details_panel = wx.Panel(self, style=wx.BORDER_STATIC)
        details_panel_sizer = wx.BoxSizer(wx.VERTICAL)

        self.details_code_name = wx.StaticText(details_panel, label="")
        font = self.details_code_name.GetFont()
        font = font.Bold()
        self.details_code_name.SetFont(font)
        details_panel_sizer.Add(self.details_code_name, 0, wx.ALL, 5)

        self.details_info = wx.StaticText(details_panel, label="")
        details_panel_sizer.Add(self.details_info, 1, wx.ALL | wx.EXPAND, 5)

        details_panel.SetSizer(details_panel_sizer)
        main_sizer.Add(details_panel, 0, wx.ALL | wx.EXPAND, 10)

        main_sizer.Add(
            wx.StaticLine(self, style=wx.LI_HORIZONTAL), 0, wx.EXPAND | wx.ALL, 5
        )

        form_sizer = wx.BoxSizer(wx.HORIZONTAL)
        form_sizer.Add(
            wx.StaticText(self, label="Module Status:"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            5,
        )

        self.status_combo = wx.ComboBox(
            self, style=wx.CB_READONLY, choices=list(StudentModuleStatus.__args__)
        )
        compulsory_index = list(StudentModuleStatus.__args__).index("Compulsory")
        self.status_combo.SetSelection(compulsory_index)
        form_sizer.Add(self.status_combo, 0, wx.RIGHT, 10)

        main_sizer.Add(form_sizer, 0, wx.ALL | wx.EXPAND, 10)

        button_sizer = wx.StdDialogButtonSizer()

        cancel_btn = wx.Button(self, wx.ID_CANCEL, "Cancel")
        button_sizer.AddButton(cancel_btn)

        self.add_btn = wx.Button(self, wx.ID_OK, "Add Module")
        self.add_btn.Enable(False)
        self.add_btn.Bind(wx.EVT_BUTTON, self.on_add_module)
        button_sizer.AddButton(self.add_btn)
        button_sizer.Realize()

        main_sizer.Add(button_sizer, 0, wx.ALL | wx.ALIGN_RIGHT, 10)

        self.SetSizer(main_sizer)

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
        self.add_btn.Enable(False)
        self.selected_semester_module_id = None

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
        self.details_code_name.SetLabel("")
        self.details_info.SetLabel("")
        self.selected_module_data = None
        self.stored_results = results if results else []

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
            self.results_list.SetItem(idx, 4, str(result.get("credits", "")))
            self.results_list.SetItemData(idx, result["semester_module_id"])

        if self.status_bar:
            wx.CallAfter(self.status_bar.clear)

    def on_module_selected(self, event):
        self.add_btn.Enable(True)
        selected_idx = self.results_list.GetFirstSelected()
        if selected_idx != -1:
            self.selected_semester_module_id = self.results_list.GetItemData(
                selected_idx
            )
            if selected_idx < len(self.stored_results):
                result = self.stored_results[selected_idx]
                self.selected_module_data = result
                code_name, info = self._format_module_details(result)
                self.details_code_name.SetLabel(code_name)
                self.details_info.SetLabel(info)

    def _format_module_details(self, module_data):
        code_name = f"{module_data.get('module_name', 'N/A')} ({module_data.get('module_code', 'N/A')})"
        info = f"{module_data.get('program_name', 'N/A')} • {format_semester(module_data.get('semester_number'), type='short')} • Credits: {module_data.get('credits', 'N/A')}"
        return code_name, info

    def on_module_activated(self, event):
        self.on_add_module(event)

    def on_add_module(self, event):
        if not self.selected_semester_module_id:
            selected_idx = self.results_list.GetFirstSelected()
            if selected_idx == -1:
                wx.MessageBox(
                    "Please select a module first",
                    "No Module Selected",
                    wx.OK | wx.ICON_WARNING,
                )
                return
            self.selected_semester_module_id = self.results_list.GetItemData(
                selected_idx
            )

        module_status = self.status_combo.GetValue().strip()
        if not module_status:
            wx.MessageBox(
                "Please select a module status",
                "Validation Error",
                wx.OK | wx.ICON_WARNING,
            )
            return

        if self.push_worker and self.push_worker.is_alive():
            wx.MessageBox(
                "Another operation is in progress. Please wait.",
                "Operation in Progress",
                wx.OK | wx.ICON_INFORMATION,
            )
            return

        if not self.service:
            self.service = StudentSyncService(self.repository)

        module_code = (
            self.selected_module_data.get("module_code")
            if self.selected_module_data
            else None
        )
        if not module_code:
            wx.MessageBox(
                "Module code not found",
                "Error",
                wx.OK | wx.ICON_ERROR,
            )
            return

        self.push_worker = PushStudentModuleWorker(
            self.student_semester_id,
            self.selected_semester_module_id,
            module_status,
            module_code,
            self.service,
            self.push_callback,
        )
        self.push_worker.start()

    def push_callback(self, event_type, *args):
        if event_type == "progress":
            message = args[0] if args else ""
            if self.status_bar:
                wx.CallAfter(self.status_bar.show_message, message)
        elif event_type == "complete":
            success, message = args if len(args) == 2 else (False, "Unknown error")
            if self.status_bar:
                wx.CallAfter(self.status_bar.clear)

            if success:
                wx.CallAfter(
                    wx.MessageBox,
                    "Module added successfully",
                    "Success",
                    wx.OK | wx.ICON_INFORMATION,
                )
                wx.CallAfter(self.EndModal, wx.ID_OK)
            else:
                wx.CallAfter(
                    wx.MessageBox,
                    f"Failed to add module: {message}",
                    "Error",
                    wx.OK | wx.ICON_ERROR,
                )
        elif event_type == "error":
            error_message = args[0] if args else "Unknown error"
            if self.status_bar:
                wx.CallAfter(self.status_bar.clear)
            wx.CallAfter(
                wx.MessageBox,
                f"Error: {error_message}",
                "Error",
                wx.OK | wx.ICON_ERROR,
            )


class SearchModulesWorker(threading.Thread):
    def __init__(self, search_query, repository, callback):
        super().__init__(daemon=True)
        self.search_query = search_query
        self.repository = repository
        self.callback = callback

    def run(self):
        results = self.repository.search_semester_modules(self.search_query)
        self.callback(results)


class PushStudentModuleWorker(threading.Thread):
    def __init__(
        self,
        student_semester_id,
        semester_module_id,
        module_status,
        module_code,
        service,
        callback,
    ):
        super().__init__(daemon=True)
        self.student_semester_id = student_semester_id
        self.semester_module_id = semester_module_id
        self.module_status = module_status
        self.module_code = module_code
        self.service = service
        self.callback = callback

    def run(self):
        try:
            self.callback("progress", "Adding module to CMS...")
            success, message = self.service.push_student_module(
                self.student_semester_id,
                self.semester_module_id,
                self.module_status,
                self.module_code,
                progress_callback=lambda msg: self.callback("progress", msg),
            )
            self.callback("complete", success, message)
        except Exception as e:
            logger.error(f"Error in PushStudentModuleWorker: {str(e)}")
            self.callback("error", str(e))
