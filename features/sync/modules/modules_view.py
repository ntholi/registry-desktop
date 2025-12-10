import threading

import wx

from .fetch_module_dialog import FetchModuleDialog
from .module_form import ModuleFormDialog
from .repository import ModuleRepository
from .service import ModuleSyncService


class FetchAllModulesWorker(threading.Thread):
    def __init__(self, service, callback):
        super().__init__(daemon=True)
        self.service = service
        self.callback = callback
        self.should_stop = False

    def run(self):
        try:
            self.service.fetch_and_save_all_modules(progress_callback=self.progress)
            wx.CallAfter(lambda: self.callback("complete", None))
        except Exception as e:
            error_msg = str(e)
            wx.CallAfter(lambda: self.callback("error", error_msg))

    def progress(self, message, current, total):
        if not self.should_stop:
            wx.CallAfter(lambda: self.callback("progress", message, current, total))


class LoadModulesWorker(threading.Thread):
    def __init__(self, repository, search_query, page, page_size, callback):
        super().__init__(daemon=True)
        self.repository = repository
        self.search_query = search_query
        self.page = page
        self.page_size = page_size
        self.callback = callback
        self.should_stop = False

    def run(self):
        if self.should_stop:
            return
        try:
            modules, total = self.repository.fetch_modules(
                search_query=self.search_query,
                page=self.page,
                page_size=self.page_size,
            )
            self.callback("modules_loaded", modules, total)
        except Exception as e:
            self.callback("modules_error", str(e))

    def stop(self):
        self.should_stop = True


class UpdateModuleWorker(threading.Thread):
    def __init__(self, module_id, module_data, service, callback):
        super().__init__(daemon=True)
        self.module_id = module_id
        self.module_data = module_data
        self.service = service
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

            success, message = self.service.push_module(
                self.module_id,
                self.module_data,
                self.emit_progress,
            )

            self.callback("update_finished", success, message)

        except Exception as e:
            self.callback(
                "error", f"Error updating module {self.module_id}: {str(e)}"
            )
            self.callback("update_finished", False, str(e))

    def stop(self):
        self.should_stop = True


class ModulesView(wx.Panel):
    def __init__(self, parent, status_bar=None):
        super().__init__(parent)
        self.status_bar = status_bar
        self.current_page = 1
        self.page_size = 30
        self.total_modules = 0
        self.search_query = None
        self.repository = ModuleRepository()
        self.service = ModuleSyncService(self.repository)
        self.load_worker = None
        self.update_worker = None
        self.search_timer = None
        self.selected_module_item = None

        self.init_ui()
        self.load_modules()

    def init_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(self, label="Modules")
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

        search_label = wx.StaticText(self, label="Search:")
        filters_sizer.Add(search_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)

        self.search_text = wx.TextCtrl(self, size=wx.Size(300, -1))
        self.search_text.Bind(wx.EVT_TEXT, self.on_search_changed)
        filters_sizer.Add(self.search_text, 0, wx.RIGHT, 10)

        filters_sizer.AddStretchSpacer()

        self.fetch_button = wx.Button(self, label="Fetch")
        self.fetch_button.Bind(wx.EVT_BUTTON, self.on_fetch)
        filters_sizer.Add(self.fetch_button, 0, wx.RIGHT, 10)

        self.fetch_all_button = wx.Button(self, label="Fetch All")
        self.fetch_all_button.Bind(wx.EVT_BUTTON, self.on_fetch_all)
        filters_sizer.Add(self.fetch_all_button, 0, wx.RIGHT, 10)

        self.edit_button = wx.Button(self, label="Edit")
        self.edit_button.Bind(wx.EVT_BUTTON, self.on_edit)
        self.edit_button.Enable(False)
        filters_sizer.Add(self.edit_button, 0)

        main_sizer.Add(filters_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 40)

        main_sizer.AddSpacer(15)

        line = wx.StaticLine(self)
        main_sizer.Add(line, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 40)

        main_sizer.AddSpacer(15)

        self.list_ctrl = wx.ListCtrl(self, style=wx.LC_REPORT | wx.BORDER_SIMPLE)
        self.list_ctrl.AppendColumn("Code", width=150)
        self.list_ctrl.AppendColumn("Name", width=400)
        self.list_ctrl.AppendColumn("Status", width=100)
        self.list_ctrl.AppendColumn("Timestamp", width=150)

        self.list_ctrl.Bind(wx.EVT_RIGHT_UP, self.on_list_right_click)
        self.list_ctrl.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_list_item_selected)
        self.list_ctrl.Bind(wx.EVT_LIST_ITEM_DESELECTED, self.on_list_item_deselected)

        main_sizer.Add(self.list_ctrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 40)

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

        main_sizer.Add(pagination_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 40)

        main_sizer.AddSpacer(40)

        self.SetSizer(main_sizer)

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

    def on_search_changed(self, event):
        self.search_query = self.search_text.GetValue().strip() or None
        self.current_page = 1

        if self.search_timer:
            self.search_timer.Stop()

        self.search_timer = wx.CallLater(300, self.load_modules)

    def load_modules(self):
        if self.status_bar:
            self.status_bar.show_message("Loading modules...")
        self.load_worker = LoadModulesWorker(
            self.repository,
            self.search_query,
            self.current_page,
            self.page_size,
            self.on_modules_callback,
        )
        self.load_worker.start()

    def update_total_label(self):
        plural = "s" if self.total_modules != 1 else ""
        self.records_label.SetLabel(f"{self.total_modules} Module{plural}")
        self.Layout()

    def update_pagination_controls(self):
        total_pages = max(
            (self.total_modules + self.page_size - 1) // self.page_size, 1
        )
        self.page_label.SetLabel(f"Page {self.current_page} of {total_pages}")

        self.prev_button.Enable(self.current_page > 1)
        self.next_button.Enable(self.current_page < total_pages)

    def previous_page(self, event):
        if self.current_page > 1:
            self.current_page -= 1
            if self.status_bar:
                self.status_bar.show_message("Loading modules...")
            self.load_worker = LoadModulesWorker(
                self.repository,
                self.search_query,
                self.current_page,
                self.page_size,
                self.on_modules_callback,
            )
            self.load_worker.start()

    def next_page(self, event):
        total_pages = (self.total_modules + self.page_size - 1) // self.page_size
        if self.current_page < total_pages:
            self.current_page += 1
            if self.status_bar:
                self.status_bar.show_message("Loading modules...")
            self.load_worker = LoadModulesWorker(
                self.repository,
                self.search_query,
                self.current_page,
                self.page_size,
                self.on_modules_callback,
            )
            self.load_worker.start()

    def on_fetch(self, event):
        dialog = FetchModuleDialog(self, self.service, self.status_bar)
        if dialog.ShowModal() == wx.ID_OK:
            self.load_modules()
        dialog.Destroy()

    def on_fetch_all(self, event):
        dialog = wx.MessageDialog(
            self,
            "This will fetch all modules from the CMS and may take a long time.\n\n"
            "The operation will scrape through all pages of the module list and save them to the database.\n"
            "Do you want to continue?",
            "Fetch All Modules - Warning",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
        )

        if dialog.ShowModal() == wx.ID_YES:
            self.fetch_button.Enable(False)
            self.fetch_all_button.Enable(False)

            worker = FetchAllModulesWorker(self.service, self.on_fetch_all_callback)
            worker.start()

        dialog.Destroy()

    def on_fetch_all_callback(self, event_type, *args):
        if event_type == "progress":
            message, current, total = args
            if self.status_bar:
                self.status_bar.show_progress(message, current, total)
        elif event_type == "complete":
            if self.status_bar:
                self.status_bar.clear()
            self.fetch_button.Enable(True)
            self.fetch_all_button.Enable(True)
            self.load_modules()
            wx.MessageBox(
                "All modules have been fetched and saved successfully!",
                "Success",
                wx.OK | wx.ICON_INFORMATION,
            )
        elif event_type == "error":
            error_message = args[0] if args else "Unknown error"
            if self.status_bar:
                self.status_bar.clear()
            self.fetch_button.Enable(True)
            self.fetch_all_button.Enable(True)
            wx.MessageBox(
                f"Error fetching modules: {error_message}",
                "Error",
                wx.OK | wx.ICON_ERROR,
            )

    def on_list_item_selected(self, event):
        item = event.GetIndex()
        if item != wx.NOT_FOUND:
            self.selected_module_item = item
            self.edit_button.Enable(True)

    def on_list_item_deselected(self, event):
        self.selected_module_item = None
        self.edit_button.Enable(False)

    def on_edit(self, event):
        if self.selected_module_item is None:
            wx.MessageBox(
                "Please select a module to edit.",
                "No Selection",
                wx.OK | wx.ICON_INFORMATION,
            )
            return

        module_id = self.list_ctrl.GetItemData(self.selected_module_item)
        module_code = self.list_ctrl.GetItemText(self.selected_module_item, 0)
        module_name = self.list_ctrl.GetItemText(self.selected_module_item, 1)
        module_status = self.list_ctrl.GetItemText(self.selected_module_item, 2)
        module_timestamp = self.list_ctrl.GetItemText(self.selected_module_item, 3)

        module_data = {
            "id": module_id,
            "code": module_code,
            "name": module_name,
            "status": module_status,
            "timestamp": module_timestamp,
        }

        dialog = ModuleFormDialog(module_data, self, self.status_bar)
        if dialog.ShowModal() == wx.ID_OK:
            updated_data = dialog.get_updated_data()

            self.fetch_button.Enable(False)
            self.fetch_all_button.Enable(False)
            self.edit_button.Enable(False)

            self.update_worker = UpdateModuleWorker(
                updated_data["id"],
                {
                    "code": updated_data["code"],
                    "name": updated_data["name"],
                    "status": updated_data["status"],
                    "date_stamp": updated_data["date_stamp"],
                },
                self.service,
                self.on_update_callback,
            )
            self.update_worker.start()
        dialog.Destroy()

    def on_update_callback(self, event_type, *args):
        wx.CallAfter(self._handle_update_event, event_type, *args)

    def _handle_update_event(self, event_type, *args):
        if event_type == "progress":
            message, current, total = args
            if self.status_bar:
                self.status_bar.show_progress(message, current, total)
        elif event_type == "update_finished":
            success, message = args
            if self.status_bar:
                self.status_bar.clear()
            self.fetch_button.Enable(True)
            self.fetch_all_button.Enable(True)
            self.edit_button.Enable(self.selected_module_item is not None)

            if success:
                wx.MessageBox(
                    "Module updated successfully.",
                    "Success",
                    wx.OK | wx.ICON_INFORMATION,
                )
                self.load_modules()
            else:
                wx.MessageBox(message, "Update Failed", wx.OK | wx.ICON_ERROR)
        elif event_type == "error":
            error_msg = args[0]
            wx.MessageBox(error_msg, "Error", wx.OK | wx.ICON_WARNING)

    def on_modules_callback(self, event_type, *args):
        wx.CallAfter(self._handle_modules_event, event_type, *args)

    def _handle_modules_event(self, event_type, *args):
        if event_type == "modules_loaded":
            modules, total = args
            self.total_modules = total
            self.list_ctrl.DeleteAllItems()
            self.selected_module_item = None
            self.edit_button.Enable(False)

            for row, module in enumerate(modules):
                index = self.list_ctrl.InsertItem(row, module.code or "")
                self.list_ctrl.SetItem(index, 1, module.name or "")
                self.list_ctrl.SetItem(index, 2, module.status or "")
                self.list_ctrl.SetItem(index, 3, module.timestamp or "")
                self.list_ctrl.SetItemData(index, module.id)

            self.update_pagination_controls()
            self.update_total_label()
        elif event_type == "modules_error":
            error_msg = args[0]
            print(f"Error loading modules: {error_msg}")
            self.list_ctrl.DeleteAllItems()
            self.selected_module_item = None
            self.edit_button.Enable(False)
            self.page_label.SetLabel("No data available")
            self.records_label.SetLabel("")

        if self.status_bar:
            self.status_bar.clear()
