import threading

import wx

from features.sync.students.repository import StudentRepository
from features.sync.students.service import StudentSyncService
from utils.formatters import format_semester

from ..repository import BulkStudentModulesRepository
from .bulk_module_form import BulkModuleFormDialog


class LoadFilterOptionsWorker(threading.Thread):
    def __init__(self, repository, callback):
        super().__init__(daemon=True)
        self.repository = repository
        self.callback = callback
        self.should_stop = False

    def run(self):
        if self.should_stop:
            return
        try:
            schools = self.repository.list_active_schools()
            self.callback("filters_loaded", schools)
        except Exception as e:
            self.callback("filters_error", str(e))

    def stop(self):
        self.should_stop = True


class LoadProgramsWorker(threading.Thread):
    def __init__(self, repository, school_id, callback):
        super().__init__(daemon=True)
        self.repository = repository
        self.school_id = school_id
        self.callback = callback
        self.should_stop = False

    def run(self):
        if self.should_stop:
            return
        try:
            programs = self.repository.list_programs(self.school_id)
            self.callback("programs_loaded", programs)
        except Exception as e:
            self.callback("programs_error", str(e))

    def stop(self):
        self.should_stop = True


class LoadStructuresWorker(threading.Thread):
    def __init__(self, repository, program_id, callback):
        super().__init__(daemon=True)
        self.repository = repository
        self.program_id = program_id
        self.callback = callback
        self.should_stop = False

    def run(self):
        if self.should_stop:
            return
        try:
            structures = self.repository.list_structures(self.program_id)
            self.callback("structures_loaded", structures)
        except Exception as e:
            self.callback("structures_error", str(e))

    def stop(self):
        self.should_stop = True


class LoadModulesWorker(threading.Thread):
    def __init__(self, repository, structure_id, callback):
        super().__init__(daemon=True)
        self.repository = repository
        self.structure_id = structure_id
        self.callback = callback
        self.should_stop = False

    def run(self):
        if self.should_stop:
            return
        try:
            modules = self.repository.list_structure_modules(self.structure_id)
            semesters = self.repository.list_semester_numbers(self.structure_id)
            self.callback("modules_loaded", modules, semesters)
        except Exception as e:
            self.callback("modules_error", str(e))

    def stop(self):
        self.should_stop = True


class LoadStudentsWorker(threading.Thread):
    def __init__(
        self, repository, semester_module_id, structure_id, semester_number, callback
    ):
        super().__init__(daemon=True)
        self.repository = repository
        self.semester_module_id = semester_module_id
        self.structure_id = structure_id
        self.semester_number = semester_number
        self.callback = callback
        self.should_stop = False

    def run(self):
        if self.should_stop:
            return
        try:
            students = self.repository.fetch_students_with_module(
                self.semester_module_id,
                self.structure_id,
                self.semester_number,
            )
            self.callback("students_loaded", students)
        except Exception as e:
            self.callback("students_error", str(e))

    def stop(self):
        self.should_stop = True


class BulkUpdateWorker(threading.Thread):
    def __init__(self, student_modules, update_data, service, callback):
        super().__init__(daemon=True)
        self.student_modules = student_modules
        self.update_data = update_data
        self.service = service
        self.callback = callback
        self.should_stop = False

    def run(self):
        success_count = 0
        failed_count = 0
        total = len(self.student_modules)

        for idx, student_module in enumerate(self.student_modules):
            if self.should_stop:
                break

            try:

                def progress_callback(message):
                    self.callback(
                        "progress",
                        f"Updating {idx + 1}/{total}: {message}",
                        idx + 1,
                        total,
                    )

                # Validate required fields
                if not student_module.student_semester_id:
                    self.callback(
                        "error",
                        f"Skipping student {student_module.std_no}: Missing student_semester_id",
                    )
                    failed_count += 1
                    continue

                # Build module_data matching the pattern from student_detail_panel.py
                # Note: 'id' must be the student_module_id for upsert_student_module
                module_data = {
                    "id": student_module.student_module_id,
                    "student_semester_id": student_module.student_semester_id,
                }

                # Add only the fields that should be updated
                if "status" in self.update_data:
                    module_data["status"] = self.update_data["status"]

                if "credits" in self.update_data:
                    module_data["credits"] = self.update_data["credits"]

                # Use updated semester_module_id if provided, otherwise keep existing
                if "semester_module_id" in self.update_data:
                    module_data["semester_module_id"] = self.update_data[
                        "semester_module_id"
                    ]
                else:
                    module_data["semester_module_id"] = (
                        student_module.semester_module_id
                    )

                success, message = self.service.push_module(
                    student_module.student_module_id,
                    module_data,
                    progress_callback,
                )

                if success:
                    success_count += 1
                else:
                    self.callback(
                        "error",
                        f"Failed to update {student_module.std_no}: {message}",
                    )
                    failed_count += 1

            except Exception as e:
                self.callback(
                    "error",
                    f"Error updating module for student {student_module.std_no}: {str(e)}",
                )
                failed_count += 1

        self.callback("finished", success_count, failed_count)

    def stop(self):
        self.should_stop = True


class StudentModulesView(wx.Panel):
    def __init__(self, parent, status_bar=None):
        super().__init__(parent)
        self.status_bar = status_bar
        self.repository = BulkStudentModulesRepository()
        self.student_repository = StudentRepository()
        self.sync_service = StudentSyncService(self.student_repository)

        self.selected_school_id = None
        self.selected_program_id = None
        self.selected_structure_id = None
        self.selected_module_id = None
        self.selected_semester_number = None

        self.current_students = []
        self.checked_items = set()

        self.filter_worker = None
        self.programs_worker = None
        self.structures_worker = None
        self.modules_worker = None
        self.students_worker = None
        self.update_worker = None

        self.init_ui()
        self.load_filter_options()

    def init_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(self, label="Student Modules")
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

        # First row of filters: School, Program, Structure
        filters_sizer1 = wx.BoxSizer(wx.HORIZONTAL)

        self.school_filter = wx.Choice(self)
        self.school_filter.Append("Select School", None)
        self.school_filter.SetSelection(0)
        self.school_filter.Bind(wx.EVT_CHOICE, self.on_school_changed)
        filters_sizer1.Add(self.school_filter, 0, wx.RIGHT, 10)

        self.program_filter = wx.Choice(self)
        self.program_filter.Append("Select Program", None)
        self.program_filter.SetSelection(0)
        self.program_filter.Enable(False)
        self.program_filter.Bind(wx.EVT_CHOICE, self.on_program_changed)
        filters_sizer1.Add(self.program_filter, 0, wx.RIGHT, 10)

        self.structure_filter = wx.Choice(self)
        self.structure_filter.Append("Select Structure", None)
        self.structure_filter.SetSelection(0)
        self.structure_filter.Enable(False)
        self.structure_filter.Bind(wx.EVT_CHOICE, self.on_structure_changed)
        filters_sizer1.Add(self.structure_filter, 0, wx.RIGHT, 10)

        main_sizer.Add(filters_sizer1, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 40)

        main_sizer.AddSpacer(10)

        # Second row: Module, Semester Number, Add Students button
        filters_sizer2 = wx.BoxSizer(wx.HORIZONTAL)

        self.module_filter = wx.Choice(self)
        self.module_filter.Append("Select Module", None)
        self.module_filter.SetSelection(0)
        self.module_filter.Enable(False)
        self.module_filter.Bind(wx.EVT_CHOICE, self.on_module_changed)
        filters_sizer2.Add(self.module_filter, 0, wx.RIGHT, 10)

        self.semester_filter = wx.Choice(self)
        self.semester_filter.Append("All Semesters", None)
        self.semester_filter.SetSelection(0)
        self.semester_filter.Enable(False)
        self.semester_filter.Bind(wx.EVT_CHOICE, self.on_semester_changed)
        filters_sizer2.Add(self.semester_filter, 0, wx.RIGHT, 10)

        filters_sizer2.AddStretchSpacer()

        self.add_students_button = wx.Button(self, label="Add Students")
        self.add_students_button.Bind(wx.EVT_BUTTON, self.on_add_students)
        self.add_students_button.Enable(False)
        filters_sizer2.Add(self.add_students_button, 0, wx.RIGHT, 10)

        self.update_button = wx.Button(self, label="Update Module")
        self.update_button.Bind(wx.EVT_BUTTON, self.on_update_module)
        self.update_button.Enable(False)
        filters_sizer2.Add(self.update_button, 0)

        main_sizer.Add(filters_sizer2, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 40)

        main_sizer.AddSpacer(15)
        line = wx.StaticLine(self)
        main_sizer.Add(line, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 40)
        main_sizer.AddSpacer(15)

        # Selection controls
        selection_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.select_all_checkbox = wx.CheckBox(self, label="Select All")
        self.select_all_checkbox.Bind(wx.EVT_CHECKBOX, self.on_select_all_changed)
        selection_sizer.Add(self.select_all_checkbox, 0, wx.RIGHT, 10)

        self.selection_label = wx.StaticText(self, label="0 selected")
        selection_sizer.Add(self.selection_label, 0)

        main_sizer.Add(selection_sizer, 0, wx.LEFT | wx.RIGHT, 40)

        main_sizer.AddSpacer(10)

        # Student list
        self.list_ctrl = wx.ListCtrl(self, style=wx.LC_REPORT | wx.BORDER_SIMPLE)

        self.image_list = wx.ImageList(16, 16)
        self.unchecked_idx = self.image_list.Add(self._create_checkbox_bitmap(False))
        self.checked_idx = self.image_list.Add(self._create_checkbox_bitmap(True))
        self.list_ctrl.SetImageList(self.image_list, wx.IMAGE_LIST_SMALL)

        self.list_ctrl.AppendColumn("", width=40)
        self.list_ctrl.AppendColumn("Student No", width=120)
        self.list_ctrl.AppendColumn("Name", width=250)
        self.list_ctrl.AppendColumn("Module", width=100)
        self.list_ctrl.AppendColumn("Status", width=100)
        self.list_ctrl.AppendColumn("Credits", width=70)
        self.list_ctrl.AppendColumn("Marks", width=70)
        self.list_ctrl.AppendColumn("Grade", width=70)

        self.list_ctrl.Bind(wx.EVT_LEFT_DOWN, self.on_list_left_down)

        main_sizer.Add(self.list_ctrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 40)

        main_sizer.AddSpacer(10)

        # Records label
        self.records_label = wx.StaticText(self, label="")
        main_sizer.Add(self.records_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 40)

        self.SetSizer(main_sizer)

    def _create_checkbox_bitmap(self, checked):
        bmp = wx.Bitmap(16, 16)
        dc = wx.MemoryDC(bmp)
        dc.SetBackground(wx.Brush(self.GetBackgroundColour()))
        dc.Clear()
        dc.SetPen(wx.Pen(wx.Colour(128, 128, 128), 1))
        dc.SetBrush(wx.Brush(wx.WHITE))
        dc.DrawRectangle(2, 2, 12, 12)
        if checked:
            dc.SetPen(wx.Pen(wx.Colour(0, 120, 215), 2))
            dc.DrawLine(4, 8, 7, 11)
            dc.DrawLine(7, 11, 12, 4)
        dc.SelectObject(wx.NullBitmap)
        return bmp

    def load_filter_options(self):
        self.school_filter.Enable(False)
        self.school_filter.SetSelection(0)
        self.school_filter.SetString(0, "Loading...")

        if self.status_bar:
            self.status_bar.show_message("Loading schools...")
        self.filter_worker = LoadFilterOptionsWorker(
            self.repository, self.on_filter_callback
        )
        self.filter_worker.start()

    def on_filter_callback(self, event_type, *args):
        wx.CallAfter(self._handle_filter_event, event_type, *args)

    def _handle_filter_event(self, event_type, *args):
        if event_type == "filters_loaded":
            schools = args[0]
            self.school_filter.Clear()
            self.school_filter.Append("Select School", None)
            for school in schools:
                self.school_filter.Append(str(school.name), school.id)
            self.school_filter.SetSelection(0)
            self.school_filter.Enable(True)
        elif event_type == "filters_error":
            error_msg = args[0]
            self.school_filter.SetString(0, "Select School")
            self.school_filter.Enable(True)
            wx.MessageBox(
                f"Error loading schools: {error_msg}", "Error", wx.OK | wx.ICON_ERROR
            )

        if self.status_bar:
            self.status_bar.clear()

    def on_school_changed(self, event):
        sel = self.school_filter.GetSelection()
        self.selected_school_id = (
            self.school_filter.GetClientData(sel) if sel != wx.NOT_FOUND else None
        )

        # Reset dependent filters
        self.program_filter.Clear()
        self.program_filter.Append("Select Program", None)
        self.program_filter.SetSelection(0)
        self.program_filter.Enable(False)

        self.structure_filter.Clear()
        self.structure_filter.Append("Select Structure", None)
        self.structure_filter.SetSelection(0)
        self.structure_filter.Enable(False)

        self.module_filter.Clear()
        self.module_filter.Append("Select Module", None)
        self.module_filter.SetSelection(0)
        self.module_filter.Enable(False)

        self.semester_filter.Clear()
        self.semester_filter.Append("All Semesters", None)
        self.semester_filter.SetSelection(0)
        self.semester_filter.Enable(False)

        self.add_students_button.Enable(False)
        self.clear_students()

        self.selected_program_id = None
        self.selected_structure_id = None
        self.selected_module_id = None
        self.selected_semester_number = None

        if self.selected_school_id:
            self.load_programs(self.selected_school_id)

    def load_programs(self, school_id):
        self.program_filter.SetString(0, "Loading...")
        if self.status_bar:
            self.status_bar.show_message("Loading programs...")
        self.programs_worker = LoadProgramsWorker(
            self.repository, school_id, self.on_programs_callback
        )
        self.programs_worker.start()

    def on_programs_callback(self, event_type, *args):
        wx.CallAfter(self._handle_programs_event, event_type, *args)

    def _handle_programs_event(self, event_type, *args):
        if event_type == "programs_loaded":
            programs = args[0]
            self.program_filter.Clear()
            self.program_filter.Append("Select Program", None)
            for program in programs:
                self.program_filter.Append(str(program.name), program.id)
            self.program_filter.SetSelection(0)
            self.program_filter.Enable(True)
        elif event_type == "programs_error":
            self.program_filter.SetString(0, "Select Program")
            self.program_filter.Enable(True)

        if self.status_bar:
            self.status_bar.clear()

    def on_program_changed(self, event):
        sel = self.program_filter.GetSelection()
        self.selected_program_id = (
            self.program_filter.GetClientData(sel) if sel != wx.NOT_FOUND else None
        )

        # Reset dependent filters
        self.structure_filter.Clear()
        self.structure_filter.Append("Select Structure", None)
        self.structure_filter.SetSelection(0)
        self.structure_filter.Enable(False)

        self.module_filter.Clear()
        self.module_filter.Append("Select Module", None)
        self.module_filter.SetSelection(0)
        self.module_filter.Enable(False)

        self.semester_filter.Clear()
        self.semester_filter.Append("All Semesters", None)
        self.semester_filter.SetSelection(0)
        self.semester_filter.Enable(False)

        self.add_students_button.Enable(False)
        self.clear_students()

        self.selected_structure_id = None
        self.selected_module_id = None
        self.selected_semester_number = None

        if self.selected_program_id:
            self.load_structures(self.selected_program_id)

    def load_structures(self, program_id):
        self.structure_filter.SetString(0, "Loading...")
        if self.status_bar:
            self.status_bar.show_message("Loading structures...")
        self.structures_worker = LoadStructuresWorker(
            self.repository, program_id, self.on_structures_callback
        )
        self.structures_worker.start()

    def on_structures_callback(self, event_type, *args):
        wx.CallAfter(self._handle_structures_event, event_type, *args)

    def _handle_structures_event(self, event_type, *args):
        if event_type == "structures_loaded":
            structures = args[0]
            self.structure_filter.Clear()
            self.structure_filter.Append("Select Structure", None)
            for structure in structures:
                display = f"{structure.code}" + (
                    f" - {structure.desc}" if structure.desc else ""
                )
                self.structure_filter.Append(display, structure.id)
            self.structure_filter.SetSelection(0)
            self.structure_filter.Enable(True)
        elif event_type == "structures_error":
            self.structure_filter.SetString(0, "Select Structure")
            self.structure_filter.Enable(True)

        if self.status_bar:
            self.status_bar.clear()

    def on_structure_changed(self, event):
        sel = self.structure_filter.GetSelection()
        self.selected_structure_id = (
            self.structure_filter.GetClientData(sel) if sel != wx.NOT_FOUND else None
        )

        # Reset dependent filters
        self.module_filter.Clear()
        self.module_filter.Append("Select Module", None)
        self.module_filter.SetSelection(0)
        self.module_filter.Enable(False)

        self.semester_filter.Clear()
        self.semester_filter.Append("All Semesters", None)
        self.semester_filter.SetSelection(0)
        self.semester_filter.Enable(False)

        self.add_students_button.Enable(False)
        self.clear_students()

        self.selected_module_id = None
        self.selected_semester_number = None

        if self.selected_structure_id:
            self.load_modules(self.selected_structure_id)

    def load_modules(self, structure_id):
        self.module_filter.SetString(0, "Loading...")
        if self.status_bar:
            self.status_bar.show_message("Loading modules...")
        self.modules_worker = LoadModulesWorker(
            self.repository, structure_id, self.on_modules_callback
        )
        self.modules_worker.start()

    def on_modules_callback(self, event_type, *args):
        wx.CallAfter(self._handle_modules_event, event_type, *args)

    def _handle_modules_event(self, event_type, *args):
        if event_type == "modules_loaded":
            modules, semesters = args
            self.module_filter.Clear()
            self.module_filter.Append("Select Module", None)
            for module in modules:
                sem_str = format_semester(module.semester_number, type="short")
                display = f"{module.module_code} - {module.module_name} ({sem_str})"
                self.module_filter.Append(display, module.semester_module_id)
            self.module_filter.SetSelection(0)
            self.module_filter.Enable(True)

            # Populate semester filter
            self.semester_filter.Clear()
            self.semester_filter.Append("All Semesters", None)
            for sem in semesters:
                self.semester_filter.Append(format_semester(sem, type="full"), sem)
            self.semester_filter.SetSelection(0)
            self.semester_filter.Enable(True)
        elif event_type == "modules_error":
            self.module_filter.SetString(0, "Select Module")
            self.module_filter.Enable(True)

        if self.status_bar:
            self.status_bar.clear()

    def on_module_changed(self, event):
        sel = self.module_filter.GetSelection()
        self.selected_module_id = (
            self.module_filter.GetClientData(sel) if sel != wx.NOT_FOUND else None
        )

        self.clear_students()
        self.add_students_button.Enable(self.selected_module_id is not None)

    def on_semester_changed(self, event):
        sel = self.semester_filter.GetSelection()
        self.selected_semester_number = (
            self.semester_filter.GetClientData(sel) if sel != wx.NOT_FOUND else None
        )

    def on_add_students(self, event):
        if not self.selected_module_id or not self.selected_structure_id:
            wx.MessageBox(
                "Please select a module first",
                "Module Required",
                wx.OK | wx.ICON_WARNING,
            )
            return

        self.add_students_button.Enable(False)
        if self.status_bar:
            self.status_bar.show_message("Loading students...")

        self.students_worker = LoadStudentsWorker(
            self.repository,
            self.selected_module_id,
            self.selected_structure_id,
            self.selected_semester_number,
            self.on_students_callback,
        )
        self.students_worker.start()

    def on_students_callback(self, event_type, *args):
        wx.CallAfter(self._handle_students_event, event_type, *args)

    def _handle_students_event(self, event_type, *args):
        self.add_students_button.Enable(True)

        if event_type == "students_loaded":
            students = args[0]
            self.current_students = list(students)
            self.display_students(students)
        elif event_type == "students_error":
            error_msg = args[0]
            wx.MessageBox(
                f"Error loading students: {error_msg}", "Error", wx.OK | wx.ICON_ERROR
            )

        if self.status_bar:
            self.status_bar.clear()

    def display_students(self, students):
        self.list_ctrl.DeleteAllItems()
        self.checked_items.clear()

        for row, student in enumerate(students):
            index = self.list_ctrl.InsertItem(row, "")
            self.list_ctrl.SetItemImage(index, self.unchecked_idx)
            self.list_ctrl.SetItem(index, 1, student.std_no)
            self.list_ctrl.SetItem(index, 2, student.name or "")
            self.list_ctrl.SetItem(index, 3, student.module_code or "")
            self.list_ctrl.SetItem(index, 4, student.status or "")
            self.list_ctrl.SetItem(
                index, 5, str(student.credits) if student.credits else ""
            )
            self.list_ctrl.SetItem(index, 6, student.marks or "")
            self.list_ctrl.SetItem(index, 7, student.grade or "")
            self.list_ctrl.SetItemData(index, row)

        self.update_records_label()
        self.select_all_checkbox.SetValue(False)
        self.update_selection_state()

    def clear_students(self):
        self.list_ctrl.DeleteAllItems()
        self.current_students = []
        self.checked_items.clear()
        self.update_records_label()
        self.update_selection_state()

    def update_records_label(self):
        count = len(self.current_students)
        plural = "s" if count != 1 else ""
        self.records_label.SetLabel(f"{count} Record{plural}")
        self.Layout()

    def on_list_left_down(self, event):
        item, flags, col = self.list_ctrl.HitTestSubItem(event.GetPosition())
        if item != wx.NOT_FOUND and col == 0:
            self.toggle_item_check(item)
        else:
            event.Skip()

    def toggle_item_check(self, item):
        if item in self.checked_items:
            self.checked_items.remove(item)
            self.list_ctrl.SetItemImage(item, self.unchecked_idx)
        else:
            self.checked_items.add(item)
            self.list_ctrl.SetItemImage(item, self.checked_idx)
        self.update_selection_state()

    def on_select_all_changed(self, event):
        should_select_all = self.select_all_checkbox.GetValue()
        item_count = self.list_ctrl.GetItemCount()

        for idx in range(item_count):
            if should_select_all:
                self.checked_items.add(idx)
                self.list_ctrl.SetItemImage(idx, self.checked_idx)
            else:
                self.checked_items.discard(idx)
                self.list_ctrl.SetItemImage(idx, self.unchecked_idx)

        self.update_selection_state()

    def update_selection_state(self):
        selected_count = len(self.checked_items)
        self.selection_label.SetLabel(f"{selected_count} selected")
        self.update_button.Enable(selected_count > 0)

        total_items = self.list_ctrl.GetItemCount()
        should_check_all = total_items > 0 and selected_count == total_items
        if self.select_all_checkbox.GetValue() != should_check_all:
            self.select_all_checkbox.SetValue(should_check_all)

    def get_selected_students(self):
        return [self.current_students[idx] for idx in sorted(self.checked_items)]

    def on_update_module(self, event):
        selected_students = self.get_selected_students()
        if not selected_students:
            wx.MessageBox(
                "Please select at least one student",
                "No Selection",
                wx.OK | wx.ICON_WARNING,
            )
            return

        # Get module info for the dialog (use first selected student's values as defaults)
        first_student = selected_students[0]
        module_info = {
            "module_code": first_student.module_code,
            "module_name": first_student.module_name,
            "status": first_student.status,
            "credits": first_student.credits,
        }

        dialog = BulkModuleFormDialog(
            module_info, parent=self, status_bar=self.status_bar
        )

        if dialog.ShowModal() == wx.ID_OK:
            update_data = dialog.get_updated_data()

            if not update_data:
                dialog.Destroy()
                return

            # Compare update_data against database values to find actual changes
            db_status = first_student.status or ""
            db_credits = str(first_student.credits) if first_student.credits else ""

            actual_changes = {}
            if "status" in update_data and update_data["status"] != db_status:
                actual_changes["status"] = update_data["status"]
            if "credits" in update_data and update_data["credits"] != db_credits:
                actual_changes["credits"] = update_data["credits"]
            if "semester_module_id" in update_data:
                # semester_module_id change is always considered a real change
                actual_changes["semester_module_id"] = update_data["semester_module_id"]

            if not actual_changes:
                wx.MessageBox(
                    "No changes detected. The values are the same as in the database.",
                    "No Changes",
                    wx.OK | wx.ICON_INFORMATION,
                )
                dialog.Destroy()
                return

            # Confirm bulk update with actual changes
            count = len(selected_students)
            message = (
                f"You are about to update {count} student module(s).\n\n"
                f"Changes to apply:\n"
            )
            if "status" in actual_changes:
                message += f"  - Status: {db_status} → {actual_changes['status']}\n"
            if "credits" in actual_changes:
                message += f"  - Credits: {db_credits} → {actual_changes['credits']}\n"
            if "semester_module_id" in actual_changes:
                message += (
                    f"  - Semester Module ID: {actual_changes['semester_module_id']}\n"
                )
            message += "\nDo you want to proceed?"

            confirm_dlg = wx.MessageDialog(
                self,
                message,
                "Confirm Bulk Update",
                wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
            )

            if confirm_dlg.ShowModal() == wx.ID_YES:
                self.update_button.Enable(False)
                self.add_students_button.Enable(False)

                self.update_worker = BulkUpdateWorker(
                    selected_students,
                    update_data,
                    self.sync_service,
                    self.on_update_callback,
                )
                self.update_worker.start()

            confirm_dlg.Destroy()

        dialog.Destroy()

    def on_update_callback(self, event_type, *args):
        wx.CallAfter(self._handle_update_event, event_type, *args)

    def _handle_update_event(self, event_type, *args):
        if event_type == "progress":
            message, current, total = args
            if self.status_bar:
                self.status_bar.show_progress(message, current, total)
        elif event_type == "finished":
            success_count, failed_count = args
            if self.status_bar:
                self.status_bar.clear()
            self.update_button.Enable(True)
            self.add_students_button.Enable(True)

            if failed_count > 0:
                wx.MessageBox(
                    f"Updated {success_count} module(s).\n{failed_count} failed.",
                    "Bulk Update Complete",
                    wx.OK | wx.ICON_INFORMATION,
                )
            else:
                wx.MessageBox(
                    f"Successfully updated {success_count} module(s).",
                    "Bulk Update Complete",
                    wx.OK | wx.ICON_INFORMATION,
                )

            # Refresh the list
            if self.selected_module_id and self.selected_structure_id:
                self.on_add_students(None)
        elif event_type == "error":
            error_msg = args[0]
            wx.MessageBox(error_msg, "Error", wx.OK | wx.ICON_WARNING)
