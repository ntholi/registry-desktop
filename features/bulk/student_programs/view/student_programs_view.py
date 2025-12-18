import threading

import wx

from ..repository import BulkStudentProgramsRepository
from ..service import StudentProgramService
from .update_structure_dialog import UpdateStructureDialog


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


class LoadTermsWorker(threading.Thread):
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
            terms = self.repository.list_terms_for_program(self.program_id)
            self.callback("terms_loaded", terms)
        except Exception as e:
            self.callback("terms_error", str(e))

    def stop(self):
        self.should_stop = True


class LoadStudentsWorker(threading.Thread):
    def __init__(self, repository, program_id, term, callback):
        super().__init__(daemon=True)
        self.repository = repository
        self.program_id = program_id
        self.term = term
        self.callback = callback
        self.should_stop = False

    def run(self):
        if self.should_stop:
            return
        try:
            students = self.repository.fetch_students_by_program_and_term(
                self.program_id,
                self.term,
            )
            self.callback("students_loaded", students)
        except Exception as e:
            self.callback("students_error", str(e))

    def stop(self):
        self.should_stop = True


class BulkUpdateStructureWorker(threading.Thread):
    def __init__(
        self, student_programs, new_structure_id, new_structure_code, service, callback
    ):
        super().__init__(daemon=True)
        self.student_programs = student_programs
        self.new_structure_id = new_structure_id
        self.new_structure_code = new_structure_code
        self.service = service
        self.callback = callback
        self.should_stop = False

    def run(self):
        success_count = 0
        failed_count = 0
        total = len(self.student_programs)

        for idx, student_program in enumerate(self.student_programs):
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

                success, message = self.service.update_student_program_structure(
                    student_program,
                    self.new_structure_id,
                    self.new_structure_code,
                    progress_callback,
                )

                if success:
                    success_count += 1
                else:
                    self.callback(
                        "error",
                        f"Failed to update {student_program.std_no}: {message}",
                    )
                    failed_count += 1

            except Exception as e:
                self.callback(
                    "error",
                    f"Error updating {student_program.std_no}: {str(e)}",
                )
                failed_count += 1

        self.callback("finished", success_count, failed_count)

    def stop(self):
        self.should_stop = True


class StudentProgramsView(wx.Panel):
    def __init__(self, parent, status_bar=None):
        super().__init__(parent)
        self.status_bar = status_bar
        self.repository = BulkStudentProgramsRepository()
        self.service = StudentProgramService(self.repository)

        self.selected_school_id = None
        self.selected_program_id = None
        self.selected_term = None

        self.current_students = []
        self.checked_items = set()

        self.filter_worker = None
        self.programs_worker = None
        self.terms_worker = None
        self.students_worker = None
        self.update_worker = None

        self.init_ui()
        self.load_filter_options()

    def init_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(self, label="Student Programs")
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
        self.school_filter.Append("Select School", None)
        self.school_filter.SetSelection(0)
        self.school_filter.Bind(wx.EVT_CHOICE, self.on_school_changed)
        filters_sizer.Add(self.school_filter, 0, wx.RIGHT, 10)

        self.program_filter = wx.Choice(self)
        self.program_filter.Append("Select Program", None)
        self.program_filter.SetSelection(0)
        self.program_filter.Enable(False)
        self.program_filter.Bind(wx.EVT_CHOICE, self.on_program_changed)
        filters_sizer.Add(self.program_filter, 0, wx.RIGHT, 10)

        self.term_filter = wx.Choice(self)
        self.term_filter.Append("Select Term", None)
        self.term_filter.SetSelection(0)
        self.term_filter.Enable(False)
        self.term_filter.Bind(wx.EVT_CHOICE, self.on_term_changed)
        filters_sizer.Add(self.term_filter, 0, wx.RIGHT, 10)

        filters_sizer.AddStretchSpacer()

        self.update_button = wx.Button(self, label="Update")
        self.update_button.Bind(wx.EVT_BUTTON, self.on_update)
        self.update_button.Enable(False)
        filters_sizer.Add(self.update_button, 0)

        main_sizer.Add(filters_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 40)

        main_sizer.AddSpacer(15)
        line = wx.StaticLine(self)
        main_sizer.Add(line, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 40)
        main_sizer.AddSpacer(15)

        selection_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.select_all_checkbox = wx.CheckBox(self, label="Select All")
        self.select_all_checkbox.Bind(wx.EVT_CHECKBOX, self.on_select_all_changed)
        selection_sizer.Add(self.select_all_checkbox, 0, wx.RIGHT, 10)

        self.selection_label = wx.StaticText(self, label="0 selected")
        selection_sizer.Add(self.selection_label, 0)

        main_sizer.Add(selection_sizer, 0, wx.LEFT | wx.RIGHT, 40)

        main_sizer.AddSpacer(10)

        self.list_ctrl = wx.ListCtrl(self, style=wx.LC_REPORT | wx.BORDER_SIMPLE)

        self.image_list = wx.ImageList(16, 16)
        self.unchecked_idx = self.image_list.Add(self._create_checkbox_bitmap(False))
        self.checked_idx = self.image_list.Add(self._create_checkbox_bitmap(True))
        self.list_ctrl.SetImageList(self.image_list, wx.IMAGE_LIST_SMALL)

        self.list_ctrl.AppendColumn("", width=40)
        self.list_ctrl.AppendColumn("Student No", width=120)
        self.list_ctrl.AppendColumn("Name", width=200)
        self.list_ctrl.AppendColumn("Version", width=120)
        self.list_ctrl.AppendColumn("Start Term", width=100)
        self.list_ctrl.AppendColumn("Stream", width=100)
        self.list_ctrl.AppendColumn("Status", width=100)

        self.list_ctrl.Bind(wx.EVT_LEFT_DOWN, self.on_list_left_down)
        self.list_ctrl.Bind(wx.EVT_RIGHT_UP, self.on_list_right_click)

        main_sizer.Add(self.list_ctrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 40)

        main_sizer.AddSpacer(10)

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

        self.program_filter.Clear()
        self.program_filter.Append("Select Program", None)
        self.program_filter.SetSelection(0)
        self.program_filter.Enable(False)

        self.term_filter.Clear()
        self.term_filter.Append("Select Term", None)
        self.term_filter.SetSelection(0)
        self.term_filter.Enable(False)

        self.clear_students()

        self.selected_program_id = None
        self.selected_term = None

        self.update_update_button_state()

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

        self.term_filter.Clear()
        self.term_filter.Append("Select Term", None)
        self.term_filter.SetSelection(0)
        self.term_filter.Enable(False)

        self.clear_students()

        self.selected_term = None

        self.update_update_button_state()

        if self.selected_program_id:
            self.load_terms(self.selected_program_id)

    def load_terms(self, program_id):
        self.term_filter.SetString(0, "Loading...")
        if self.status_bar:
            self.status_bar.show_message("Loading terms...")
        self.terms_worker = LoadTermsWorker(
            self.repository, program_id, self.on_terms_callback
        )
        self.terms_worker.start()

    def on_terms_callback(self, event_type, *args):
        wx.CallAfter(self._handle_terms_event, event_type, *args)

    def _handle_terms_event(self, event_type, *args):
        if event_type == "terms_loaded":
            terms = args[0]
            self.term_filter.Clear()
            self.term_filter.Append("Select Term", None)
            for term in terms:
                self.term_filter.Append(term, term)
            self.term_filter.SetSelection(0)
            self.term_filter.Enable(True)
        elif event_type == "terms_error":
            self.term_filter.SetString(0, "Select Term")
            self.term_filter.Enable(True)

        if self.status_bar:
            self.status_bar.clear()

    def on_term_changed(self, event):
        sel = self.term_filter.GetSelection()
        self.selected_term = (
            self.term_filter.GetClientData(sel) if sel != wx.NOT_FOUND else None
        )

        self.update_update_button_state()

        if self.selected_program_id and self.selected_term:
            self.load_students()
        else:
            self.clear_students()

    def update_update_button_state(self):
        all_filters_selected = (
            self.selected_school_id is not None
            and self.selected_program_id is not None
            and self.selected_term is not None
        )
        has_selection = len(self.checked_items) > 0
        self.update_button.Enable(all_filters_selected and has_selection)

    def load_students(self):
        if not self.selected_program_id:
            return

        if self.status_bar:
            self.status_bar.show_message("Loading students...")

        self.students_worker = LoadStudentsWorker(
            self.repository,
            self.selected_program_id,
            self.selected_term,
            self.on_students_callback,
        )
        self.students_worker.start()

    def on_students_callback(self, event_type, *args):
        wx.CallAfter(self._handle_students_event, event_type, *args)

    def _handle_students_event(self, event_type, *args):
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
            self.list_ctrl.SetItem(index, 3, student.structure_code or "")
            self.list_ctrl.SetItem(index, 4, student.start_term or "")
            self.list_ctrl.SetItem(index, 5, student.stream or "")
            self.list_ctrl.SetItem(index, 6, student.status or "")
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
        self.update_update_button_state()

        total_items = self.list_ctrl.GetItemCount()
        should_check_all = total_items > 0 and selected_count == total_items
        if self.select_all_checkbox.GetValue() != should_check_all:
            self.select_all_checkbox.SetValue(should_check_all)

    def get_selected_students(self):
        return [self.current_students[idx] for idx in sorted(self.checked_items)]

    def on_update(self, event):
        selected_students = self.get_selected_students()
        if not selected_students:
            wx.MessageBox(
                "Please select at least one student",
                "No Selection",
                wx.OK | wx.ICON_WARNING,
            )
            return

        if self.selected_program_id is None:
            wx.MessageBox(
                "Please select a program first",
                "No Program Selected",
                wx.OK | wx.ICON_WARNING,
            )
            return

        dialog = UpdateStructureDialog(
            len(selected_students),
            self.selected_program_id,
            self.repository,
            parent=self,
        )

        if dialog.ShowModal() == wx.ID_OK:
            selected_structure = dialog.get_selected_structure()

            if not selected_structure:
                dialog.Destroy()
                return

            count = len(selected_students)
            message = (
                f"You are about to update the structure version for {count} student(s) to:\n\n"
                f"Version: {selected_structure.code}"
                + (
                    f"\nDescription: {selected_structure.desc}"
                    if selected_structure.desc
                    else ""
                )
                + "\n\nDo you want to proceed?"
            )

            confirm_dlg = wx.MessageDialog(
                self,
                message,
                "Confirm Bulk Update",
                wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
            )

            if confirm_dlg.ShowModal() == wx.ID_YES:
                self.update_button.Enable(False)

                self.update_worker = BulkUpdateStructureWorker(
                    selected_students,
                    selected_structure.id,
                    selected_structure.code,
                    self.service,
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
            self.update_update_button_state()

            if failed_count > 0:
                wx.MessageBox(
                    f"Updated structure for {success_count} student(s).\n{failed_count} failed.",
                    "Bulk Update Complete",
                    wx.OK | wx.ICON_INFORMATION,
                )
            else:
                wx.MessageBox(
                    f"Successfully updated structure for {success_count} student(s).",
                    "Bulk Update Complete",
                    wx.OK | wx.ICON_INFORMATION,
                )

            if self.selected_program_id and self.selected_term:
                self.load_students()
        elif event_type == "error":
            error_msg = args[0]
            wx.MessageBox(error_msg, "Error", wx.OK | wx.ICON_WARNING)
