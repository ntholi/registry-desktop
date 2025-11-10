import wx

from base import get_logger

from .importer_project import ImporterProject, ImporterProjectManager
from .importer_worker import ImporterWorker

logger = get_logger(__name__)


class ImporterDialog(wx.Dialog):
    def __init__(self, parent, sync_service, status_bar=None):
        super().__init__(
            parent,
            title="Import Students",
            size=wx.Size(600, 500),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self.sync_service = sync_service
        self.status_bar = status_bar
        self.worker = None
        self.project = None

        self.setup_panel = None
        self.progress_panel = None

        self.init_ui()
        self.load_project_state()
        self.CenterOnParent()

    def init_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        self.setup_panel = self.create_setup_panel()
        main_sizer.Add(self.setup_panel, 1, wx.EXPAND)

        self.progress_panel = self.create_progress_panel()
        main_sizer.Add(self.progress_panel, 1, wx.EXPAND)
        self.progress_panel.Hide()

        self.SetSizer(main_sizer)
        self.Bind(wx.EVT_CLOSE, self.on_close)

    def on_close(self, event):
        if (
            self.worker
            and self.worker.is_alive()
            and self.project
            and self.project.status == "running"
        ):
            dlg = wx.MessageDialog(
                self,
                "Import is currently running.\n\n"
                "The import will continue in the background if you close this dialog.\n"
                "Use Stop to cancel the import or Hide to minimize.",
                "Import Running",
                wx.OK | wx.ICON_INFORMATION,
            )
            dlg.ShowModal()
            dlg.Destroy()

        event.Skip()

    def create_setup_panel(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.AddSpacer(20)

        title_label = wx.StaticText(panel, label="Import Students from CMS")
        font = title_label.GetFont()
        font.PointSize = 14
        font = font.Bold()
        title_label.SetFont(font)
        sizer.Add(title_label, 0, wx.LEFT | wx.RIGHT, 20)

        sizer.AddSpacer(10)

        desc_label = wx.StaticText(
            panel,
            label="Enter the range of student numbers to import from the CMS database.",
        )
        sizer.Add(desc_label, 0, wx.LEFT | wx.RIGHT, 20)

        sizer.AddSpacer(20)

        range_label = wx.StaticText(panel, label="Student Number Range")
        font = range_label.GetFont()
        font = font.Bold()
        range_label.SetFont(font)
        sizer.Add(range_label, 0, wx.LEFT | wx.RIGHT, 20)

        sizer.AddSpacer(10)

        range_sizer = wx.BoxSizer(wx.HORIZONTAL)

        first_label = wx.StaticText(panel, label="First Student Number:")
        range_sizer.Add(first_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        self.start_student_input = wx.TextCtrl(panel, size=wx.Size(150, -1))
        range_sizer.Add(self.start_student_input, 0, wx.RIGHT, 20)

        last_label = wx.StaticText(panel, label="Last Student Number:")
        range_sizer.Add(last_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        self.end_student_input = wx.TextCtrl(panel, size=wx.Size(150, -1))
        range_sizer.Add(self.end_student_input, 0)

        sizer.Add(range_sizer, 0, wx.LEFT | wx.RIGHT, 20)

        sizer.AddSpacer(20)

        separator_line = wx.StaticLine(panel, style=wx.LI_HORIZONTAL)
        sizer.Add(separator_line, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)

        sizer.AddSpacer(20)

        options_label = wx.StaticText(panel, label="Import Options")
        font = options_label.GetFont()
        font = font.Bold()
        options_label.SetFont(font)
        sizer.Add(options_label, 0, wx.LEFT | wx.RIGHT, 20)

        sizer.AddSpacer(10)

        self.select_all_checkbox = wx.CheckBox(
            panel,
            label="Select All",
            style=wx.CHK_3STATE | wx.CHK_ALLOW_3RD_STATE_FOR_USER,
        )
        self.select_all_checkbox.Set3StateValue(wx.CHK_CHECKED)
        self.select_all_checkbox.Bind(wx.EVT_CHECKBOX, self.on_select_all_checkbox)
        sizer.Add(self.select_all_checkbox, 0, wx.LEFT | wx.RIGHT, 20)

        sizer.AddSpacer(10)

        checkbox_sizer = wx.BoxSizer(wx.VERTICAL)

        self.student_info_checkbox = wx.CheckBox(
            panel, label="Student Info (Name, IC/Passport, Phones, Country, etc.)"
        )
        self.student_info_checkbox.SetValue(True)
        self.student_info_checkbox.Bind(wx.EVT_CHECKBOX, self.on_data_checkbox_changed)
        checkbox_sizer.Add(self.student_info_checkbox, 0, wx.BOTTOM, 5)

        self.personal_info_checkbox = wx.CheckBox(
            panel, label="Personal Info (DOB, Gender, Marital Status, Religion, etc.)"
        )
        self.personal_info_checkbox.SetValue(True)
        self.personal_info_checkbox.Bind(wx.EVT_CHECKBOX, self.on_data_checkbox_changed)
        checkbox_sizer.Add(self.personal_info_checkbox, 0, wx.BOTTOM, 5)

        self.education_history_checkbox = wx.CheckBox(
            panel,
            label="Educational History (Previous schools, qualifications, etc.)",
        )
        self.education_history_checkbox.SetValue(True)
        self.education_history_checkbox.Bind(
            wx.EVT_CHECKBOX, self.on_data_checkbox_changed
        )
        checkbox_sizer.Add(self.education_history_checkbox, 0, wx.BOTTOM, 5)

        self.enrollment_data_checkbox = wx.CheckBox(
            panel, label="Enrollment Data (Programs, Semesters, Modules, etc.)"
        )
        self.enrollment_data_checkbox.SetValue(True)
        self.enrollment_data_checkbox.Bind(wx.EVT_CHECKBOX, self.on_data_checkbox_changed)
        checkbox_sizer.Add(self.enrollment_data_checkbox, 0)

        sizer.Add(checkbox_sizer, 0, wx.LEFT | wx.RIGHT, 20)

        sizer.AddStretchSpacer()

        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.AddStretchSpacer()

        cancel_button = wx.Button(panel, wx.ID_CANCEL, label="Cancel")
        button_sizer.Add(cancel_button, 0, wx.RIGHT, 10)

        self.start_import_button = wx.Button(panel, label="Start Import")
        self.start_import_button.Bind(wx.EVT_BUTTON, self.on_start_import)
        self.start_import_button.SetDefault()
        button_sizer.Add(self.start_import_button, 0)

        sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 20)

        panel.SetSizer(sizer)
        return panel

    def create_progress_panel(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.AddSpacer(20)

        title_label = wx.StaticText(panel, label="Import Progress")
        font = title_label.GetFont()
        font.PointSize = 14
        font = font.Bold()
        title_label.SetFont(font)
        sizer.Add(title_label, 0, wx.LEFT | wx.RIGHT, 20)

        sizer.AddSpacer(20)

        info_sizer = wx.FlexGridSizer(rows=2, cols=2, vgap=10, hgap=20)

        range_label = wx.StaticText(panel, label="Range:")
        font = range_label.GetFont()
        font = font.Bold()
        range_label.SetFont(font)
        info_sizer.Add(range_label, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)

        self.range_value_label = wx.StaticText(panel, label="")
        info_sizer.Add(self.range_value_label, 0, wx.ALIGN_CENTER_VERTICAL)

        status_label = wx.StaticText(panel, label="Status:")
        font = status_label.GetFont()
        font = font.Bold()
        status_label.SetFont(font)
        info_sizer.Add(status_label, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)

        self.status_value_label = wx.StaticText(panel, label="")
        info_sizer.Add(self.status_value_label, 0, wx.ALIGN_CENTER_VERTICAL)

        sizer.Add(info_sizer, 0, wx.LEFT | wx.RIGHT, 20)

        sizer.AddSpacer(20)

        separator_line = wx.StaticLine(panel, style=wx.LI_HORIZONTAL)
        sizer.Add(separator_line, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)

        sizer.AddSpacer(20)

        progress_label = wx.StaticText(panel, label="Progress")
        font = progress_label.GetFont()
        font = font.Bold()
        progress_label.SetFont(font)
        sizer.Add(progress_label, 0, wx.LEFT | wx.RIGHT, 20)

        sizer.AddSpacer(10)

        self.progress_bar = wx.Gauge(panel, range=100)
        sizer.Add(self.progress_bar, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)

        sizer.AddSpacer(10)

        self.progress_text = wx.StaticText(panel, label="")
        sizer.Add(self.progress_text, 0, wx.LEFT | wx.RIGHT, 20)

        sizer.AddSpacer(20)

        stats_sizer = wx.FlexGridSizer(rows=3, cols=2, vgap=10, hgap=20)

        success_label = wx.StaticText(panel, label="Successfully Imported:")
        font = success_label.GetFont()
        font = font.Bold()
        success_label.SetFont(font)
        stats_sizer.Add(success_label, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)

        self.success_count_label = wx.StaticText(panel, label="0")
        stats_sizer.Add(self.success_count_label, 0, wx.ALIGN_CENTER_VERTICAL)

        failed_label = wx.StaticText(panel, label="Failed:")
        font = failed_label.GetFont()
        font = font.Bold()
        failed_label.SetFont(font)
        stats_sizer.Add(failed_label, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)

        self.failed_count_label = wx.StaticText(panel, label="0")
        stats_sizer.Add(self.failed_count_label, 0, wx.ALIGN_CENTER_VERTICAL)

        current_label = wx.StaticText(panel, label="Current Student:")
        font = current_label.GetFont()
        font = font.Bold()
        current_label.SetFont(font)
        stats_sizer.Add(current_label, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)

        self.current_student_label = wx.StaticText(panel, label="")
        stats_sizer.Add(self.current_student_label, 0, wx.ALIGN_CENTER_VERTICAL)

        sizer.Add(stats_sizer, 0, wx.LEFT | wx.RIGHT, 20)

        sizer.AddStretchSpacer()

        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.AddStretchSpacer()

        self.stop_button = wx.Button(panel, label="Stop")
        self.stop_button.Bind(wx.EVT_BUTTON, self.on_stop)
        button_sizer.Add(self.stop_button, 0, wx.RIGHT, 10)

        self.pause_resume_button = wx.Button(panel, label="Pause")
        self.pause_resume_button.Bind(wx.EVT_BUTTON, self.on_pause_resume)
        button_sizer.Add(self.pause_resume_button, 0, wx.RIGHT, 10)

        self.hide_button = wx.Button(panel, label="Hide")
        self.hide_button.Bind(wx.EVT_BUTTON, self.on_hide)
        button_sizer.Add(self.hide_button, 0)

        sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 20)

        panel.SetSizer(sizer)
        return panel

    def load_project_state(self):
        self.project = ImporterProjectManager.load_project()

        if self.project and self.project.status in ["running", "paused"]:
            if self.project.status == "running":
                self.project.status = "paused"
                ImporterProjectManager.save_project(self.project)

            self.show_progress_panel()
            self.update_progress_display()
            self.pause_resume_button.SetLabel("Resume")
        else:
            self.show_setup_panel()

    def show_setup_panel(self):
        self.progress_panel.Hide()
        self.setup_panel.Show()
        self.Layout()

    def show_progress_panel(self):
        self.setup_panel.Hide()
        self.progress_panel.Show()
        self.Layout()

    def on_select_all_checkbox(self, event):
        is_checked = self.select_all_checkbox.GetValue()
        self.student_info_checkbox.SetValue(is_checked)
        self.personal_info_checkbox.SetValue(is_checked)
        self.education_history_checkbox.SetValue(is_checked)
        self.enrollment_data_checkbox.SetValue(is_checked)

    def on_data_checkbox_changed(self, event):
        all_checked = all(
            [
                self.student_info_checkbox.GetValue(),
                self.personal_info_checkbox.GetValue(),
                self.education_history_checkbox.GetValue(),
                self.enrollment_data_checkbox.GetValue(),
            ]
        )
        any_checked = any(
            [
                self.student_info_checkbox.GetValue(),
                self.personal_info_checkbox.GetValue(),
                self.education_history_checkbox.GetValue(),
                self.enrollment_data_checkbox.GetValue(),
            ]
        )

        if all_checked:
            self.select_all_checkbox.Set3StateValue(wx.CHK_CHECKED)
        elif any_checked:
            self.select_all_checkbox.Set3StateValue(wx.CHK_UNDETERMINED)
        else:
            self.select_all_checkbox.Set3StateValue(wx.CHK_UNCHECKED)

    def on_start_import(self, event):
        start_num = self.start_student_input.GetValue().strip()
        end_num = self.end_student_input.GetValue().strip()

        if not start_num or not end_num:
            wx.MessageBox(
                "Please enter both first and last student numbers.",
                "Missing Input",
                wx.OK | wx.ICON_WARNING,
            )
            return

        if not start_num.isdigit() or not end_num.isdigit():
            wx.MessageBox(
                "Student numbers must be numeric.", "Invalid Input", wx.OK | wx.ICON_WARNING
            )
            return

        if len(start_num) != 9 or len(end_num) != 9:
            wx.MessageBox(
                "Student numbers must be exactly 9 digits.",
                "Invalid Input",
                wx.OK | wx.ICON_WARNING,
            )
            return

        if int(start_num) > int(end_num):
            wx.MessageBox(
                "First student number must be less than or equal to last student number.",
                "Invalid Range",
                wx.OK | wx.ICON_WARNING,
            )
            return

        if int(end_num) - int(start_num) > 20000:
            wx.MessageBox(
                "Range is too large. Maximum 20,000 students at a time.",
                "Range Too Large",
                wx.OK | wx.ICON_WARNING,
            )
            return

        import_options = {
            "student_info": self.student_info_checkbox.GetValue(),
            "personal_info": self.personal_info_checkbox.GetValue(),
            "education_history": self.education_history_checkbox.GetValue(),
            "enrollment_data": self.enrollment_data_checkbox.GetValue(),
        }

        if not any(import_options.values()):
            wx.MessageBox(
                "Please select at least one data type to import.",
                "No Data Selected",
                wx.OK | wx.ICON_WARNING,
            )
            return

        student_count = int(end_num) - int(start_num) + 1
        dlg = wx.MessageDialog(
            self,
            f"Start importing {student_count} student(s) from the CMS?\n\n"
            f"This will fetch data from the CMS and save it to the portal database.\n"
            f"You can pause or stop the import at any time.",
            "Confirm Import",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
        )

        if dlg.ShowModal() != wx.ID_YES:
            dlg.Destroy()
            return

        dlg.Destroy()

        self.project = ImporterProjectManager.create_project(
            start_num, end_num, import_options
        )

        self.show_progress_panel()
        self.update_progress_display()
        self.start_worker()

    def start_worker(self):
        if self.worker and self.worker.is_alive():
            logger.warning("Worker already running, cannot start new worker")
            return

        self.project.status = "running"
        ImporterProjectManager.save_project(self.project)

        self.worker = ImporterWorker(
            self.project, self.sync_service, self.on_worker_callback
        )
        self.worker.start()

        self.pause_resume_button.SetLabel("Pause")
        self.pause_resume_button.Enable(True)
        self.stop_button.Enable(True)
        self.hide_button.Enable(True)

    def on_pause_resume(self, event):
        if not self.project:
            return

        if self.project.status == "running":
            self.pause_worker()
        elif self.project.status == "paused":
            self.resume_worker()

    def pause_worker(self):
        if self.worker and self.worker.is_alive():
            logger.info("Pausing import worker")
            self.worker.stop()
            self.pause_resume_button.Enable(False)
            self.pause_resume_button.SetLabel("Pausing...")

    def resume_worker(self):
        logger.info("Resuming import")
        self.project.status = "running"
        ImporterProjectManager.save_project(self.project)
        self.start_worker()

    def on_stop(self, event):
        if not self.project:
            return

        dlg = wx.MessageDialog(
            self,
            "Are you sure you want to stop the import?\n\n"
            "This will permanently delete the import project and you will need to start over.",
            "Confirm Stop",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
        )

        if dlg.ShowModal() != wx.ID_YES:
            dlg.Destroy()
            return

        dlg.Destroy()

        if self.worker and self.worker.is_alive():
            logger.info("Stopping and deleting import project")
            self.worker.stop()

        ImporterProjectManager.delete_project()
        self.project = None

        if self.status_bar:
            self.status_bar.clear()

        self.show_setup_panel()
        self.clear_setup_fields()

    def on_hide(self, event):
        if self.project and self.project.status == "running":
            dlg = wx.MessageDialog(
                self,
                "The import will continue in the background.\n\n"
                "Click the 'Import' button again to view progress or control the import.",
                "Import Continues",
                wx.OK | wx.ICON_INFORMATION,
            )
            dlg.ShowModal()
            dlg.Destroy()

        self.Hide()

    def clear_setup_fields(self):
        self.start_student_input.SetValue("")
        self.end_student_input.SetValue("")
        self.student_info_checkbox.SetValue(True)
        self.personal_info_checkbox.SetValue(True)
        self.education_history_checkbox.SetValue(True)
        self.enrollment_data_checkbox.SetValue(True)
        self.select_all_checkbox.Set3StateValue(wx.CHK_CHECKED)

    def update_progress_display(self):
        if not self.project:
            return

        self.range_value_label.SetLabel(
            f"{self.project.start_student} - {self.project.end_student}"
        )

        status_text = self.project.status.capitalize()
        self.status_value_label.SetLabel(status_text)

        self.success_count_label.SetLabel(str(self.project.success_count))
        self.failed_count_label.SetLabel(str(self.project.failed_count))
        self.current_student_label.SetLabel(self.project.current_student)

        total_students = len(
            ImporterProjectManager.generate_student_numbers(
                self.project.start_student, self.project.end_student
            )
        )
        remaining = len(ImporterProjectManager.get_remaining_students(self.project))
        completed = total_students - remaining

        if total_students > 0:
            progress_percent = int((completed / total_students) * 100)
            self.progress_bar.SetValue(progress_percent)
            self.progress_text.SetLabel(f"{completed} of {total_students} students")
        else:
            self.progress_bar.SetValue(0)
            self.progress_text.SetLabel("0 of 0 students")

    def on_worker_callback(self, event_type, *args):
        wx.CallAfter(self._handle_worker_event, event_type, *args)

    def _handle_worker_event(self, event_type, *args):
        if event_type == "progress":
            message, current, total, project = args
            self.project = project

            if self.status_bar:
                self.status_bar.show_progress(message, current, total)

            if self.IsShown():
                self.update_progress_display()

        elif event_type == "finished":
            project = args[0]
            self.project = project

            if self.status_bar:
                self.status_bar.clear()

            self.update_progress_display()

            message = (
                f"Import completed successfully!\n\n"
                f"Successfully imported: {project.success_count}\n"
                f"Failed: {project.failed_count}"
            )

            if project.failed_count > 0:
                message += f"\n\nFailed students: {', '.join(project.failed_students[:10])}"
                if len(project.failed_students) > 10:
                    message += f"\n... and {len(project.failed_students) - 10} more"

            wx.MessageBox(message, "Import Complete", wx.OK | wx.ICON_INFORMATION)

            ImporterProjectManager.delete_project()
            self.project = None
            self.show_setup_panel()
            self.clear_setup_fields()

        elif event_type == "stopped":
            project = args[0]
            self.project = project
            self.project.status = "paused"
            ImporterProjectManager.save_project(self.project)

            if self.status_bar:
                self.status_bar.clear()

            if self.IsShown():
                self.update_progress_display()
                self.pause_resume_button.SetLabel("Resume")
                self.pause_resume_button.Enable(True)

        elif event_type == "error":
            error_msg = args[0]
            logger.error(f"Worker error: {error_msg}")
