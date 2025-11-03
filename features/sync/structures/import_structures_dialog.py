import threading

import wx

from .repository import StructureRepository
from .service import SchoolSyncService


class ImportStructuresWorker(threading.Thread):
    def __init__(
        self,
        service,
        callback,
        school_id=None,
        program_id=None,
        fetch_semesters=False,
    ):
        super().__init__(daemon=True)
        self.service = service
        self.callback = callback
        self.school_id = school_id
        self.program_id = program_id
        self.fetch_semesters = fetch_semesters
        self.should_stop = False

    def run(self):
        try:
            if self.should_stop:
                return

            if self.school_id is None:
                self.service.import_all_schools_structures(
                    self._progress_callback,
                    self.fetch_semesters,
                )
            elif self.program_id is None:
                self.service.import_school_structures(
                    self.school_id,
                    self._progress_callback,
                    self.fetch_semesters,
                )
            else:
                self.service.import_program_structures(
                    self.program_id,
                    self._progress_callback,
                    self.fetch_semesters,
                )

            self.callback("finished")

        except Exception as e:
            self.callback("error", str(e))

    def _progress_callback(self, message, current, total):
        self.callback("progress", message, current, total)

    def stop(self):
        self.should_stop = True


class ImportStructuresDialog(wx.Dialog):
    def __init__(self, parent, status_bar=None):
        super().__init__(
            parent,
            title="Import Structures",
            size=wx.Size(500, 350),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self.status_bar = status_bar
        self.repository = StructureRepository()
        self.service = SchoolSyncService(self.repository)
        self.import_worker = None

        self.init_ui()
        self.load_schools()
        self.Centre()

    def init_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        instruction_text = wx.StaticText(
            self,
            label="Select school and program to import structures:",
        )
        main_sizer.Add(instruction_text, 0, wx.ALL, 15)

        scope_box = wx.StaticBox(self, label="Import Scope")
        scope_sizer = wx.StaticBoxSizer(scope_box, wx.VERTICAL)

        school_label = wx.StaticText(self, label="School:")
        scope_sizer.Add(school_label, 0, wx.ALL, 5)

        self.school_choice = wx.Choice(self)
        self.school_choice.Bind(wx.EVT_CHOICE, self.on_school_changed)
        scope_sizer.Add(self.school_choice, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)

        scope_sizer.AddSpacer(5)

        program_label = wx.StaticText(self, label="Program:")
        scope_sizer.Add(program_label, 0, wx.ALL, 5)

        self.program_choice = wx.Choice(self)
        scope_sizer.Add(self.program_choice, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)

        main_sizer.Add(scope_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)

        main_sizer.AddSpacer(15)

        options_box = wx.StaticBox(self, label="Import Options")
        options_sizer = wx.StaticBoxSizer(options_box, wx.VERTICAL)

        self.semesters_checkbox = wx.CheckBox(
            self, label="Include Semesters and Modules"
        )
        self.semesters_checkbox.SetValue(True)
        options_sizer.Add(self.semesters_checkbox, 0, wx.ALL, 5)

        main_sizer.Add(options_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)

        main_sizer.AddSpacer(15)

        line = wx.StaticLine(self)
        main_sizer.Add(line, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)

        main_sizer.AddSpacer(15)

        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.AddStretchSpacer()

        self.import_button = wx.Button(self, wx.ID_OK, "Start Import")
        self.import_button.Bind(wx.EVT_BUTTON, self.on_import)
        button_sizer.Add(self.import_button, 0, wx.RIGHT, 10)

        cancel_button = wx.Button(self, wx.ID_CANCEL, "Cancel")
        button_sizer.Add(cancel_button, 0)

        main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        self.SetSizer(main_sizer)

    def load_schools(self):
        try:
            self.school_choice.Clear()
            self.school_choice.Append("All Schools", None)

            schools = self.repository.list_active_schools()
            for school in schools:
                self.school_choice.Append(str(school.name), school.id)

            self.school_choice.SetSelection(0)
            self.load_programs_for_school(None)

        except Exception as e:
            wx.MessageBox(
                f"Error loading schools: {str(e)}",
                "Error",
                wx.OK | wx.ICON_ERROR,
            )

    def load_programs_for_school(self, school_id):
        try:
            self.program_choice.Clear()
            self.program_choice.Append("All Programs", None)

            programs = self.repository.list_programs(school_id)
            for program in programs:
                self.program_choice.Append(str(program.name), program.id)

            self.program_choice.SetSelection(0)

        except Exception as e:
            wx.MessageBox(
                f"Error loading programs: {str(e)}",
                "Error",
                wx.OK | wx.ICON_ERROR,
            )

    def on_school_changed(self, event):
        sel = self.school_choice.GetSelection()
        school_id = self.school_choice.GetClientData(sel) if sel != wx.NOT_FOUND else None
        self.load_programs_for_school(school_id)

    def on_import(self, event):
        school_sel = self.school_choice.GetSelection()
        if school_sel == wx.NOT_FOUND:
            wx.MessageBox(
                "Please select a school.",
                "Selection Required",
                wx.OK | wx.ICON_WARNING,
            )
            return

        program_sel = self.program_choice.GetSelection()
        if program_sel == wx.NOT_FOUND:
            wx.MessageBox(
                "Please select a program.",
                "Selection Required",
                wx.OK | wx.ICON_WARNING,
            )
            return

        school_id = self.school_choice.GetClientData(school_sel)
        program_id = self.program_choice.GetClientData(program_sel)
        fetch_semesters = self.semesters_checkbox.GetValue()

        message = "This will import structures for "

        if school_id is None:
            message += "all schools"
        elif program_id is None:
            school_name = self.school_choice.GetStringSelection()
            message += f"{school_name} (all programs)"
        else:
            school_name = self.school_choice.GetStringSelection()
            program_name = self.program_choice.GetStringSelection()
            message += f"{school_name} - {program_name}"

        if fetch_semesters:
            message += ", including semesters and modules"

        message += ".\n\n"

        if school_id is None:
            message += "This may take a significant amount of time.\n\n"

        message += "Do you want to continue?"

        result = wx.MessageBox(
            message,
            "Confirm Import",
            wx.YES_NO | wx.ICON_QUESTION,
        )

        if result != wx.YES:
            return

        self.import_button.Enable(False)
        self.school_choice.Enable(False)
        self.program_choice.Enable(False)
        self.semesters_checkbox.Enable(False)

        self.import_worker = ImportStructuresWorker(
            self.service,
            self.on_import_callback,
            school_id,
            program_id,
            fetch_semesters,
        )
        self.import_worker.start()

    def on_import_callback(self, event_type, *args):
        wx.CallAfter(self._handle_import_event, event_type, *args)

    def _handle_import_event(self, event_type, *args):
        if event_type == "progress":
            message, current, total = args
            if self.status_bar:
                self.status_bar.show_progress(message, current, total)
        elif event_type == "finished":
            if self.status_bar:
                self.status_bar.clear()

            wx.MessageBox(
                "Import completed successfully.",
                "Import Complete",
                wx.OK | wx.ICON_INFORMATION,
            )

            self.EndModal(wx.ID_OK)

        elif event_type == "error":
            error_msg = args[0]
            if self.status_bar:
                self.status_bar.clear()

            self.import_button.Enable(True)
            self.school_choice.Enable(True)
            self.program_choice.Enable(True)
            self.semesters_checkbox.Enable(True)

            wx.MessageBox(f"Import failed: {error_msg}", "Error", wx.OK | wx.ICON_ERROR)
