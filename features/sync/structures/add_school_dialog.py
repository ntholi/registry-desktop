import threading

import wx

from .repository import StructureRepository
from .service import SchoolSyncService


class FetchProgramsWorker(threading.Thread):
    def __init__(self, school_code, service, callback):
        super().__init__(daemon=True)
        self.school_code = school_code
        self.service = service
        self.callback = callback
        self.should_stop = False

    def run(self):
        try:
            if self.should_stop:
                return

            school_data, programs = self.service.fetch_school_and_programs(
                self.school_code, self._progress_callback
            )

            self.callback("finished", school_data, programs)

        except Exception as e:
            self.callback("error", str(e))

    def _progress_callback(self, message, current, total):
        self.callback("progress", message, current, total)

    def stop(self):
        self.should_stop = True


class ImportSchoolWorker(threading.Thread):
    def __init__(
        self,
        school_data,
        programs,
        service,
        callback,
        fetch_structures=False,
        fetch_semesters=False,
    ):
        super().__init__(daemon=True)
        self.school_data = school_data
        self.programs = programs
        self.service = service
        self.callback = callback
        self.fetch_structures = fetch_structures
        self.fetch_semesters = fetch_semesters
        self.should_stop = False

    def run(self):
        try:
            if self.should_stop:
                return

            self.service.import_school_data(
                self.school_data,
                self.programs,
                self._progress_callback,
                self.fetch_structures,
                self.fetch_semesters,
            )

            self.callback("finished")

        except Exception as e:
            self.callback("error", str(e))

    def _progress_callback(self, message, current, total):
        self.callback("progress", message, current, total)

    def stop(self):
        self.should_stop = True


class AddSchoolDialog(wx.Dialog):
    def __init__(self, parent, status_bar=None):
        super().__init__(
            parent,
            title="Add School",
            size=wx.Size(600, 500),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self.status_bar = status_bar
        self.repository = StructureRepository()
        self.service = SchoolSyncService(self.repository)
        self.fetch_worker = None
        self.import_worker = None
        self.school_data = None
        self.programs = []

        self.init_ui()
        self.CenterOnScreen()

    def init_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        instruction_text = wx.StaticText(
            self,
            label="Enter the school code to fetch programs from the CMS:",
        )
        main_sizer.Add(instruction_text, 0, wx.ALL, 15)

        input_sizer = wx.BoxSizer(wx.HORIZONTAL)

        input_label = wx.StaticText(self, label="School Code:")
        input_sizer.Add(input_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        self.school_code_input = wx.TextCtrl(self, size=wx.Size(150, -1))
        self.school_code_input.Bind(wx.EVT_TEXT, self.on_text_changed)
        input_sizer.Add(self.school_code_input, 0)

        input_sizer.AddStretchSpacer()

        self.fetch_button = wx.Button(self, label="Fetch")
        self.fetch_button.Bind(wx.EVT_BUTTON, self.on_fetch)
        self.fetch_button.Enable(False)
        input_sizer.Add(self.fetch_button, 0)

        main_sizer.Add(input_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)

        main_sizer.AddSpacer(15)

        line = wx.StaticLine(self)
        main_sizer.Add(line, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)

        main_sizer.AddSpacer(15)

        results_label = wx.StaticText(self, label="Programs Found:")
        main_sizer.Add(results_label, 0, wx.LEFT | wx.RIGHT, 15)

        main_sizer.AddSpacer(10)

        self.programs_list = wx.ListCtrl(
            self, style=wx.LC_REPORT | wx.BORDER_SIMPLE | wx.LC_SINGLE_SEL
        )
        self.programs_list.AppendColumn("Code", width=100)
        self.programs_list.AppendColumn("Name", width=400)
        main_sizer.Add(self.programs_list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)

        main_sizer.AddSpacer(10)

        options_sizer = wx.BoxSizer(wx.HORIZONTAL)

        options_label = wx.StaticText(self, label="Import With:")
        options_sizer.Add(options_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 15)

        self.structures_checkbox = wx.CheckBox(self, label="Structures")
        self.structures_checkbox.Bind(wx.EVT_CHECKBOX, self.on_structures_checked)
        options_sizer.Add(
            self.structures_checkbox, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 15
        )

        self.semesters_checkbox = wx.CheckBox(self, label="Semesters")
        self.semesters_checkbox.Enable(False)
        options_sizer.Add(self.semesters_checkbox, 0, wx.ALIGN_CENTER_VERTICAL)

        main_sizer.Add(options_sizer, 0, wx.LEFT | wx.RIGHT, 15)

        main_sizer.AddSpacer(15)

        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.AddStretchSpacer()

        self.import_button = wx.Button(self, wx.ID_OK, "Import")
        self.import_button.Enable(False)
        self.import_button.Bind(wx.EVT_BUTTON, self.on_import)
        button_sizer.Add(self.import_button, 0, wx.RIGHT, 10)

        cancel_button = wx.Button(self, wx.ID_CANCEL, "Cancel")
        button_sizer.Add(cancel_button, 0)

        main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        self.SetSizer(main_sizer)

    def on_structures_checked(self, event):
        is_checked = self.structures_checkbox.GetValue()
        self.semesters_checkbox.Enable(is_checked)
        if not is_checked:
            self.semesters_checkbox.SetValue(False)

    def on_text_changed(self, event):
        text = self.school_code_input.GetValue().strip()
        self.fetch_button.Enable(bool(text))

    def on_fetch(self, event):
        school_code = self.school_code_input.GetValue().strip()
        if not school_code:
            wx.MessageBox(
                "Please enter a school code.", "Missing Code", wx.OK | wx.ICON_WARNING
            )
            return

        self.fetch_button.Enable(False)
        self.school_code_input.Enable(False)
        self.programs_list.DeleteAllItems()
        self.import_button.Enable(False)

        self.fetch_worker = FetchProgramsWorker(
            school_code,
            self.service,
            self.on_fetch_callback,
        )
        self.fetch_worker.start()

    def on_import(self, event):
        if not self.school_data or not self.programs:
            wx.MessageBox(
                "No data to import. Please fetch programs first.",
                "No Data",
                wx.OK | wx.ICON_WARNING,
            )
            return

        fetch_structures = self.structures_checkbox.GetValue()
        fetch_semesters = self.semesters_checkbox.GetValue()

        self.import_button.Enable(False)
        self.fetch_button.Enable(False)
        self.school_code_input.Enable(False)
        self.structures_checkbox.Enable(False)
        self.semesters_checkbox.Enable(False)

        self.import_worker = ImportSchoolWorker(
            self.school_data,
            self.programs,
            self.service,
            self.on_import_callback,
            fetch_structures,
            fetch_semesters,
        )
        self.import_worker.start()

    def on_fetch_callback(self, event_type, *args):
        wx.CallAfter(self._handle_fetch_event, event_type, *args)

    def _handle_fetch_event(self, event_type, *args):
        if event_type == "progress":
            message, current, total = args
            if self.status_bar:
                self.status_bar.show_progress(message, current, total)
        elif event_type == "finished":
            school_data, programs = args
            if self.status_bar:
                self.status_bar.clear()

            self.school_data = school_data
            self.programs = programs

            for idx, program in enumerate(programs):
                index = self.programs_list.InsertItem(idx, program["code"])
                self.programs_list.SetItem(index, 1, program["name"])

            self.fetch_button.Enable(True)
            self.school_code_input.Enable(True)
            self.import_button.Enable(len(programs) > 0)

            if len(programs) == 0:
                wx.MessageBox(
                    "No programs found for this school.",
                    "No Results",
                    wx.OK | wx.ICON_INFORMATION,
                )

        elif event_type == "error":
            error_msg = args[0]
            if self.status_bar:
                self.status_bar.clear()

            self.fetch_button.Enable(True)
            self.school_code_input.Enable(True)

            wx.MessageBox(error_msg, "Error", wx.OK | wx.ICON_ERROR)

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
                f"Successfully imported school and {len(self.programs)} program(s).",
                "Import Complete",
                wx.OK | wx.ICON_INFORMATION,
            )

            self.EndModal(wx.ID_OK)

        elif event_type == "error":
            error_msg = args[0]
            if self.status_bar:
                self.status_bar.clear()

            self.import_button.Enable(True)
            self.fetch_button.Enable(True)
            self.school_code_input.Enable(True)
            self.structures_checkbox.Enable(True)
            if self.structures_checkbox.GetValue():
                self.semesters_checkbox.Enable(True)

            wx.MessageBox(f"Import failed: {error_msg}", "Error", wx.OK | wx.ICON_ERROR)

    def get_results(self):
        return {
            "school_data": self.school_data,
            "programs": self.programs,
        }
