import threading

import wx

from ..repository import StudentRepository
from ..service import StudentSyncService
from .module_form import ModuleFormDialog


class StudentDetailPanel(wx.Panel):
    def __init__(self, parent, on_close_callback, status_bar=None):
        super().__init__(parent)
        self.on_close_callback = on_close_callback
        self.status_bar = status_bar
        self.repository = StudentRepository()
        self.service = StudentSyncService(self.repository)
        self.current_student_no = None
        self.current_semesters = []
        self.current_modules = []
        self.push_worker = None

        self.init_ui()

    def init_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        top_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.program_combobox = wx.ComboBox(
            self, style=wx.CB_READONLY, size=wx.Size(400, -1)
        )
        self.program_combobox.Bind(wx.EVT_COMBOBOX, self.on_program_selected)
        top_sizer.Add(self.program_combobox, 0, wx.RIGHT, 10)

        top_sizer.AddStretchSpacer()

        self.close_button = wx.Button(self, label="Close", size=wx.Size(80, -1))
        self.close_button.Bind(wx.EVT_BUTTON, self.on_close)
        top_sizer.Add(self.close_button, 0)

        main_sizer.Add(top_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)

        main_sizer.AddSpacer(15)

        semesters_label = wx.StaticText(self, label="Semesters")
        font = semesters_label.GetFont()
        font.PointSize = 10
        font = font.Bold()
        semesters_label.SetFont(font)
        main_sizer.Add(semesters_label, 0, wx.LEFT | wx.RIGHT, 20)

        main_sizer.AddSpacer(10)

        self.semesters_list = wx.ListCtrl(
            self, style=wx.LC_REPORT | wx.BORDER_SIMPLE, size=wx.Size(-1, 145)
        )
        self.semesters_list.AppendColumn("Term", width=100)
        self.semesters_list.AppendColumn("Semester", width=80)
        self.semesters_list.AppendColumn("Status", width=100)
        self.semesters_list.AppendColumn("", width=60)
        self.semesters_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_semester_selected)
        self.semesters_list.Bind(wx.EVT_LEFT_DOWN, self.on_semesters_left_click)

        main_sizer.Add(self.semesters_list, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)

        main_sizer.AddSpacer(20)

        modules_label = wx.StaticText(self, label="Modules")
        font = modules_label.GetFont()
        font.PointSize = 10
        font = font.Bold()
        modules_label.SetFont(font)
        main_sizer.Add(modules_label, 0, wx.LEFT | wx.RIGHT, 20)

        main_sizer.AddSpacer(10)

        self.modules_list = wx.ListCtrl(
            self, style=wx.LC_REPORT | wx.BORDER_SIMPLE, size=wx.Size(-1, 300)
        )
        self.modules_list.AppendColumn("Code", width=100)
        self.modules_list.AppendColumn("Name", width=200)
        self.modules_list.AppendColumn("Status", width=100)
        self.modules_list.AppendColumn("Marks", width=70)
        self.modules_list.AppendColumn("Grade", width=70)
        self.modules_list.AppendColumn("", width=60)
        self.modules_list.Bind(wx.EVT_LEFT_DOWN, self.on_modules_left_click)

        main_sizer.Add(self.modules_list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)

        main_sizer.AddSpacer(20)

        self.SetSizer(main_sizer)

    def load_student_programs(self, student_no):
        self.current_student_no = student_no
        self.program_combobox.Clear()

        try:
            programs = self.repository.get_student_programs(student_no)

            if not programs:
                self.program_combobox.Append("No programs found", None)
                self.program_combobox.SetSelection(0)
                self.program_combobox.Enable(False)
                return

            self.program_combobox.Enable(True)
            for program in programs:
                display_text = self._format_program_display(program)
                self.program_combobox.Append(display_text, program)

            if programs:
                self.program_combobox.SetSelection(0)
                self.load_program_data()

        except Exception as e:
            print(f"Error loading student programs: {str(e)}")
            self.program_combobox.Append("Error loading programs", None)
            self.program_combobox.SetSelection(0)
            self.program_combobox.Enable(False)

    def on_program_selected(self, event):
        self.load_program_data()

    def load_program_data(self):
        program = self.get_selected_program()
        if not program or not hasattr(program, "id"):
            self.clear_tables()
            return

        student_program_id = program.id
        self.load_semesters(student_program_id)

    def load_semesters(self, student_program_id):
        self.semesters_list.DeleteAllItems()
        self.modules_list.DeleteAllItems()
        self.current_semesters = []

        try:
            semesters = self.repository.get_student_semesters(student_program_id)
            self.current_semesters = list(semesters)

            for row, semester in enumerate(semesters):
                index = self.semesters_list.InsertItem(row, str(semester.term or ""))
                self.semesters_list.SetItem(
                    index, 1, str(semester.semester_number or "")
                )
                self.semesters_list.SetItem(index, 2, str(semester.status or ""))
                self.semesters_list.SetItem(index, 3, "✎ Edit")

            if semesters:
                self.semesters_list.Select(0)
                self.load_modules_for_semester(semesters[0].id)

        except Exception as e:
            print(f"Error loading semesters: {str(e)}")

    def on_semester_selected(self, event):
        item = event.GetIndex()
        if item != wx.NOT_FOUND and item < len(self.current_semesters):
            semester = self.current_semesters[item]
            self.load_modules_for_semester(semester.id)

    def load_modules_for_semester(self, student_semester_id):
        self.modules_list.DeleteAllItems()
        self.current_modules = []

        try:
            modules = self.repository.get_semester_modules(student_semester_id)
            self.current_modules = list(modules)

            for row, module in enumerate(modules):
                index = self.modules_list.InsertItem(row, str(module.module_code or ""))
                self.modules_list.SetItem(index, 1, str(module.module_name or ""))
                self.modules_list.SetItem(index, 2, str(module.status or ""))
                self.modules_list.SetItem(index, 3, str(module.marks or ""))
                self.modules_list.SetItem(index, 4, str(module.grade or ""))
                self.modules_list.SetItem(index, 5, "✎ Edit")

        except Exception as e:
            print(f"Error loading modules: {str(e)}")

    def on_semesters_left_click(self, event):
        item, flags, col = self.semesters_list.HitTestSubItem(event.GetPosition())
        if item != wx.NOT_FOUND and col == 3:
            if item < len(self.current_semesters):
                semester = self.current_semesters[item]
                self.on_semester_edit_clicked(semester)
        else:
            event.Skip()

    def on_semester_edit_clicked(self, semester):
        wx.MessageBox(
            f"Edit semester: {semester.term} - Semester {semester.semester_number}",
            "Edit Semester",
            wx.OK | wx.ICON_INFORMATION,
        )

    def on_modules_left_click(self, event):
        item, flags, col = self.modules_list.HitTestSubItem(event.GetPosition())
        if item != wx.NOT_FOUND and col == 5:
            if item < len(self.current_modules):
                module = self.current_modules[item]
                self.on_module_edit_clicked(module)
        else:
            event.Skip()

    def on_module_edit_clicked(self, module):
        selected_semester_index = self.semesters_list.GetFirstSelected()
        if selected_semester_index == wx.NOT_FOUND or selected_semester_index >= len(
            self.current_semesters
        ):
            wx.MessageBox(
                "Please select a semester first",
                "No Semester Selected",
                wx.OK | wx.ICON_WARNING,
            )
            return

        current_semester = self.current_semesters[selected_semester_index]

        module_data = {
            "id": module.id,
            "module_code": module.module_code,
            "module_name": module.module_name,
            "status": module.status,
            "credits": module.credits if hasattr(module, "credits") else "",
            "marks": module.marks,
            "grade": module.grade,
            "student_semester_id": current_semester.id,
        }

        dialog = ModuleFormDialog(module_data, parent=self, status_bar=self.status_bar)

        if dialog.ShowModal() == wx.ID_OK:
            updated_data = dialog.get_updated_data()
            updated_data["student_semester_id"] = current_semester.id

            if self.push_worker and self.push_worker.is_alive():
                wx.MessageBox(
                    "Another push operation is in progress. Please wait.",
                    "Operation in Progress",
                    wx.OK | wx.ICON_INFORMATION,
                )
                dialog.Destroy()
                return

            self.push_worker = PushModuleWorker(
                updated_data, self.service, self.push_callback
            )
            self.push_worker.start()

        dialog.Destroy()

    def clear_tables(self):
        self.semesters_list.DeleteAllItems()
        self.modules_list.DeleteAllItems()

    def _format_program_display(self, program):
        parts = []

        if hasattr(program, "program_name") and program.program_name:
            parts.append(program.program_name)

        if hasattr(program, "status") and program.status:
            parts.append(f"({program.status})")

        return " ".join(parts) if parts else "Unknown Program"

    def get_selected_program(self):
        selection = self.program_combobox.GetSelection()
        if selection != wx.NOT_FOUND:
            return self.program_combobox.GetClientData(selection)
        return None

    def push_callback(self, event_type, *args):
        if event_type == "progress":
            message = args[0] if args else ""
            if self.status_bar:
                wx.CallAfter(self.status_bar.show_message, message)
        elif event_type == "complete":
            success, message = args if len(args) >= 2 else (False, "Unknown error")
            if self.status_bar:
                wx.CallAfter(self.status_bar.clear)

            if success:
                wx.CallAfter(
                    wx.MessageBox,
                    message,
                    "Success",
                    wx.OK | wx.ICON_INFORMATION,
                )
                wx.CallAfter(self.refresh_current_view)
            else:
                wx.CallAfter(
                    wx.MessageBox,
                    f"Error: {message}",
                    "Push Failed",
                    wx.OK | wx.ICON_ERROR,
                )

    def refresh_current_view(self):
        if self.current_semesters:
            selected_item = self.semesters_list.GetFirstSelected()
            if selected_item != wx.NOT_FOUND and selected_item < len(
                self.current_semesters
            ):
                semester = self.current_semesters[selected_item]
                self.load_modules_for_semester(semester.id)

    def on_close(self, event):
        if self.on_close_callback:
            self.on_close_callback()


class PushModuleWorker(threading.Thread):
    def __init__(self, module_data, service, callback):
        super().__init__(daemon=True)
        self.module_data = module_data
        self.service = service
        self.callback = callback

    def run(self):
        def progress_callback(message):
            self.callback("progress", message)

        try:
            std_module_id = int(self.module_data["id"])
            success, message = self.service.push_module(
                std_module_id, self.module_data, progress_callback
            )
            self.callback("complete", success, message)
        except Exception as e:
            self.callback("complete", False, str(e))
