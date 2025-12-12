import threading
from typing import Any, cast

import wx

from .loader_control import LoadableControl
from .new_structure_dialog import NewStructureDialog
from .repository import StructureRepository
from .service import SchoolSyncService


class FetchSemesterModulesWorker(threading.Thread):
    def __init__(self, semester_id, semester_name, service, repository, callback):
        super().__init__(daemon=True)
        self.semester_id = semester_id
        self.semester_name = semester_name
        self.service = service
        self.repository = repository
        self.callback = callback
        self.should_stop = False

    def run(self):
        try:
            if self.should_stop:
                return

            from .scraper import scrape_semester_modules

            self.callback(
                "progress", f"Fetching modules for {self.semester_name}...", 0, 1
            )

            semester_modules = scrape_semester_modules(self.semester_id)

            self.callback(
                "progress", f"Saving modules for {self.semester_name}...", 1, 1
            )

            for sem_module in semester_modules:
                self.repository.save_semester_module(
                    int(sem_module["id"]),
                    str(sem_module["module_code"]),
                    str(sem_module["module_name"]),
                    str(sem_module["type"]),
                    float(sem_module["credits"]),
                    self.semester_id,
                    bool(sem_module["hidden"]),
                )

            self.callback("finished", len(semester_modules))

        except Exception as e:
            self.callback("error", str(e))

    def stop(self):
        self.should_stop = True


class CreateStructureWorker(threading.Thread):
    def __init__(
        self,
        program_id: int,
        data: dict,
        service: SchoolSyncService,
        callback,
    ):
        super().__init__(daemon=True)
        self.program_id = program_id
        self.data = data
        self.service = service
        self.callback = callback
        self.should_stop = False

    def run(self):
        try:
            if self.should_stop:
                return

            def progress(message: str):
                self.callback("progress", message)

            success, message = self.service.create_structure(
                self.program_id,
                self.data,
                progress,
            )

            if success:
                self.callback("finished")
            else:
                self.callback("error", message)
        except Exception as e:
            self.callback("error", str(e))

    def stop(self):
        self.should_stop = True


class FetchStructureDataWorker(threading.Thread):
    def __init__(self, structure_id, structure_code, service, callback):
        super().__init__(daemon=True)
        self.structure_id = structure_id
        self.structure_code = structure_code
        self.service = service
        self.callback = callback
        self.should_stop = False

    def run(self):
        try:
            if self.should_stop:
                return

            self.service._import_semesters(
                [{"id": self.structure_id, "code": self.structure_code}],
                self.structure_code,
                self._progress_callback,
            )

            self.callback("finished")

        except Exception as e:
            self.callback("error", str(e))

    def _progress_callback(self, message, current, total):
        self.callback("progress", message, current, total)

    def stop(self):
        self.should_stop = True


class StructureDetailPanel(wx.Panel):
    def __init__(self, parent, repository, status_bar=None):
        super().__init__(parent)
        self.repository = repository
        self.status_bar = status_bar
        self.service = SchoolSyncService(repository)
        self.selected_structure_id = None
        self.selected_structure_code = None
        self.selected_semester_id = None
        self.selected_semester_name = None
        self.fetch_worker = None
        self.fetch_modules_worker = None
        self.create_structure_worker = None
        self.semesters_loader: LoadableControl
        self.modules_loader: LoadableControl

        self.init_ui()

    def init_ui(self):
        sizer = wx.BoxSizer(wx.VERTICAL)

        title_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.detail_title = wx.StaticText(self, label="Structure Details")
        font = self.detail_title.GetFont()
        font.PointSize = 14
        font = font.Bold()
        self.detail_title.SetFont(font)
        title_sizer.Add(self.detail_title, 0, wx.ALIGN_CENTER_VERTICAL)

        title_sizer.AddStretchSpacer()

        self.new_button = wx.Button(self, label="New")
        self.new_button.Bind(wx.EVT_BUTTON, self.on_new)
        self.new_button.Enable(False)
        title_sizer.Add(self.new_button, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        self.fetch_button = wx.Button(self, label="Fetch")
        self.fetch_button.Bind(wx.EVT_BUTTON, self.on_fetch)
        self.fetch_button.Enable(False)
        title_sizer.Add(self.fetch_button, 0, wx.ALIGN_CENTER_VERTICAL)

        sizer.Add(title_sizer, 0, wx.EXPAND | wx.BOTTOM, 10)

        self.detail_info = wx.StaticText(
            self, label="Select a structure to view details"
        )
        sizer.Add(self.detail_info, 0, wx.BOTTOM, 20)

        line = wx.StaticLine(self)
        sizer.Add(line, 0, wx.EXPAND | wx.BOTTOM, 15)

        self.semesters_loader = LoadableControl(self, self.on_semesters_loaded)
        semesters_container = self.semesters_loader.get_container()

        self.semesters_list = wx.ListCtrl(
            semesters_container,
            style=wx.LC_REPORT | wx.BORDER_SIMPLE | wx.LC_SINGLE_SEL,
        )
        self.semesters_list.AppendColumn("No.", width=50)
        self.semesters_list.AppendColumn("Semester", width=150)
        self.semesters_list.AppendColumn("Credits", width=80)
        self.semesters_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_semester_selected)
        self.semesters_loader.set_content_panel(self.semesters_list)

        sizer.Add(semesters_container, 4, wx.EXPAND | wx.BOTTOM, 15)

        modules_header_sizer = wx.BoxSizer(wx.HORIZONTAL)

        modules_label = wx.StaticText(self, label="Modules")
        font = modules_label.GetFont()
        font.PointSize = 11
        font = font.Bold()
        modules_label.SetFont(font)
        modules_header_sizer.Add(modules_label, 0, wx.ALIGN_CENTER_VERTICAL)

        modules_header_sizer.AddStretchSpacer()

        self.fetch_modules_button = wx.Button(self, label="Fetch")
        self.fetch_modules_button.Bind(wx.EVT_BUTTON, self.on_fetch_modules)
        self.fetch_modules_button.Enable(False)
        modules_header_sizer.Add(self.fetch_modules_button, 0, wx.ALIGN_CENTER_VERTICAL)

        sizer.Add(modules_header_sizer, 0, wx.EXPAND | wx.BOTTOM, 5)

        self.modules_loader = LoadableControl(self, self.on_modules_loaded)
        modules_container = self.modules_loader.get_container()

        self.modules_list = wx.ListCtrl(
            modules_container, style=wx.LC_REPORT | wx.BORDER_SIMPLE
        )
        self.modules_list.AppendColumn("Code", width=100)
        self.modules_list.AppendColumn("Name", width=250)
        self.modules_list.AppendColumn("Type", width=100)
        self.modules_list.AppendColumn("Credits", width=70)
        self.modules_loader.set_content_panel(self.modules_list)

        sizer.Add(modules_container, 5, wx.EXPAND)

        self.SetSizer(sizer)

    def load_structure_details(self, structure_id, code, desc, program):
        try:
            self.selected_structure_id = structure_id
            self.selected_structure_code = code
            self.selected_semester_id = None
            self.selected_semester_name = None
            self.detail_title.SetLabel(f"Structure: {code}")
            self.fetch_button.Enable(True)
            self.new_button.Enable(True)
            self.fetch_modules_button.Enable(False)
            info_text = f"{desc}\n{program}"
            self.detail_info.SetLabel(info_text)

            self.modules_list.DeleteAllItems()

            def load_data():
                return self.repository.get_structure_semesters(structure_id)

            self.semesters_loader.load_async(load_data, "Loading semesters...")

        except Exception as e:
            print(f"Error loading structure details: {str(e)}")

    def on_semesters_loaded(self, success, data):
        if not success:
            wx.MessageBox(
                f"Error loading semesters: {data}", "Load Error", wx.OK | wx.ICON_ERROR
            )
            return

        semesters = data
        self.semesters_list.DeleteAllItems()

        for row, semester in enumerate(semesters):
            index = self.semesters_list.InsertItem(row, semester.semester_number)
            self.semesters_list.SetItem(index, 1, semester.name)
            self.semesters_list.SetItem(index, 2, f"{semester.total_credits:.1f}")
            self.semesters_list.SetItemData(index, semester.id)

        self.Layout()

    def on_fetch(self, event):
        if not self.selected_structure_id or not self.selected_structure_code:
            wx.MessageBox(
                "No structure selected.",
                "Missing Structure",
                wx.OK | wx.ICON_WARNING,
            )
            return

        self.fetch_button.Enable(False)

        self.fetch_worker = FetchStructureDataWorker(
            self.selected_structure_id,
            self.selected_structure_code,
            self.service,
            self.on_fetch_callback,
        )
        self.fetch_worker.start()

    def on_new(self, event):
        if not self.selected_structure_id:
            wx.MessageBox(
                "No structure selected.",
                "Missing Structure",
                wx.OK | wx.ICON_WARNING,
            )
            return

        program_info = self.repository.get_program_for_structure(
            int(self.selected_structure_id)
        )
        if not program_info:
            wx.MessageBox(
                "Could not determine program for selected structure.",
                "Missing Program",
                wx.OK | wx.ICON_ERROR,
            )
            return

        program_id, program_name = program_info

        dialog = NewStructureDialog(
            self,
            program_name=program_name,
            default_code="",
            default_desc="",
        )
        result = dialog.ShowModal()
        data = dialog.get_data()
        dialog.Destroy()

        if result != wx.ID_OK:
            return

        if not data.get("code") or not data.get("desc"):
            wx.MessageBox(
                "Code and Desc are required.",
                "Validation",
                wx.OK | wx.ICON_WARNING,
            )
            return

        self.new_button.Enable(False)
        self.fetch_button.Enable(False)

        self.create_structure_worker = CreateStructureWorker(
            program_id,
            data,
            self.service,
            self.on_create_structure_callback,
        )
        self.create_structure_worker.start()

    def on_create_structure_callback(self, event_type, *args):
        wx.CallAfter(self._handle_create_structure_event, event_type, *args)

    def _handle_create_structure_event(self, event_type, *args):
        if event_type == "progress":
            message = args[0]
            if self.status_bar:
                self.status_bar.show_message(message)
        elif event_type == "finished":
            if self.status_bar:
                self.status_bar.clear()

            self.new_button.Enable(True)
            self.fetch_button.Enable(True)

            parent = self.GetParent()
            if parent and hasattr(parent, "load_structures"):
                cast(Any, parent).load_structures()

            wx.MessageBox(
                "Structure created successfully.",
                "Create Complete",
                wx.OK | wx.ICON_INFORMATION,
            )
        elif event_type == "error":
            error_msg = args[0]
            if self.status_bar:
                self.status_bar.clear()

            self.new_button.Enable(True)
            self.fetch_button.Enable(True)

            wx.MessageBox(
                f"Create failed: {error_msg}",
                "Error",
                wx.OK | wx.ICON_ERROR,
            )

    def on_fetch_callback(self, event_type, *args):
        wx.CallAfter(self._handle_fetch_event, event_type, *args)

    def _handle_fetch_event(self, event_type, *args):
        if event_type == "progress":
            message, current, total = args
            if self.status_bar:
                self.status_bar.show_progress(message, current, total)
        elif event_type == "finished":
            if self.status_bar:
                self.status_bar.clear()

            self.fetch_button.Enable(True)

            if self.selected_structure_id:
                self.modules_list.DeleteAllItems()

                def load_data():
                    return self.repository.get_structure_semesters(
                        self.selected_structure_id
                    )

                self.semesters_loader.load_async(load_data, "Loading semesters...")

            wx.MessageBox(
                f"Successfully fetched structure data for {self.selected_structure_code}.",
                "Fetch Complete",
                wx.OK | wx.ICON_INFORMATION,
            )

        elif event_type == "error":
            error_msg = args[0]
            if self.status_bar:
                self.status_bar.clear()

            self.fetch_button.Enable(True)

            wx.MessageBox(f"Fetch failed: {error_msg}", "Error", wx.OK | wx.ICON_ERROR)

    def on_semester_selected(self, event):
        item = event.GetIndex()
        semester_id = self.semesters_list.GetItemData(item)
        semester_name = self.semesters_list.GetItemText(item, 0)
        self.selected_semester_id = semester_id
        self.selected_semester_name = semester_name
        self.fetch_modules_button.Enable(True)
        self.load_semester_modules(semester_id)

    def on_fetch_modules(self, event):
        if not self.selected_semester_id or not self.selected_semester_name:
            wx.MessageBox(
                "No semester selected.",
                "Missing Semester",
                wx.OK | wx.ICON_WARNING,
            )
            return

        self.fetch_modules_button.Enable(False)

        self.fetch_modules_worker = FetchSemesterModulesWorker(
            self.selected_semester_id,
            self.selected_semester_name,
            self.service,
            self.repository,
            self.on_fetch_modules_callback,
        )
        self.fetch_modules_worker.start()

    def on_fetch_modules_callback(self, event_type, *args):
        wx.CallAfter(self._handle_fetch_modules_event, event_type, *args)

    def _handle_fetch_modules_event(self, event_type, *args):
        if event_type == "progress":
            message, current, total = args
            if self.status_bar:
                self.status_bar.show_progress(message, current, total)
        elif event_type == "finished":
            modules_count = args[0]
            if self.status_bar:
                self.status_bar.clear()

            self.fetch_modules_button.Enable(True)

            if self.selected_semester_id:
                self.load_semester_modules(self.selected_semester_id)

            wx.MessageBox(
                f"Successfully fetched {modules_count} module(s) for {self.selected_semester_name}.",
                "Fetch Complete",
                wx.OK | wx.ICON_INFORMATION,
            )

        elif event_type == "error":
            error_msg = args[0]
            if self.status_bar:
                self.status_bar.clear()

            self.fetch_modules_button.Enable(True)

            wx.MessageBox(f"Fetch failed: {error_msg}", "Error", wx.OK | wx.ICON_ERROR)

    def load_semester_modules(self, semester_id):
        def load_data():
            return self.repository.get_semester_modules(semester_id)

        self.modules_loader.load_async(load_data, "Loading modules...")

    def on_modules_loaded(self, success, data):
        if not success:
            wx.MessageBox(
                f"Error loading modules: {data}", "Load Error", wx.OK | wx.ICON_ERROR
            )
            return

        modules = data
        self.modules_list.DeleteAllItems()

        for row, module in enumerate(modules):
            if module.hidden:
                continue

            index = self.modules_list.InsertItem(row, module.module_code)
            self.modules_list.SetItem(index, 1, module.module_name)
            self.modules_list.SetItem(index, 2, module.type)
            self.modules_list.SetItem(index, 3, f"{module.credits:.1f}")

        self.Layout()

    def clear(self):
        self.selected_structure_id = None
        self.selected_structure_code = None
        self.selected_semester_id = None
        self.selected_semester_name = None
        self.detail_title.SetLabel("Structure Details")
        self.detail_info.SetLabel("Select a structure to view details")
        self.new_button.Enable(False)
        self.fetch_button.Enable(False)
        self.fetch_modules_button.Enable(False)
        self.semesters_list.DeleteAllItems()
        self.modules_list.DeleteAllItems()
        self.Layout()
