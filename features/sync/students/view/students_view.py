import threading
from datetime import datetime

import wx
import wx.dataview as dv

from ..repository import StudentRepository
from ..service import StudentSyncService
from .fetch_options_dialog import FetchOptionsDialog
from .importer import ImporterDialog
from .student_detail_panel import StudentDetailPanel
from .student_form import StudentFormDialog


class FetchStudentsWorker(threading.Thread):
    def __init__(self, student_numbers, sync_service, callback, import_options=None):
        super().__init__(daemon=True)
        self.student_numbers = student_numbers
        self.sync_service = sync_service
        self.callback = callback
        self.import_options = import_options
        self.should_stop = False

    def run(self):
        success_count = 0
        failed_count = 0

        for idx, std_no in enumerate(self.student_numbers):
            if self.should_stop:
                break

            try:

                def progress_callback(message, current, total):
                    overall_progress = idx * 3 + current
                    overall_total = len(self.student_numbers) * 3
                    self.callback("progress", message, overall_progress, overall_total)

                was_updated = self.sync_service.fetch_student(
                    std_no, progress_callback, self.import_options
                )

                if was_updated:
                    success_count += 1
                else:
                    failed_count += 1

            except Exception as e:
                self.callback("error", f"Error pulling student {std_no}: {str(e)}")
                failed_count += 1

        self.callback("finished", success_count, failed_count)

    def stop(self):
        self.should_stop = True


class UpdateStudentsWorker(threading.Thread):
    def __init__(self, student_number, student_data, sync_service, callback):
        super().__init__(daemon=True)
        self.student_number = student_number
        self.student_data = student_data
        self.sync_service = sync_service
        self.callback = callback
        self.should_stop = False
        self.current_step = 0
        self.total_steps = 4

    def emit_progress(self, message: str):
        self.current_step += 1
        self.callback("progress", message, self.current_step, self.total_steps)

    def run(self):
        try:
            if self.should_stop:
                return

            success, message = self.sync_service.push_student(
                self.student_number, self.student_data, self.emit_progress
            )

            self.callback("update_finished", success, message)

        except Exception as e:
            self.callback(
                "error", f"Error updating student {self.student_number}: {str(e)}"
            )
            self.callback("update_finished", False, str(e))

    def stop(self):
        self.should_stop = True


class SearchWorker(threading.Thread):
    def __init__(self, view, callback):
        super().__init__(daemon=True)
        self.view = view
        self.callback = callback
        self.should_stop = False

    def run(self):
        if self.should_stop:
            return
        try:
            students, total = self.view.repository.fetch_students(
                school_id=self.view.selected_school_id,
                program_id=self.view.selected_program_id,
                term=self.view.selected_term,
                semester_number=self.view.selected_semester_number,
                search_query=self.view.search_query,
                page=self.view.current_page,
                page_size=self.view.page_size,
            )
            self.callback("search_finished", students, total)
        except Exception as e:
            self.callback("search_error", str(e))

    def stop(self):
        self.should_stop = True


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
            programs = self.repository.list_programs(None)
            terms = self.repository.list_terms()
            semesters = self.repository.list_semesters()
            self.callback("filters_loaded", schools, programs, terms, semesters)
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


class GetSelectedStudentsWorker(threading.Thread):
    def __init__(self, repository, student_numbers, callback):
        super().__init__(daemon=True)
        self.repository = repository
        self.student_numbers = student_numbers
        self.callback = callback
        self.should_stop = False

    def run(self):
        if self.should_stop:
            return
        try:
            selected = []
            for std_no in self.student_numbers:
                if self.should_stop:
                    break
                students, _ = self.repository.fetch_students(
                    search_query=std_no,
                    page=1,
                    page_size=1,
                )
                if students:
                    student = students[0]
                    selected.append(
                        {
                            "std_no": student.std_no,
                            "name": student.name,
                            "gender": student.gender,
                            "date_of_birth": student.date_of_birth,
                            "phone1": student.phone1,
                        }
                    )
            self.callback("students_data_loaded", selected)
        except Exception as e:
            self.callback("students_data_error", str(e))

    def stop(self):
        self.should_stop = True


class StudentsView(wx.Panel):
    def __init__(self, parent, status_bar=None):
        super().__init__(parent)
        self.status_bar = status_bar
        self.current_page = 1
        self.page_size = 30
        self.total_students = 0
        self.search_query = ""
        self.selected_school_id = None
        self.selected_program_id = None
        self.selected_term = None
        self.selected_semester_number = None
        self.fetch_worker = None
        self.update_worker = None
        self.search_worker = None
        self.filter_worker = None
        self.programs_worker = None
        self.selected_students_worker = None
        self.repository = StudentRepository()
        self.sync_service = StudentSyncService(self.repository)
        self.checked_items = set()
        self.selected_student_item = None
        self.pending_update_callback = None

        self.init_ui()
        self.load_filter_options()
        self.load_students()

    def init_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(self, label="Students")
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

        self.term_filter = wx.Choice(self)
        self.term_filter.Append("All Terms", None)
        self.term_filter.SetSelection(0)
        self.term_filter.Bind(wx.EVT_CHOICE, self.on_filter_changed)
        filters_sizer.Add(self.term_filter, 0, wx.RIGHT, 10)

        self.semester_filter = wx.Choice(self)
        self.semester_filter.Append("All Semesters", None)
        self.semester_filter.SetSelection(0)
        self.semester_filter.Bind(wx.EVT_CHOICE, self.on_filter_changed)
        filters_sizer.Add(self.semester_filter, 0, wx.RIGHT, 10)

        filters_sizer.AddStretchSpacer()

        self.import_button = wx.Button(self, label="Import")
        self.import_button.Bind(wx.EVT_BUTTON, self.on_import_students)
        filters_sizer.Add(self.import_button, 0)

        main_sizer.Add(filters_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 40)

        main_sizer.AddSpacer(20)

        search_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.search_input = wx.SearchCtrl(self, size=wx.Size(400, -1))
        self.search_input.SetDescriptiveText("Search by student number, name...")
        self.search_input.ShowCancelButton(True)
        self.search_input.Bind(wx.EVT_SEARCHCTRL_CANCEL_BTN, self.clear_search)
        search_sizer.Add(self.search_input, 0, wx.RIGHT, 10)

        self.search_button = wx.Button(self, label="Search")
        self.search_button.Bind(wx.EVT_BUTTON, self.perform_search)
        search_sizer.Add(self.search_button, 0, wx.RIGHT, 10)

        search_sizer.AddStretchSpacer()

        self.fetch_button = wx.Button(self, label="Fetch")
        self.fetch_button.Bind(wx.EVT_BUTTON, self.fetch_students)
        self.fetch_button.Enable(False)
        search_sizer.Add(self.fetch_button, 0, wx.RIGHT, 10)

        self.edit_button = wx.Button(self, label="Edit")
        self.edit_button.Bind(wx.EVT_BUTTON, self.update_students)
        self.edit_button.Enable(False)
        search_sizer.Add(self.edit_button, 0)

        main_sizer.Add(search_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 40)

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

        content_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.list_ctrl = wx.ListCtrl(self, style=wx.LC_REPORT | wx.BORDER_SIMPLE)

        self.image_list = wx.ImageList(16, 16)
        self.unchecked_idx = self.image_list.Add(self._create_checkbox_bitmap(False))
        self.checked_idx = self.image_list.Add(self._create_checkbox_bitmap(True))
        self.list_ctrl.SetImageList(self.image_list, wx.IMAGE_LIST_SMALL)

        self.list_ctrl.AppendColumn("", width=40)
        self.list_ctrl.AppendColumn("Student No", width=150)
        self.list_ctrl.AppendColumn("Name", width=250)
        self.list_ctrl.AppendColumn("Gender", width=100)
        self.list_ctrl.AppendColumn("Age", width=60)
        self.list_ctrl.AppendColumn("Faculty", width=80)
        self.list_ctrl.AppendColumn("Program", width=280)
        self.list_ctrl.AppendColumn("Phone", width=150)

        self.list_ctrl.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.on_list_item_clicked)
        self.list_ctrl.Bind(wx.EVT_LEFT_DOWN, self.on_list_left_down)
        self.list_ctrl.Bind(wx.EVT_RIGHT_UP, self.on_list_right_click)
        self.list_ctrl.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_list_item_selected)
        self.list_ctrl.Bind(wx.EVT_LIST_ITEM_DESELECTED, self.on_list_item_deselected)

        content_sizer.Add(self.list_ctrl, 1, wx.EXPAND)

        self.detail_panel = StudentDetailPanel(
            self, self.on_detail_panel_close, self.status_bar
        )
        self.detail_panel.Hide()

        content_sizer.Add(self.detail_panel, 0, wx.EXPAND | wx.LEFT, 10)

        main_sizer.Add(content_sizer, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 40)

        main_sizer.AddSpacer(10)

        pagination_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.records_label = wx.StaticText(self, label="")
        pagination_sizer.Add(self.records_label, 0, wx.ALIGN_CENTER_VERTICAL)

        pagination_sizer.AddStretchSpacer()

        self.prev_button = wx.Button(self, label="Previous")
        self.prev_button.Bind(wx.EVT_BUTTON, self.previous_page)
        self.prev_button.Enable(False)
        pagination_sizer.Add(self.prev_button, 0, wx.RIGHT, 15)

        self.page_label = wx.StaticText(self, label="")
        pagination_sizer.Add(
            self.page_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 15
        )

        self.next_button = wx.Button(self, label="Next")
        self.next_button.Bind(wx.EVT_BUTTON, self.next_page)
        pagination_sizer.Add(self.next_button, 0)

        pagination_sizer.AddStretchSpacer()

        main_sizer.Add(
            pagination_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 40
        )

        self.SetSizer(main_sizer)

    def _create_checkbox_bitmap(self, checked):
        bmp = wx.Bitmap(16, 16)
        dc = wx.MemoryDC(bmp)

        # Fill background
        dc.SetBackground(wx.Brush(self.GetBackgroundColour()))
        dc.Clear()

        # Draw checkbox border
        dc.SetPen(wx.Pen(wx.Colour(128, 128, 128), 1))
        dc.SetBrush(wx.Brush(wx.WHITE))
        dc.DrawRectangle(2, 2, 12, 12)

        # Draw checkmark if checked
        if checked:
            dc.SetPen(wx.Pen(wx.Colour(0, 120, 215), 2))
            dc.DrawLine(4, 8, 7, 11)
            dc.DrawLine(7, 11, 12, 4)

        dc.SelectObject(wx.NullBitmap)
        return bmp

    def _calculate_age(self, date_of_birth):
        if not date_of_birth:
            return ""
        try:
            if isinstance(date_of_birth, str):
                date_of_birth = datetime.fromisoformat(
                    date_of_birth.replace("Z", "+00:00")
                )
            today = datetime.now()
            age = (
                today.year
                - date_of_birth.year
                - ((today.month, today.day) < (date_of_birth.month, date_of_birth.day))
            )
            return str(age)
        except Exception:
            return ""

    def on_list_left_down(self, event):
        item, flags, col = self.list_ctrl.HitTestSubItem(event.GetPosition())

        if item != wx.NOT_FOUND and col == 0:
            self.toggle_item_check(item)
        else:
            event.Skip()

    def on_list_item_clicked(self, event):
        pass

    def on_list_item_selected(self, event):
        item = event.GetIndex()
        if item != wx.NOT_FOUND:
            self.selected_student_item = item
            student_no = self.list_ctrl.GetItemText(item, 1)
            self.show_student_detail(student_no)

    def on_list_item_deselected(self, event):
        if self.detail_panel.IsShown():
            return
        self.selected_student_item = None

    def show_student_detail(self, student_no):
        self.detail_panel.load_student_programs(student_no)
        self.detail_panel.Show()
        self.Layout()

    def on_detail_panel_close(self):
        self.detail_panel.Hide()
        if self.selected_student_item is not None:
            self.list_ctrl.Select(self.selected_student_item, False)
            self.selected_student_item = None
        self.Layout()

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

    def load_filter_options(self):
        self.school_filter.Enable(False)
        self.program_filter.Enable(False)
        self.term_filter.Enable(False)
        self.semester_filter.Enable(False)

        self.school_filter.SetSelection(0)
        self.school_filter.SetString(0, "Loading...")
        self.program_filter.SetSelection(0)
        self.program_filter.SetString(0, "Loading...")
        self.term_filter.SetSelection(0)
        self.term_filter.SetString(0, "Loading...")
        self.semester_filter.SetSelection(0)
        self.semester_filter.SetString(0, "Loading...")

        if self.status_bar:
            self.status_bar.show_message("Loading filters...")
        self.filter_worker = LoadFilterOptionsWorker(
            self.repository, self.on_filter_options_callback
        )
        self.filter_worker.start()

    def load_programs_for_school(self, school_id, trigger_load_students=False):
        self.pending_update_callback = trigger_load_students

        self.program_filter.Enable(False)
        while self.program_filter.GetCount() > 1:
            self.program_filter.Delete(1)
        self.program_filter.SetSelection(0)
        self.program_filter.SetString(0, "Loading...")

        if self.status_bar:
            self.status_bar.show_message("Loading programs...")
        self.programs_worker = LoadProgramsWorker(
            self.repository, school_id, self.on_programs_callback
        )
        self.programs_worker.start()

    def on_school_changed(self, event):
        sel = self.school_filter.GetSelection()
        self.selected_school_id = (
            self.school_filter.GetClientData(sel) if sel != wx.NOT_FOUND else None
        )
        self.term_filter.SetSelection(0)
        self.semester_filter.SetSelection(0)
        self.selected_program_id = None
        self.selected_term = None
        self.selected_semester_number = None
        self.current_page = 1
        self.load_programs_for_school(self.selected_school_id, trigger_load_students=True)

    def on_filter_changed(self, event):
        sel = self.school_filter.GetSelection()
        self.selected_school_id = (
            self.school_filter.GetClientData(sel) if sel != wx.NOT_FOUND else None
        )

        sel = self.program_filter.GetSelection()
        self.selected_program_id = (
            self.program_filter.GetClientData(sel) if sel != wx.NOT_FOUND else None
        )

        sel = self.term_filter.GetSelection()
        self.selected_term = (
            self.term_filter.GetClientData(sel) if sel != wx.NOT_FOUND else None
        )

        sel = self.semester_filter.GetSelection()
        self.selected_semester_number = (
            self.semester_filter.GetClientData(sel) if sel != wx.NOT_FOUND else None
        )

        self.current_page = 1
        if self.status_bar:
            self.status_bar.show_message("Loading students...")
        self.search_worker = SearchWorker(self, self.on_search_callback)
        self.search_worker.start()

    def clear_search(self, event=None):
        self.search_input.SetValue("")
        self.search_query = ""
        self.current_page = 1
        if self.status_bar:
            self.status_bar.show_message("Loading students...")
        self.search_worker = SearchWorker(self, self.on_search_callback)
        self.search_worker.start()

    def perform_search(self, event=None):
        self.search_button.SetLabel("Searching...")
        self.search_button.Enable(False)
        self.search_query = self.search_input.GetValue().strip()
        self.current_page = 1
        if self.status_bar:
            self.status_bar.show_message("Searching students...")
        self.search_worker = SearchWorker(self, self.on_search_callback)
        self.search_worker.start()

    def load_students(self):
        if self.status_bar:
            self.status_bar.show_message("Loading students...")
        self.search_worker = SearchWorker(self, self.on_search_callback)
        self.search_worker.start()

    def update_total_label(self):
        plural = "s" if self.total_students != 1 else ""
        self.records_label.SetLabel(f"{self.total_students} Record{plural}")
        self.Layout()

    def update_pagination_controls(self):
        total_pages = max(
            (self.total_students + self.page_size - 1) // self.page_size, 1
        )
        self.page_label.SetLabel(f"Page {self.current_page} of {total_pages}")

        self.prev_button.Enable(self.current_page > 1)
        self.next_button.Enable(self.current_page < total_pages)

    def previous_page(self, event):
        if self.current_page > 1:
            self.current_page -= 1
            if self.status_bar:
                self.status_bar.show_message("Loading students...")
            self.search_worker = SearchWorker(self, self.on_search_callback)
            self.search_worker.start()

    def next_page(self, event):
        total_pages = (self.total_students + self.page_size - 1) // self.page_size
        if self.current_page < total_pages:
            self.current_page += 1
            if self.status_bar:
                self.status_bar.show_message("Loading students...")
            self.search_worker = SearchWorker(self, self.on_search_callback)
            self.search_worker.start()

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

    def get_selected_count(self):
        return len(self.checked_items)

    def get_selected_student_numbers(self):
        selected = []
        for index in sorted(self.checked_items):
            selected.append(self.list_ctrl.GetItemText(index, 1))
        return selected

    def get_selected_students_data(self, callback):
        selected_numbers = []
        for index in sorted(self.checked_items):
            std_no = self.list_ctrl.GetItemText(index, 1)
            selected_numbers.append(std_no)

        if self.status_bar:
            self.status_bar.show_message("Loading student data...")
        self.selected_students_worker = GetSelectedStudentsWorker(
            self.repository, selected_numbers, callback
        )
        self.selected_students_worker.start()

    def _iterate_selected_indices(self):
        for index in sorted(self.checked_items):
            yield index

    def on_list_selection_changed(self, event):
        self.update_selection_state()
        event.Skip()

    def update_selection_state(self):
        selected_count = self.get_selected_count()
        self.selection_label.SetLabel(f"{selected_count} selected")
        self.fetch_button.Enable(selected_count > 0)
        self.edit_button.Enable(selected_count == 1)
        total_items = self.list_ctrl.GetItemCount()
        should_check_all = total_items > 0 and selected_count == total_items
        if self.select_all_checkbox.GetValue() != should_check_all:
            self.select_all_checkbox.SetValue(should_check_all)

    def fetch_students(self, event):
        selected_students = self.get_selected_student_numbers()
        if not selected_students:
            return

        options_dialog = FetchOptionsDialog(self)
        if options_dialog.ShowModal() == wx.ID_OK:
            import_options = options_dialog.get_import_options()
            options_dialog.Destroy()

            self.fetch_button.Enable(False)
            self.edit_button.Enable(False)

            self.fetch_worker = FetchStudentsWorker(
                selected_students, self.sync_service, self.on_worker_callback, import_options
            )
            self.fetch_worker.start()
        else:
            options_dialog.Destroy()

    def update_students(self, event):
        selected_count = self.get_selected_count()
        if selected_count == 0:
            return
        elif selected_count > 1:
            wx.MessageBox(
                "Please select only one student to update.",
                "Multiple Students",
                wx.OK | wx.ICON_INFORMATION,
            )
            return

        self.fetch_button.Enable(False)
        self.edit_button.Enable(False)
        self.get_selected_students_data(self.on_selected_students_loaded)

    def on_import_students(self, event):
        dialog = ImporterDialog(self, self.sync_service, self.status_bar)
        dialog.ShowModal()
        dialog.Destroy()
        self.load_students()

    def on_worker_callback(self, event_type, *args):
        wx.CallAfter(self._handle_worker_event, event_type, *args)

    def on_import_callback(self, event_type, *args):
        wx.CallAfter(self._handle_import_event, event_type, *args)

    def on_search_callback(self, event_type, *args):
        wx.CallAfter(self._handle_search_event, event_type, *args)

    def on_filter_options_callback(self, event_type, *args):
        wx.CallAfter(self._handle_filter_options_event, event_type, *args)

    def on_programs_callback(self, event_type, *args):
        wx.CallAfter(self._handle_programs_event, event_type, *args)

    def on_selected_students_loaded(self, event_type, *args):
        wx.CallAfter(self._handle_selected_students_event, event_type, *args)

    def _handle_worker_event(self, event_type, *args):
        if event_type == "progress":
            message, current, total = args
            if self.status_bar:
                self.status_bar.show_progress(message, current, total)
        elif event_type == "finished":
            success_count, failed_count = args
            if self.status_bar:
                self.status_bar.clear()
            self.fetch_button.Enable(True)
            self.edit_button.Enable(True)

            if failed_count > 0:
                wx.MessageBox(
                    f"Successfully fetched {success_count} student(s).\n{failed_count} failed.",
                    "Fetch Complete",
                    wx.OK | wx.ICON_INFORMATION,
                )
            else:
                wx.MessageBox(
                    f"Successfully fetched data for {success_count} student(s).",
                    "Fetch Complete",
                    wx.OK | wx.ICON_INFORMATION,
                )

            self.load_students()
        elif event_type == "update_finished":
            success, message = args
            if self.status_bar:
                self.status_bar.clear()
            self.fetch_button.Enable(True)
            self.edit_button.Enable(True)

            if success:
                wx.MessageBox(
                    "Student updated successfully.",
                    "Success",
                    wx.OK | wx.ICON_INFORMATION,
                )
                self.load_students()
            else:
                wx.MessageBox(message, "Update Failed", wx.OK | wx.ICON_ERROR)
        elif event_type == "error":
            error_msg = args[0]
            wx.MessageBox(error_msg, "Error", wx.OK | wx.ICON_WARNING)

    def _handle_import_event(self, event_type, *args):
        if event_type == "progress":
            message, current, total = args
            if self.status_bar:
                self.status_bar.show_progress(message, current, total)
        elif event_type == "finished":
            success_count, failed_count = args
            if self.status_bar:
                self.status_bar.clear()
            self.fetch_button.Enable(True)
            self.edit_button.Enable(True)
            self.import_button.Enable(True)

            if failed_count > 0:
                wx.MessageBox(
                    f"Successfully imported {success_count} student(s).\n{failed_count} failed.",
                    "Import Complete",
                    wx.OK | wx.ICON_INFORMATION,
                )
            else:
                wx.MessageBox(
                    f"Successfully imported {success_count} student(s).",
                    "Import Complete",
                    wx.OK | wx.ICON_INFORMATION,
                )

            self.load_students()
        elif event_type == "error":
            error_msg = args[0]
            if self.status_bar:
                self.status_bar.clear()
            self.fetch_button.Enable(True)
            self.edit_button.Enable(True)
            self.import_button.Enable(True)
            wx.MessageBox(error_msg, "Error", wx.OK | wx.ICON_WARNING)

    def _handle_search_event(self, event_type, *args):
        if event_type == "search_finished":
            students, total = args
            self.total_students = total
            self.list_ctrl.DeleteAllItems()
            self.checked_items.clear()

            for row, student in enumerate(students):
                index = self.list_ctrl.InsertItem(row, "")
                self.list_ctrl.SetItemImage(index, self.unchecked_idx)
                self.list_ctrl.SetItem(index, 1, student.std_no)
                self.list_ctrl.SetItem(index, 2, student.name or "")
                self.list_ctrl.SetItem(index, 3, student.gender or "")
                self.list_ctrl.SetItem(
                    index, 4, self._calculate_age(student.date_of_birth)
                )
                self.list_ctrl.SetItem(index, 5, student.faculty_code or "")
                self.list_ctrl.SetItem(index, 6, student.program_name or "")
                self.list_ctrl.SetItem(index, 7, student.phone1 or "")
                self.list_ctrl.SetItemData(index, row)

            self.update_pagination_controls()
            self.update_total_label()
            self.select_all_checkbox.SetValue(False)
            self.update_selection_state()
        elif event_type == "search_error":
            error_msg = args[0]
            print(f"Error searching students: {error_msg}")
            self.list_ctrl.DeleteAllItems()
            self.checked_items.clear()
            self.page_label.SetLabel("No data available")
            self.records_label.SetLabel("")
            self.update_selection_state()

        if self.status_bar:
            self.status_bar.clear()
        self.search_button.SetLabel("Search")
        self.search_button.Enable(True)

    def _handle_filter_options_event(self, event_type, *args):
        if event_type == "filters_loaded":
            schools, programs, terms, semesters = args

            self.school_filter.SetString(0, "All Schools")
            for school in schools:
                self.school_filter.Append(str(school.name), school.id)
            self.school_filter.SetSelection(0)
            self.school_filter.Enable(True)

            self.program_filter.SetString(0, "All Programs")
            for program in programs:
                self.program_filter.Append(str(program.name), program.id)
            self.program_filter.SetSelection(0)
            self.program_filter.Enable(True)

            self.term_filter.SetString(0, "All Terms")
            for term in terms:
                self.term_filter.Append(str(term), term)
            self.term_filter.SetSelection(0)
            self.term_filter.Enable(True)

            self.semester_filter.SetString(0, "All Semesters")
            for sem in semesters:
                self.semester_filter.Append(f"Semester {sem}", sem)
            self.semester_filter.SetSelection(0)
            self.semester_filter.Enable(True)
        elif event_type == "filters_error":
            error_msg = args[0]
            print(f"Error loading filters: {error_msg}")

            self.school_filter.SetString(0, "All Schools")
            self.school_filter.Enable(True)
            self.program_filter.SetString(0, "All Programs")
            self.program_filter.Enable(True)
            self.term_filter.SetString(0, "All Terms")
            self.term_filter.Enable(True)
            self.semester_filter.SetString(0, "All Semesters")
            self.semester_filter.Enable(True)

        if self.status_bar:
            self.status_bar.clear()

    def _handle_programs_event(self, event_type, *args):
        if event_type == "programs_loaded":
            programs = args[0]
            while self.program_filter.GetCount() > 1:
                self.program_filter.Delete(1)
            self.program_filter.SetString(0, "All Programs")
            for program in programs:
                self.program_filter.Append(str(program.name), program.id)
            self.program_filter.SetSelection(0)
            self.program_filter.Enable(True)

            if self.pending_update_callback:
                self.pending_update_callback = False
                self.load_students()
        elif event_type == "programs_error":
            error_msg = args[0]
            print(f"Error loading programs: {error_msg}")
            self.program_filter.SetString(0, "All Programs")
            self.program_filter.Enable(True)

        if self.status_bar:
            self.status_bar.clear()

    def _handle_selected_students_event(self, event_type, *args):
        if event_type == "students_data_loaded":
            selected_students = args[0]
            if self.status_bar:
                self.status_bar.clear()

            if not selected_students:
                self.fetch_button.Enable(True)
                self.edit_button.Enable(True)
                return

            if len(selected_students) == 1:
                student_data = selected_students[0]
                dialog = StudentFormDialog(student_data, self, self.status_bar)
                if dialog.ShowModal() == wx.ID_OK:
                    updated_data = dialog.get_updated_data()

                    self.update_worker = UpdateStudentsWorker(
                        updated_data["std_no"],
                        {
                            "name": updated_data["name"],
                            "gender": updated_data["gender"],
                            "date_of_birth": updated_data["date_of_birth"],
                            "phone1": updated_data["phone1"],
                        },
                        self.sync_service,
                        self.on_worker_callback,
                    )
                    self.update_worker.start()
                else:
                    self.fetch_button.Enable(True)
                    self.edit_button.Enable(True)
                dialog.Destroy()
            else:
                self.fetch_button.Enable(True)
                self.edit_button.Enable(True)
        elif event_type == "students_data_error":
            error_msg = args[0]
            if self.status_bar:
                self.status_bar.clear()
            self.fetch_button.Enable(True)
            self.edit_button.Enable(True)
            wx.MessageBox(
                f"Error loading student data: {error_msg}",
                "Error",
                wx.OK | wx.ICON_ERROR,
            )
