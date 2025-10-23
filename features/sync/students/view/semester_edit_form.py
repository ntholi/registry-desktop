import threading

import wx

from base import get_logger
from features.sync.students.repository import StudentRepository
from features.sync.students.service import StudentSyncService

logger = get_logger(__name__)


class SemesterEditFormDialog(wx.Dialog):
    def __init__(self, student_semester_id, parent=None, status_bar=None):
        super().__init__(
            parent,
            title="Edit Semester",
            size=wx.Size(500, 300),
            style=wx.DEFAULT_DIALOG_STYLE,
        )
        self.student_semester_id = student_semester_id
        self.status_bar = status_bar
        self.repository = StudentRepository()
        self.service = StudentSyncService(self.repository)
        self.push_worker = None
        self.structure_id = None
        self.student_program_id = None

        self.load_semester_data()
        self.init_ui()
        self.Centre()

    def load_semester_data(self):
        try:
            semester_data = self.repository.get_student_semester_by_id(
                self.student_semester_id
            )
            if semester_data:
                self.structure_id = semester_data.get("structure_id")
                self.student_program_id = semester_data.get("student_program_id")
                self.current_semester_number = semester_data.get("semester_number")
                self.current_status = semester_data.get("status")
        except Exception as e:
            logger.error(f"Error loading semester data: {str(e)}")
            self.structure_id = None
            self.student_program_id = None
            self.current_semester_number = None
            self.current_status = None

    def init_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        form_panel = wx.Panel(self)
        form_sizer = wx.FlexGridSizer(2, 2, 10, 10)
        form_sizer.AddGrowableCol(1)

        semester_number_label = wx.StaticText(form_panel, label="Semester:")
        self.semester_number_combo = wx.ComboBox(
            form_panel, style=wx.CB_READONLY, size=wx.Size(200, -1)
        )
        self.populate_semesters()
        form_sizer.Add(
            semester_number_label,
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT | wx.ALL,
            5,
        )
        form_sizer.Add(self.semester_number_combo, 0, wx.EXPAND | wx.ALL, 5)

        status_label = wx.StaticText(form_panel, label="Status:")
        self.status_combo = wx.ComboBox(
            form_panel, style=wx.CB_READONLY, size=wx.Size(200, -1)
        )
        self.status_combo.Append("Active", "Active")
        self.status_combo.Append("Repeat", "Repeat")

        if self.current_status == "Active":
            self.status_combo.SetSelection(0)
        elif self.current_status == "Repeat":
            self.status_combo.SetSelection(1)
        else:
            self.status_combo.SetSelection(0)

        form_sizer.Add(
            status_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT | wx.ALL, 5
        )
        form_sizer.Add(self.status_combo, 0, wx.EXPAND | wx.ALL, 5)

        form_panel.SetSizer(form_sizer)
        main_sizer.Add(form_panel, 1, wx.EXPAND | wx.ALL, 10)

        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.AddStretchSpacer()

        cancel_button = wx.Button(self, wx.ID_CANCEL, "Cancel")
        button_sizer.Add(cancel_button, 0, wx.ALL, 5)

        save_button = wx.Button(self, wx.ID_OK, "Save")
        save_button.Bind(wx.EVT_BUTTON, self.on_save)
        button_sizer.Add(save_button, 0, wx.ALL, 5)

        main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 5)

        self.SetSizer(main_sizer)

    def populate_semesters(self):
        try:
            if not self.structure_id:
                logger.warning("No structure_id available to load semesters")
                return

            semesters = self.repository.get_structure_semesters(self.structure_id)
            for semester in semesters:
                display_text = f"{semester.semester_number:02d} {semester.name}"
                self.semester_number_combo.Append(
                    display_text, (semester.id, semester.semester_number)
                )

            if semesters and self.current_semester_number:
                for i in range(self.semester_number_combo.GetCount()):
                    semester_data = self.semester_number_combo.GetClientData(i)
                    if (
                        semester_data
                        and semester_data[1] == self.current_semester_number
                    ):
                        self.semester_number_combo.SetSelection(i)
                        break
            elif semesters:
                self.semester_number_combo.SetSelection(0)
        except Exception as e:
            logger.error(f"Error populating semesters: {str(e)}")

    def on_save(self, event):
        semester_idx = self.semester_number_combo.GetSelection()
        status = self.status_combo.GetStringSelection()

        if semester_idx == wx.NOT_FOUND:
            wx.MessageBox(
                "Please select a semester",
                "Validation Error",
                wx.OK | wx.ICON_WARNING,
            )
            return

        semester_data = self.semester_number_combo.GetClientData(semester_idx)
        structure_semester_id, semester_number = semester_data

        if not status:
            wx.MessageBox(
                "Please select a status", "Validation Error", wx.OK | wx.ICON_WARNING
            )
            return

        data = {
            "student_semester_id": self.student_semester_id,
            "structure_semester_id": structure_semester_id,
            "semester_number": semester_number,
            "status": status,
        }

        if self.push_worker and self.push_worker.is_alive():
            wx.MessageBox(
                "Another operation is in progress. Please wait.",
                "Operation in Progress",
                wx.OK | wx.ICON_INFORMATION,
            )
            return

        self.push_worker = PushSemesterEditWorker(
            data, self.service, self.push_callback
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
                    "Semester updated successfully",
                    "Success",
                    wx.OK | wx.ICON_INFORMATION,
                )
                wx.CallAfter(self.EndModal, wx.ID_OK)
            else:
                wx.CallAfter(
                    wx.MessageBox,
                    f"Failed to update semester: {message}",
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


class PushSemesterEditWorker(threading.Thread):
    def __init__(self, data, service, callback):
        super().__init__(daemon=True)
        self.data = data
        self.service = service
        self.callback = callback

    def run(self):
        try:
            self.callback("progress", "Updating semester in CMS...")
            success, message = self.service.update_semester(
                self.data, progress_callback=lambda msg: self.callback("progress", msg)
            )
            self.callback("complete", success, message)
        except Exception as e:
            logger.error(f"Error in PushSemesterEditWorker: {str(e)}")
            self.callback("error", str(e))
