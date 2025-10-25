import threading

import wx

from .loader_control import LoadableControl
from .registration_detail_panel import RegistrationDetailPanel
from .repository import EnrollmentRequestRepository
from .service import EnrollmentService


class EnrollStudentsWorker(threading.Thread):
    def __init__(
        self,
        service: EnrollmentService,
        request_ids: list[int],
        callback,
    ):
        super().__init__(daemon=True)
        self.service = service
        self.request_ids = request_ids
        self.callback = callback
        self.should_stop = False

    def run(self):
        try:

            def progress_callback(message: str, current: int, total: int):
                if self.should_stop:
                    return
                wx.CallAfter(self.callback, "progress", message, current, total)

            success_count, failed_count = self.service.enroll_students(
                self.request_ids, progress_callback
            )

            wx.CallAfter(
                self.callback,
                "complete",
                success_count,
                failed_count,
            )

        except Exception as e:
            wx.CallAfter(self.callback, "error", str(e))


class RequestsView(wx.Panel):
    def __init__(self, parent, status_bar=None):
        super().__init__(parent)
        self.status_bar = status_bar
        self.current_page = 1
        self.page_size = 30
        self.total_requests = 0
        self.search_query = ""
        self.selected_school_id = None
        self.selected_program_id = None
        self.selected_term_id = None
        self.selected_status = "approved"
        self.search_timer = None
        self.repository = EnrollmentRequestRepository()
        self.service = EnrollmentService(self.repository)
        self.checked_items = set()
        self.selected_request_item = None
        self.enroll_worker = None
        self.detail_loader: LoadableControl | None = None
        self.detail_container: wx.Panel | None = None
        self.active_request_id: int | None = None

        self.init_ui()
        self.load_filter_options()
        self.load_registration_requests()

    def init_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(self, label="Registration Requests")
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

        main_sizer.Add(filters_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 40)

        main_sizer.AddSpacer(20)

        status_filters_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.status_radio_buttons = {}
        statuses = [("all", "All")] + self.repository.list_statuses()
        for idx, (status_code, status_label) in enumerate(statuses):
            style = wx.RB_GROUP if idx == 0 else 0
            radio_btn = wx.RadioButton(self, label=status_label, style=style)
            radio_btn.Bind(
                wx.EVT_RADIOBUTTON,
                lambda evt, code=status_code: self.on_status_filter_changed(evt, code),
            )
            self.status_radio_buttons[status_code] = radio_btn
            status_filters_sizer.Add(radio_btn, 0, wx.RIGHT, 15)
            if status_code == "approved":
                radio_btn.SetValue(True)

        main_sizer.Add(status_filters_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 40)

        main_sizer.AddSpacer(20)

        search_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.search_input = wx.SearchCtrl(self, size=wx.Size(400, -1))
        self.search_input.SetDescriptiveText(
            "Search by student number, name, sponsor..."
        )
        self.search_input.Bind(wx.EVT_TEXT, self.on_search_changed)
        search_sizer.Add(self.search_input, 0, wx.RIGHT, 10)

        self.clear_search_button = wx.Button(self, label="Clear")
        self.clear_search_button.Bind(wx.EVT_BUTTON, self.clear_search)
        self.clear_search_button.Enable(False)
        search_sizer.Add(self.clear_search_button, 0, wx.RIGHT, 10)

        search_sizer.AddStretchSpacer()

        self.enroll_button = wx.Button(self, label="Enroll")
        self.enroll_button.Bind(wx.EVT_BUTTON, self.enroll_students)
        self.enroll_button.Enable(False)
        search_sizer.Add(self.enroll_button, 0)

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
        self.list_ctrl.AppendColumn("Student No", width=120)
        self.list_ctrl.AppendColumn("Student Name", width=200)
        self.list_ctrl.AppendColumn("Sponsor", width=150)
        self.list_ctrl.AppendColumn("Term", width=100)
        self.list_ctrl.AppendColumn("Semester", width=100)
        self.list_ctrl.AppendColumn("School", width=100)
        self.list_ctrl.AppendColumn("Program", width=250)
        self.list_ctrl.AppendColumn("Modules", width=80)
        self.list_ctrl.AppendColumn("Status", width=100)

        self.list_ctrl.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.on_list_item_clicked)
        self.list_ctrl.Bind(wx.EVT_LEFT_DOWN, self.on_list_left_down)
        self.list_ctrl.Bind(wx.EVT_RIGHT_UP, self.on_list_right_click)
        self.list_ctrl.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_list_item_selected)
        self.list_ctrl.Bind(wx.EVT_LIST_ITEM_DESELECTED, self.on_list_item_deselected)

        content_sizer.Add(self.list_ctrl, 1, wx.EXPAND)

        self.detail_loader = LoadableControl(self, self.on_detail_load_complete)
        self.detail_container = self.detail_loader.get_container()
        self.detail_container.SetMinSize(wx.Size(550, -1))

        self.detail_panel = RegistrationDetailPanel(
            self.detail_container, self.on_detail_panel_close, self.status_bar
        )
        self.detail_loader.set_content_panel(self.detail_panel)
        self.detail_container.Hide()

        content_sizer.Add(self.detail_container, 0, wx.EXPAND | wx.LEFT, 10)

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
            self.selected_request_item = item
            data = self.list_ctrl.GetItemData(item)
            request_id = None
            if data is not None:
                try:
                    request_id = int(data)
                except Exception:
                    request_id = None

            if request_id is None:
                for col in range(self.list_ctrl.GetColumnCount()):
                    txt = self.list_ctrl.GetItemText(item, col)
                    if txt:
                        parts = txt.split("#")
                        try:
                            request_id = int(parts[0])
                            break
                        except Exception:
                            continue

            if request_id is None:
                return

            self.show_request_detail(request_id)

    def on_list_item_deselected(self, event):
        if self.detail_panel.IsShown():
            return
        self.selected_request_item = None

    def show_request_detail(self, request_id: int):
        self.active_request_id = request_id

        if self.detail_container and not self.detail_container.IsShown():
            self.detail_container.Show()

        def load_data():
            details = self.repository.get_registration_request_details(request_id)
            if not details:
                raise ValueError("Registration request not found.")
            modules = self.repository.get_requested_modules(request_id)
            return {
                "request_id": request_id,
                "details": details,
                "modules": modules,
            }

        if self.detail_loader:
            self.detail_loader.load_async(
                load_data, "Loading registration details..."
            )

        self.Layout()

    def on_detail_panel_close(self):
        self.active_request_id = None
        if self.detail_panel:
            self.detail_panel.Hide()
        if self.detail_container and self.detail_container.IsShown():
            self.detail_container.Hide()
        if self.selected_request_item is not None:
            self.list_ctrl.Select(self.selected_request_item, False)
            self.selected_request_item = None
        self.Layout()

    def on_detail_load_complete(self, success: bool, data):
        if not success:
            error_message = data if isinstance(data, str) else "Unable to load details."
            wx.MessageBox(
                f"Error loading registration request:\n\n{error_message}",
                "Error",
                wx.OK | wx.ICON_ERROR,
            )
            if self.detail_container and self.detail_container.IsShown():
                self.detail_container.Hide()
                self.Layout()
            return

        if not isinstance(data, dict):
            return

        request_id = data.get("request_id")
        if request_id is None or request_id != self.active_request_id:
            return

        details = data.get("details")
        modules = data.get("modules") or []

        if not details:
            if self.detail_container and self.detail_container.IsShown():
                self.detail_container.Hide()
                self.Layout()
            return

        self.detail_panel.populate_from_data(request_id, details, modules)
        if self.detail_panel and not self.detail_panel.IsShown():
            self.detail_panel.Show()
        if self.detail_container and not self.detail_container.IsShown():
            self.detail_container.Show()
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
        try:
            schools = self.repository.list_active_schools()
            for school in schools:
                self.school_filter.Append(str(school.name), school.id)

            self.load_programs_for_school(None)

            terms = self.repository.list_terms()
            for term in terms:
                self.term_filter.Append(str(term.name), term.id)

        except Exception as e:
            print(f"Error loading filter options: {str(e)}")

    def load_programs_for_school(self, school_id):
        try:
            while self.program_filter.GetCount() > 1:
                self.program_filter.Delete(1)

            programs = self.repository.list_programs(school_id)

            for program in programs:
                self.program_filter.Append(str(program.name), program.id)
        except Exception as e:
            print(f"Error loading programs: {str(e)}")

    def on_school_changed(self, event):
        sel = self.school_filter.GetSelection()
        self.selected_school_id = (
            self.school_filter.GetClientData(sel) if sel != wx.NOT_FOUND else None
        )
        self.load_programs_for_school(self.selected_school_id)
        self.program_filter.SetSelection(0)
        self.selected_program_id = None
        self.current_page = 1
        self.load_registration_requests()

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
        self.selected_term_id = (
            self.term_filter.GetClientData(sel) if sel != wx.NOT_FOUND else None
        )

        self.current_page = 1
        self.load_registration_requests()

    def on_status_filter_changed(self, event, status_code):
        self.selected_status = None if status_code == "all" else status_code
        self.current_page = 1
        self.load_registration_requests()

    def on_search_changed(self, event):
        text = self.search_input.GetValue()
        self.clear_search_button.Enable(bool(text))
        if self.search_timer:
            self.search_timer.Stop()
        self.search_timer = wx.CallLater(500, self.perform_search)

    def clear_search(self, event):
        self.search_input.SetValue("")
        self.search_query = ""
        self.current_page = 1
        self.load_registration_requests()

    def perform_search(self):
        self.search_query = self.search_input.GetValue().strip()
        self.current_page = 1
        self.load_registration_requests()

    def load_registration_requests(self):
        try:
            requests, total = self.repository.fetch_registration_requests(
                school_id=self.selected_school_id,
                program_id=self.selected_program_id,
                term_id=self.selected_term_id,
                status=self.selected_status,
                search_query=self.search_query,
                page=self.current_page,
                page_size=self.page_size,
            )

            self.total_requests = total
            self.list_ctrl.DeleteAllItems()
            self.checked_items.clear()

            for row, request in enumerate(requests):
                index = self.list_ctrl.InsertItem(row, "")
                self.list_ctrl.SetItemImage(index, self.unchecked_idx)
                self.list_ctrl.SetItemData(index, request.id)
                self.list_ctrl.SetItem(index, 1, request.std_no)
                self.list_ctrl.SetItem(index, 2, request.student_name or "")
                self.list_ctrl.SetItem(index, 3, request.sponsor_name or "")
                self.list_ctrl.SetItem(index, 4, request.term_name or "")
                self.list_ctrl.SetItem(
                    index,
                    5,
                    f"{request.semester_number} ({request.semester_status})",
                )
                self.list_ctrl.SetItem(index, 6, request.school_name or "")
                self.list_ctrl.SetItem(index, 7, request.program_name or "")
                self.list_ctrl.SetItem(index, 8, str(request.module_count))
                self.list_ctrl.SetItem(index, 9, request.status.upper())

            self.update_pagination_controls()
            self.update_total_label()
            self.select_all_checkbox.SetValue(False)
            self.update_selection_state()

        except Exception as e:
            print(f"Error loading registration requests: {str(e)}")
            self.list_ctrl.DeleteAllItems()
            self.checked_items.clear()
            self.page_label.SetLabel("No data available")
            self.records_label.SetLabel("")
            self.update_selection_state()

    def update_total_label(self):
        plural = "s" if self.total_requests != 1 else ""
        self.records_label.SetLabel(f"{self.total_requests} Record{plural}")
        self.Layout()

    def update_pagination_controls(self):
        total_pages = max(
            (self.total_requests + self.page_size - 1) // self.page_size, 1
        )
        self.page_label.SetLabel(f"Page {self.current_page} of {total_pages}")

        self.prev_button.Enable(self.current_page > 1)
        self.next_button.Enable(self.current_page < total_pages)

    def previous_page(self, event):
        if self.current_page > 1:
            self.current_page -= 1
            self.load_registration_requests()

    def next_page(self, event):
        total_pages = (self.total_requests + self.page_size - 1) // self.page_size
        if self.current_page < total_pages:
            self.current_page += 1
            self.load_registration_requests()

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

    def get_selected_request_ids(self):
        selected = []
        for index in sorted(self.checked_items):
            request_id = self.list_ctrl.GetItemData(index)
            selected.append(request_id)
        return selected

    def update_selection_state(self):
        selected_count = self.get_selected_count()
        self.selection_label.SetLabel(f"{selected_count} selected")
        self.enroll_button.Enable(selected_count > 0)
        total_items = self.list_ctrl.GetItemCount()
        should_check_all = total_items > 0 and selected_count == total_items
        if self.select_all_checkbox.GetValue() != should_check_all:
            self.select_all_checkbox.SetValue(should_check_all)

    def enroll_students(self, event):
        selected_requests = self.get_selected_request_ids()
        if not selected_requests:
            return

        if self.enroll_worker and self.enroll_worker.is_alive():
            wx.MessageBox(
                "An enrollment operation is already in progress. Please wait for it to complete.",
                "Operation in Progress",
                wx.OK | wx.ICON_INFORMATION,
            )
            return

        clearance_issues = self.service.check_clearances_for_requests(selected_requests)
        if clearance_issues:
            wx.MessageBox(
                f"Cannot enroll students due to incomplete clearances:\n\n{clearance_issues}",
                "Clearance Required",
                wx.OK | wx.ICON_WARNING,
            )
            return

        dlg = wx.MessageDialog(
            self,
            f"Enroll {len(selected_requests)} student(s)?\n\nThis will process their registration requests and enroll them in the requested modules.",
            "Confirm Enrollment",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
        )

        if dlg.ShowModal() != wx.ID_YES:
            dlg.Destroy()
            return
        dlg.Destroy()

        self.enroll_button.Enable(False)

        self.enroll_worker = EnrollStudentsWorker(
            self.service, selected_requests, self.on_enroll_progress
        )
        self.enroll_worker.start()

    def on_enroll_progress(self, event_type, *args):
        if event_type == "progress":
            message, current, total = args
            if self.status_bar:
                self.status_bar.show_progress(message, current, total)

        elif event_type == "complete":
            success_count, failed_count = args
            if self.status_bar:
                self.status_bar.clear()

            result_message = f"Enrollment complete!\n\n"
            result_message += f"Successfully enrolled: {success_count}\n"
            result_message += f"Failed: {failed_count}"

            wx.MessageBox(
                result_message,
                "Enrollment Complete",
                wx.OK | (wx.ICON_INFORMATION if failed_count == 0 else wx.ICON_WARNING),
            )

            self.enroll_button.Enable(True)
            self.load_registration_requests()

        elif event_type == "error":
            error_message = args[0]
            if self.status_bar:
                self.status_bar.clear()

            wx.MessageBox(
                f"An error occurred during enrollment:\n\n{error_message}",
                "Enrollment Error",
                wx.OK | wx.ICON_ERROR,
            )

            self.enroll_button.Enable(True)
