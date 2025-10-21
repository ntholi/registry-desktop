import threading

import wx

from .repository import StructureRepository
from .service import SchoolSyncService


class FetchStructureDataWorker(threading.Thread):
    def __init__(self, structure_id, structure_code, service, callback):
        super().__init__(daemon=True)
        self.structure_id = structure_id
        self.structure_code = structure_code
        self.service = service
        self.callback = callback
        self.should_stop = False

    def run(self):
        try:
            if self.should_stop:
                return

            self.service._import_semesters(
                [{"id": self.structure_id, "code": self.structure_code}],
                self.structure_code,
                self._progress_callback,
            )

            self.callback("finished")

        except Exception as e:
            self.callback("error", str(e))

    def _progress_callback(self, message, current, total):
        self.callback("progress", message, current, total)

    def stop(self):
        self.should_stop = True


class StructureDetailPanel(wx.Panel):
    def __init__(self, parent, repository, status_bar=None):
        super().__init__(parent)
        self.repository = repository
        self.status_bar = status_bar
        self.service = SchoolSyncService(repository)
        self.selected_structure_id = None
        self.selected_structure_code = None
        self.fetch_worker = None

        self.init_ui()

    def init_ui(self):
        sizer = wx.BoxSizer(wx.VERTICAL)

        title_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.detail_title = wx.StaticText(self, label="Structure Details")
        font = self.detail_title.GetFont()
        font.PointSize = 14
        font = font.Bold()
        self.detail_title.SetFont(font)
        title_sizer.Add(self.detail_title, 0, wx.ALIGN_CENTER_VERTICAL)

        title_sizer.AddStretchSpacer()

        self.fetch_button = wx.Button(self, label="Fetch")
        self.fetch_button.Bind(wx.EVT_BUTTON, self.on_fetch)
        self.fetch_button.Enable(False)
        title_sizer.Add(self.fetch_button, 0, wx.ALIGN_CENTER_VERTICAL)

        sizer.Add(title_sizer, 0, wx.EXPAND | wx.BOTTOM, 10)

        self.detail_info = wx.StaticText(
            self, label="Select a structure to view details"
        )
        sizer.Add(self.detail_info, 0, wx.BOTTOM, 20)

        line = wx.StaticLine(self)
        sizer.Add(line, 0, wx.EXPAND | wx.BOTTOM, 15)

        self.semesters_list = wx.ListCtrl(
            self, style=wx.LC_REPORT | wx.BORDER_SIMPLE | wx.LC_SINGLE_SEL
        )
        self.semesters_list.AppendColumn("Semester", width=200)
        self.semesters_list.AppendColumn("Credits", width=80)
        self.semesters_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_semester_selected)
        sizer.Add(self.semesters_list, 4, wx.EXPAND | wx.BOTTOM, 15)

        modules_label = wx.StaticText(self, label="Modules")
        font = modules_label.GetFont()
        font.PointSize = 11
        font = font.Bold()
        modules_label.SetFont(font)
        sizer.Add(modules_label, 0, wx.BOTTOM, 5)

        self.modules_list = wx.ListCtrl(self, style=wx.LC_REPORT | wx.BORDER_SIMPLE)
        self.modules_list.AppendColumn("Code", width=100)
        self.modules_list.AppendColumn("Name", width=250)
        self.modules_list.AppendColumn("Type", width=100)
        self.modules_list.AppendColumn("Credits", width=70)
        sizer.Add(self.modules_list, 5, wx.EXPAND)

        self.SetSizer(sizer)

    def load_structure_details(self, structure_id, code, desc, program):
        try:
            self.selected_structure_id = structure_id
            self.selected_structure_code = code
            self.detail_title.SetLabel(f"Structure: {code}")
            self.fetch_button.Enable(True)
            info_text = f"{desc}\n{program}"
            self.detail_info.SetLabel(info_text)

            semesters = self.repository.get_structure_semesters(structure_id)
            self.semesters_list.DeleteAllItems()

            for row, semester in enumerate(semesters):
                index = self.semesters_list.InsertItem(row, semester.name)
                self.semesters_list.SetItem(index, 1, f"{semester.total_credits:.1f}")
                self.semesters_list.SetItemData(index, semester.id)

            self.modules_list.DeleteAllItems()

            self.Layout()

        except Exception as e:
            print(f"Error loading structure details: {str(e)}")

    def on_fetch(self, event):
        if not self.selected_structure_id or not self.selected_structure_code:
            wx.MessageBox(
                "No structure selected.",
                "Missing Structure",
                wx.OK | wx.ICON_WARNING,
            )
            return

        self.fetch_button.Enable(False)

        self.fetch_worker = FetchStructureDataWorker(
            self.selected_structure_id,
            self.selected_structure_code,
            self.service,
            self.on_fetch_callback,
        )
        self.fetch_worker.start()

    def on_fetch_callback(self, event_type, *args):
        wx.CallAfter(self._handle_fetch_event, event_type, *args)

    def _handle_fetch_event(self, event_type, *args):
        if event_type == "progress":
            message, current, total = args
            if self.status_bar:
                self.status_bar.show_progress(message, current, total)
        elif event_type == "finished":
            if self.status_bar:
                self.status_bar.clear()

            self.fetch_button.Enable(True)

            if self.selected_structure_id:
                semesters = self.repository.get_structure_semesters(
                    self.selected_structure_id
                )
                self.semesters_list.DeleteAllItems()

                for row, semester in enumerate(semesters):
                    index = self.semesters_list.InsertItem(row, semester.name)
                    self.semesters_list.SetItem(
                        index, 1, f"{semester.total_credits:.1f}"
                    )
                    self.semesters_list.SetItemData(index, semester.id)

                self.modules_list.DeleteAllItems()
                self.Layout()

            wx.MessageBox(
                f"Successfully fetched structure data for {self.selected_structure_code}.",
                "Fetch Complete",
                wx.OK | wx.ICON_INFORMATION,
            )

        elif event_type == "error":
            error_msg = args[0]
            if self.status_bar:
                self.status_bar.clear()

            self.fetch_button.Enable(True)

            wx.MessageBox(f"Fetch failed: {error_msg}", "Error", wx.OK | wx.ICON_ERROR)

    def on_semester_selected(self, event):
        item = event.GetIndex()
        semester_id = self.semesters_list.GetItemData(item)
        self.load_semester_modules(semester_id)

    def load_semester_modules(self, semester_id):
        try:
            modules = self.repository.get_semester_modules(semester_id)
            self.modules_list.DeleteAllItems()

            for row, module in enumerate(modules):
                if module.hidden:
                    continue

                index = self.modules_list.InsertItem(row, module.module_code)
                self.modules_list.SetItem(index, 1, module.module_name)
                self.modules_list.SetItem(index, 2, module.type)
                self.modules_list.SetItem(index, 3, f"{module.credits:.1f}")

            self.Layout()

        except Exception as e:
            print(f"Error loading semester modules: {str(e)}")

    def clear(self):
        self.selected_structure_id = None
        self.selected_structure_code = None
        self.detail_title.SetLabel("Structure Details")
        self.detail_info.SetLabel("Select a structure to view details")
        self.fetch_button.Enable(False)
        self.semesters_list.DeleteAllItems()
        self.modules_list.DeleteAllItems()
        self.Layout()
