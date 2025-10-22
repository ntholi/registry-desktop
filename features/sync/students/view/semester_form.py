import threading
from datetime import datetime

import wx

from base import get_logger
from base.widgets.date_picker import DatePickerCtrl
from features.sync.students.repository import StudentRepository
from features.sync.students.service import StudentSyncService

logger = get_logger(__name__)


class SemesterFormDialog(wx.Dialog):
    def __init__(self, student_program_id, parent=None, status_bar=None):
        super().__init__(
            parent,
            title="Add Semester",
            size=wx.Size(500, 400),
            style=wx.DEFAULT_DIALOG_STYLE,
        )
        self.student_program_id = student_program_id
        self.status_bar = status_bar
        self.repository = StudentRepository()
        self.service = StudentSyncService(self.repository)
        self.push_worker = None
        self.structure_id = None

        self.load_program_structure()
        self.init_ui()
        self.Centre()

    def load_program_structure(self):
        try:
            program_details = self.repository.get_student_program_details_by_id(
                self.student_program_id
            )
            if program_details:
                self.structure_id = program_details.get("structure_id")
        except Exception as e:
            logger.error(f"Error loading program structure: {str(e)}")
            self.structure_id = None

    def init_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        form_panel = wx.Panel(self)
        form_sizer = wx.FlexGridSizer(5, 2, 10, 10)
        form_sizer.AddGrowableCol(1)

        term_label = wx.StaticText(form_panel, label="Term:")
        self.term_combo = wx.ComboBox(
            form_panel, style=wx.CB_READONLY, size=wx.Size(200, -1)
        )
        self.populate_terms()
        form_sizer.Add(
            term_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT | wx.ALL, 5
        )
        form_sizer.Add(self.term_combo, 0, wx.EXPAND | wx.ALL, 5)

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
        self.status_combo.Append("Inactive", "Inactive")
        self.status_combo.SetSelection(0)
        form_sizer.Add(
            status_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT | wx.ALL, 5
        )
        form_sizer.Add(self.status_combo, 0, wx.EXPAND | wx.ALL, 5)

        caf_no_label = wx.StaticText(form_panel, label="CAF No:")
        self.caf_no_text = wx.TextCtrl(form_panel, size=wx.Size(200, -1))
        form_sizer.Add(
            caf_no_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT | wx.ALL, 5
        )
        form_sizer.Add(self.caf_no_text, 0, wx.EXPAND | wx.ALL, 5)

        caf_date_label = wx.StaticText(form_panel, label="CAF Date:")
        self.caf_date_picker = DatePickerCtrl(form_panel, size=wx.Size(200, -1))
        self.caf_date_picker.SetValue(datetime.now().strftime("%Y-%m-%d"))
        form_sizer.Add(
            caf_date_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT | wx.ALL, 5
        )
        form_sizer.Add(self.caf_date_picker, 0, wx.EXPAND | wx.ALL, 5)

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

    def populate_terms(self):
        try:
            terms = self.repository.list_terms()
            for term in terms:
                self.term_combo.Append(term, term)

            if terms:
                self.term_combo.SetSelection(0)
        except Exception as e:
            logger.error(f"Error populating terms: {str(e)}")

    def populate_semesters(self):
        try:
            if not self.structure_id:
                logger.warning("No structure_id available to load semesters")
                return

            semesters = self.repository.get_structure_semesters(self.structure_id)
            for semester in semesters:
                display_text = f"{semester.semester_number:02d} {semester.name}"
                self.semester_number_combo.Append(display_text, semester.id)

            if semesters:
                self.semester_number_combo.SetSelection(0)
        except Exception as e:
            logger.error(f"Error populating semesters: {str(e)}")

    def on_save(self, event):
        term = self.term_combo.GetStringSelection()
        semester_idx = self.semester_number_combo.GetSelection()
        status = self.status_combo.GetStringSelection()
        caf_no = self.caf_no_text.GetValue().strip()
        caf_date = self.caf_date_picker.GetValue()

        if not term:
            wx.MessageBox(
                "Please select a term", "Validation Error", wx.OK | wx.ICON_WARNING
            )
            return

        if semester_idx == wx.NOT_FOUND:
            wx.MessageBox(
                "Please select a semester",
                "Validation Error",
                wx.OK | wx.ICON_WARNING,
            )
            return

        structure_semester_id = self.semester_number_combo.GetClientData(semester_idx)

        if not status:
            wx.MessageBox(
                "Please select a status", "Validation Error", wx.OK | wx.ICON_WARNING
            )
            return

        data = {
            "student_program_id": self.student_program_id,
            "term": term,
            "structure_semester_id": structure_semester_id,
            "status": status,
            "caf_no": caf_no if caf_no else None,
            "caf_date": caf_date if caf_date else None,
        }

        if self.push_worker and self.push_worker.is_alive():
            wx.MessageBox(
                "Another operation is in progress. Please wait.",
                "Operation in Progress",
                wx.OK | wx.ICON_INFORMATION,
            )
            return

        self.push_worker = PushSemesterWorker(data, self.service, self.push_callback)
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
                    "Semester added successfully",
                    "Success",
                    wx.OK | wx.ICON_INFORMATION,
                )
                wx.CallAfter(self.EndModal, wx.ID_OK)
            else:
                wx.CallAfter(
                    wx.MessageBox,
                    f"Failed to add semester: {message}",
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


class PushSemesterWorker(threading.Thread):
    def __init__(self, data, service, callback):
        super().__init__(daemon=True)
        self.data = data
        self.service = service
        self.callback = callback

    def run(self):
        try:
            self.callback("progress", "Adding semester to CMS...")
            success, message = self.service.push_semester(
                self.data, progress_callback=lambda msg: self.callback("progress", msg)
            )
            self.callback("complete", success, message)
        except Exception as e:
            logger.error(f"Error in PushSemesterWorker: {str(e)}")
            self.callback("error", str(e))
