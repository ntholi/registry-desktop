import threading

import wx

from .repository import StructureRepository
from .service import SchoolSyncService


class ImportStructuresWorker(threading.Thread):
    def __init__(
        self,
        service,
        callback,
        import_scope,
        school_id=None,
        program_id=None,
        fetch_semesters=False,
    ):
        super().__init__(daemon=True)
        self.service = service
        self.callback = callback
        self.import_scope = import_scope
        self.school_id = school_id
        self.program_id = program_id
        self.fetch_semesters = fetch_semesters
        self.should_stop = False

    def run(self):
        try:
            if self.should_stop:
                return

            if self.import_scope == "all_schools":
                self.service.import_all_schools_structures(
                    self._progress_callback,
                    self.fetch_semesters,
                )
            elif self.import_scope == "school":
                if not self.school_id:
                    raise ValueError("School ID is required for school scope")
                self.service.import_school_structures(
                    self.school_id,
                    self._progress_callback,
                    self.fetch_semesters,
                )
            elif self.import_scope == "program":
                if not self.program_id:
                    raise ValueError("Program ID is required for program scope")
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
            size=wx.Size(500, 400),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self.status_bar = status_bar
        self.repository = StructureRepository()
        self.service = SchoolSyncService(self.repository)
        self.import_worker = None

        self.init_ui()
        self.load_schools_and_programs()
        self.Centre()

    def init_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        instruction_text = wx.StaticText(
            self,
            label="Select import scope and configure options:",
        )
        main_sizer.Add(instruction_text, 0, wx.ALL, 15)

        scope_box = wx.StaticBox(self, label="Import Scope")
        scope_sizer = wx.StaticBoxSizer(scope_box, wx.VERTICAL)

        self.all_schools_radio = wx.RadioButton(
            self, label="All Schools", style=wx.RB_GROUP
        )
        self.all_schools_radio.Bind(wx.EVT_RADIOBUTTON, self.on_scope_changed)
        scope_sizer.Add(self.all_schools_radio, 0, wx.ALL, 5)

        self.school_radio = wx.RadioButton(self, label="Specific School:")
        self.school_radio.Bind(wx.EVT_RADIOBUTTON, self.on_scope_changed)
        scope_sizer.Add(self.school_radio, 0, wx.ALL, 5)

        school_choice_sizer = wx.BoxSizer(wx.HORIZONTAL)
        school_choice_sizer.AddSpacer(25)
        self.school_choice = wx.Choice(self)
        self.school_choice.Enable(False)
        school_choice_sizer.Add(self.school_choice, 1, wx.EXPAND | wx.RIGHT, 5)
        scope_sizer.Add(school_choice_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 5)

        scope_sizer.AddSpacer(5)

        self.program_radio = wx.RadioButton(self, label="Specific Program:")
        self.program_radio.Bind(wx.EVT_RADIOBUTTON, self.on_scope_changed)
        scope_sizer.Add(self.program_radio, 0, wx.ALL, 5)

        program_choice_sizer = wx.BoxSizer(wx.HORIZONTAL)
        program_choice_sizer.AddSpacer(25)
        self.program_choice = wx.Choice(self)
        self.program_choice.Enable(False)
        program_choice_sizer.Add(self.program_choice, 1, wx.EXPAND | wx.RIGHT, 5)
        scope_sizer.Add(program_choice_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 5)

        main_sizer.Add(scope_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)

        main_sizer.AddSpacer(15)

        options_box = wx.StaticBox(self, label="Import Options")
        options_sizer = wx.StaticBoxSizer(options_box, wx.VERTICAL)

        self.semesters_checkbox = wx.CheckBox(
            self, label="Include Semesters and Modules"
        )
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

    def load_schools_and_programs(self):
        try:
            schools = self.repository.list_active_schools()
            for school in schools:
                self.school_choice.Append(str(school.name), school.id)

            programs = self.repository.list_programs()
            for program in programs:
                self.program_choice.Append(str(program.name), program.id)

        except Exception as e:
            wx.MessageBox(
                f"Error loading data: {str(e)}",
                "Error",
                wx.OK | wx.ICON_ERROR,
            )

    def on_scope_changed(self, event):
        self.school_choice.Enable(self.school_radio.GetValue())
        self.program_choice.Enable(self.program_radio.GetValue())

    def on_import(self, event):
        import_scope = None
        school_id = None
        program_id = None

        if self.all_schools_radio.GetValue():
            import_scope = "all_schools"
        elif self.school_radio.GetValue():
            import_scope = "school"
            sel = self.school_choice.GetSelection()
            if sel == wx.NOT_FOUND:
                wx.MessageBox(
                    "Please select a school.",
                    "Selection Required",
                    wx.OK | wx.ICON_WARNING,
                )
                return
            school_id = self.school_choice.GetClientData(sel)
        elif self.program_radio.GetValue():
            import_scope = "program"
            sel = self.program_choice.GetSelection()
            if sel == wx.NOT_FOUND:
                wx.MessageBox(
                    "Please select a program.",
                    "Selection Required",
                    wx.OK | wx.ICON_WARNING,
                )
                return
            program_id = self.program_choice.GetClientData(sel)
        else:
            wx.MessageBox(
                "Please select an import scope.",
                "Selection Required",
                wx.OK | wx.ICON_WARNING,
            )
            return

        fetch_semesters = self.semesters_checkbox.GetValue()

        message = "This will import structures "
        if import_scope == "all_schools":
            message += "for all schools. This may take a significant amount of time."
        elif import_scope == "school":
            school_name = self.school_choice.GetStringSelection()
            message += f"for {school_name}."
        elif import_scope == "program":
            program_name = self.program_choice.GetStringSelection()
            message += f"for {program_name}."

        if fetch_semesters:
            message += " Including semesters and modules will significantly increase import time."

        message += "\n\nDo you want to continue?"

        result = wx.MessageBox(
            message,
            "Confirm Import",
            wx.YES_NO | wx.ICON_QUESTION,
        )

        if result != wx.YES:
            return

        self.import_button.Enable(False)
        self.all_schools_radio.Enable(False)
        self.school_radio.Enable(False)
        self.program_radio.Enable(False)
        self.school_choice.Enable(False)
        self.program_choice.Enable(False)
        self.semesters_checkbox.Enable(False)

        self.import_worker = ImportStructuresWorker(
            self.service,
            self.on_import_callback,
            import_scope,
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
            self.all_schools_radio.Enable(True)
            self.school_radio.Enable(True)
            self.program_radio.Enable(True)
            self.on_scope_changed(None)
            self.semesters_checkbox.Enable(True)

            wx.MessageBox(f"Import failed: {error_msg}", "Error", wx.OK | wx.ICON_ERROR)
