import threading
from typing import Any, cast

import wx

from .loader_control import LoadableControl
from .new_semester_dialog import NewSemesterDialog
from .new_semester_module_dialog import NewSemesterModuleDialog
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


class CreateSemesterModuleWorker(threading.Thread):
    def __init__(
        self,
        semester_id: int,
        data: dict,
        service: SchoolSyncService,
        callback,
    ):
        super().__init__(daemon=True)
        self.semester_id = semester_id
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

            success, message = self.service.create_semester_module(
                self.semester_id,
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


class CreateSemesterWorker(threading.Thread):
    def __init__(
        self,
        structure_id: int,
        data: dict,
        service: SchoolSyncService,
        callback,
    ):
        super().__init__(daemon=True)
        self.structure_id = structure_id
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

            success, message = self.service.create_semester(
                self.structure_id,
                str(self.data.get("semester_code") or "").strip(),
                self.data.get("credits"),
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
        self.selected_program_id: int | None = None
        self.selected_program_name: str | None = None
        self.selected_structure_id: int | None = None
        self.selected_structure_code: str | None = None
        self.selected_semester_id: int | None = None
        self.selected_semester_name: str | None = None
        self.fetch_worker = None
        self.fetch_modules_worker = None
        self.create_structure_worker = None
        self.create_semester_worker = None
        self.create_semester_module_worker = None
        self.semesters_loader: LoadableControl
        self.modules_loader: LoadableControl

        self.init_ui()

    def init_ui(self):
        self.SetMinSize(wx.Size(760, -1))
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

        self.desc_label = wx.StaticText(
            self, label="Select a structure to view details"
        )
        sizer.Add(self.desc_label, 0, wx.BOTTOM, 5)

        program_row_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.program_label = wx.StaticText(self, label="")
        program_row_sizer.Add(self.program_label, 0, wx.ALIGN_CENTER_VERTICAL)
        program_row_sizer.AddStretchSpacer()

        self.add_semester_button = wx.Button(self, label="Add Semester")
        self.add_semester_button.Bind(wx.EVT_BUTTON, self.on_add_semester)
        self.add_semester_button.Enable(False)
        program_row_sizer.Add(self.add_semester_button, 0, wx.ALIGN_CENTER_VERTICAL)

        sizer.Add(program_row_sizer, 0, wx.EXPAND | wx.BOTTOM, 20)

        line = wx.StaticLine(self)
        sizer.Add(line, 0, wx.EXPAND | wx.BOTTOM, 15)

        self.semesters_loader = LoadableControl(self, self.on_semesters_loaded)
        semesters_container = self.semesters_loader.get_container()

        self.semesters_list = wx.ListCtrl(
            semesters_container,
            style=wx.LC_REPORT | wx.BORDER_SIMPLE | wx.LC_SINGLE_SEL,
        )
        self.semesters_list.AppendColumn("No.", width=50)
        self.semesters_list.AppendColumn("Semester", width=240)
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

        self.new_semester_module_button = wx.Button(self, label="New")
        self.new_semester_module_button.Bind(wx.EVT_BUTTON, self.on_new_semester_module)
        self.new_semester_module_button.Enable(False)
        modules_header_sizer.Add(
            self.new_semester_module_button,
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )

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
        self.modules_list.AppendColumn("Name", width=320)
        self.modules_list.AppendColumn("Type", width=100)
        self.modules_list.AppendColumn("Credits", width=70)
        self.modules_loader.set_content_panel(self.modules_list)

        sizer.Add(modules_container, 5, wx.EXPAND)

        self.SetSizer(sizer)

    def set_program_context(
        self, program_id: int | None, program_name: str | None
    ) -> None:
        self.selected_program_id = program_id
        self.selected_program_name = program_name
        self.new_button.Enable(program_id is not None)
        self.Layout()

    def load_structure_details(self, structure_id, code, desc, program):
        try:
            self.selected_structure_id = structure_id
            self.selected_structure_code = code
            self.selected_semester_id = None
            self.selected_semester_name = None
            self.detail_title.SetLabel(code)
            self.fetch_button.Enable(True)
            self.new_button.Enable(True)
            self.fetch_modules_button.Enable(False)
            self.new_semester_module_button.Enable(False)
            self.add_semester_button.Enable(True)
            self.desc_label.SetLabel(str(desc))
            self.program_label.SetLabel(str(program))

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
        program_id: int | None = self.selected_program_id
        program_name: str | None = self.selected_program_name

        if program_id is None and self.selected_structure_id is not None:
            program_info = self.repository.get_program_for_structure(
                int(self.selected_structure_id)
            )
            if program_info:
                program_id, program_name = program_info

        if program_id is None or program_name is None:
            wx.MessageBox(
                "Please select a program in Filters first.",
                "Missing Program",
                wx.OK | wx.ICON_WARNING,
            )
            return

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
            int(program_id),
            data,
            self.service,
            self.on_create_structure_callback,
        )
        self.create_structure_worker.start()

    def on_add_semester(self, event):
        if self.selected_structure_id is None or self.selected_structure_code is None:
            wx.MessageBox(
                "Please select a structure first.",
                "Missing Structure",
                wx.OK | wx.ICON_WARNING,
            )
            return

        program_id: int | None = self.selected_program_id
        program_name: str | None = self.selected_program_name
        if program_id is None or program_name is None:
            program_info = self.repository.get_program_for_structure(
                int(self.selected_structure_id)
            )
            if program_info:
                program_id, program_name = program_info

        if program_name is None:
            wx.MessageBox(
                "Please select a program in Filters first.",
                "Missing Program",
                wx.OK | wx.ICON_WARNING,
            )
            return

        dialog = NewSemesterDialog(
            self,
            program_name=program_name,
            structure_code=str(self.selected_structure_code),
        )
        result = dialog.ShowModal()
        data = dialog.get_data()
        dialog.Destroy()

        if result != wx.ID_OK:
            return

        if not str(data.get("semester_code") or "").strip():
            wx.MessageBox(
                "Semester is required.",
                "Validation",
                wx.OK | wx.ICON_WARNING,
            )
            return

        if self.create_semester_worker and self.create_semester_worker.is_alive():
            wx.MessageBox(
                "Another operation is in progress. Please wait.",
                "Operation in Progress",
                wx.OK | wx.ICON_INFORMATION,
            )
            return

        self.add_semester_button.Enable(False)

        self.create_semester_worker = CreateSemesterWorker(
            int(self.selected_structure_id),
            data,
            self.service,
            self.on_create_semester_callback,
        )
        self.create_semester_worker.start()

    def on_create_semester_callback(self, event_type, *args):
        wx.CallAfter(self._handle_create_semester_event, event_type, *args)

    def _handle_create_semester_event(self, event_type, *args):
        if event_type == "progress":
            message = args[0]
            if self.status_bar:
                self.status_bar.show_message(message)
        elif event_type == "finished":
            if self.status_bar:
                self.status_bar.clear()

            self.add_semester_button.Enable(True)

            structure_id = self.selected_structure_id
            if structure_id is not None:

                def load_data():
                    return self.repository.get_structure_semesters(int(structure_id))

                self.semesters_loader.load_async(load_data, "Loading semesters...")

            wx.MessageBox(
                "Semester created successfully.",
                "Create Complete",
                wx.OK | wx.ICON_INFORMATION,
            )
        elif event_type == "error":
            error_msg = args[0]
            if self.status_bar:
                self.status_bar.clear()

            self.add_semester_button.Enable(True)

            wx.MessageBox(
                f"Create failed: {error_msg}",
                "Error",
                wx.OK | wx.ICON_ERROR,
            )

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
        self.new_semester_module_button.Enable(True)
        self.load_semester_modules(semester_id)

    def on_new_semester_module(self, event):
        if self.selected_semester_id is None or self.selected_semester_name is None:
            wx.MessageBox(
                "Please select a semester first.",
                "Missing Semester",
                wx.OK | wx.ICON_WARNING,
            )
            return

        semester_id = int(self.selected_semester_id)
        existing_modules = self.repository.get_semester_modules(semester_id)

        dialog = NewSemesterModuleDialog(
            self,
            semester_id=semester_id,
            semester_name=str(self.selected_semester_name),
            existing_semester_modules=existing_modules,
        )
        result = dialog.ShowModal()
        data = dialog.get_data()
        dialog.Destroy()

        if result != wx.ID_OK:
            return

        if not data.get("module_id"):
            wx.MessageBox(
                "Please select a module.",
                "Validation",
                wx.OK | wx.ICON_WARNING,
            )
            return

        if not str(data.get("module_type") or "").strip():
            wx.MessageBox(
                "Type is required.",
                "Validation",
                wx.OK | wx.ICON_WARNING,
            )
            return

        if not str(data.get("credits") or "").strip():
            wx.MessageBox(
                "Credits is required.",
                "Validation",
                wx.OK | wx.ICON_WARNING,
            )
            return

        if (
            self.create_semester_module_worker
            and self.create_semester_module_worker.is_alive()
        ):
            wx.MessageBox(
                "Another operation is in progress. Please wait.",
                "Operation in Progress",
                wx.OK | wx.ICON_INFORMATION,
            )
            return

        self.new_semester_module_button.Enable(False)
        self.fetch_modules_button.Enable(False)

        self.create_semester_module_worker = CreateSemesterModuleWorker(
            semester_id,
            data,
            self.service,
            self.on_create_semester_module_callback,
        )
        self.create_semester_module_worker.start()

    def on_create_semester_module_callback(self, event_type, *args):
        wx.CallAfter(self._handle_create_semester_module_event, event_type, *args)

    def _handle_create_semester_module_event(self, event_type, *args):
        if event_type == "progress":
            message = args[0]
            if self.status_bar:
                self.status_bar.show_message(message)
        elif event_type == "finished":
            if self.status_bar:
                self.status_bar.clear()

            self.new_semester_module_button.Enable(True)
            self.fetch_modules_button.Enable(True)

            if self.selected_semester_id:
                self.load_semester_modules(int(self.selected_semester_id))

            wx.MessageBox(
                "Module added to semester successfully.",
                "Create Complete",
                wx.OK | wx.ICON_INFORMATION,
            )
        elif event_type == "error":
            error_msg = args[0]
            if self.status_bar:
                self.status_bar.clear()

            self.new_semester_module_button.Enable(True)
            self.fetch_modules_button.Enable(True)

            wx.MessageBox(
                f"Create failed: {error_msg}",
                "Error",
                wx.OK | wx.ICON_ERROR,
            )

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
        self.desc_label.SetLabel("Select a structure to view details")
        self.program_label.SetLabel("")
        self.new_button.Enable(self.selected_program_id is not None)
        self.fetch_button.Enable(False)
        self.fetch_modules_button.Enable(False)
        self.new_semester_module_button.Enable(False)
        self.add_semester_button.Enable(False)
        self.semesters_list.DeleteAllItems()
        self.modules_list.DeleteAllItems()
        self.Layout()
