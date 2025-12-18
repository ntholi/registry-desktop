import threading

import wx

from .repository import TermRepository
from .service import TermSyncService


class FetchAllTermsWorker(threading.Thread):
    def __init__(self, service, callback):
        super().__init__(daemon=True)
        self.service = service
        self.callback = callback
        self.should_stop = False

    def run(self):
        try:
            self.service.fetch_and_save_all_terms(progress_callback=self.progress)
            wx.CallAfter(lambda: self.callback("complete", None))
        except Exception as e:
            error_msg = str(e)
            wx.CallAfter(lambda: self.callback("error", error_msg))

    def progress(self, message, current, total):
        if not self.should_stop:
            wx.CallAfter(lambda: self.callback("progress", message, current, total))


class LoadTermsWorker(threading.Thread):
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
            terms, total = self.repository.fetch_terms(
                search_query=self.search_query,
                page=self.page,
                page_size=self.page_size,
            )
            self.callback("terms_loaded", terms, total)
        except Exception as e:
            self.callback("terms_error", str(e))

    def stop(self):
        self.should_stop = True


class TermsView(wx.Panel):
    def __init__(self, parent, status_bar=None):
        super().__init__(parent)
        self.status_bar = status_bar
        self.current_page = 1
        self.page_size = 30
        self.total_terms = 0
        self.search_query = None
        self.repository = TermRepository()
        self.service = TermSyncService(self.repository)
        self.load_worker = None
        self.search_timer = None

        self.init_ui()
        self.load_terms()

    def init_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(self, label="Terms")
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

        filters_sizer = wx.BoxSizer(wx.HORIZONTAL)

        search_label = wx.StaticText(self, label="Search:")
        filters_sizer.Add(search_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)

        self.search_text = wx.TextCtrl(self, size=wx.Size(300, -1))
        self.search_text.Bind(wx.EVT_TEXT, self.on_search_changed)
        filters_sizer.Add(self.search_text, 0, wx.RIGHT, 10)

        filters_sizer.AddStretchSpacer()

        self.fetch_all_button = wx.Button(self, label="Fetch All")
        self.fetch_all_button.Bind(wx.EVT_BUTTON, self.on_fetch_all)
        filters_sizer.Add(self.fetch_all_button, 0)

        main_sizer.Add(filters_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 40)

        main_sizer.AddSpacer(15)

        line = wx.StaticLine(self)
        main_sizer.Add(line, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 40)

        main_sizer.AddSpacer(15)

        self.list_ctrl = wx.ListCtrl(self, style=wx.LC_REPORT | wx.BORDER_SIMPLE)
        self.list_ctrl.AppendColumn("Code", width=120)
        self.list_ctrl.AppendColumn("Name", width=250)
        self.list_ctrl.AppendColumn("Year", width=80)
        self.list_ctrl.AppendColumn("Start Date", width=120)
        self.list_ctrl.AppendColumn("End Date", width=120)
        self.list_ctrl.AppendColumn("Active", width=80)

        self.list_ctrl.Bind(wx.EVT_RIGHT_UP, self.on_list_right_click)

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

        self.search_timer = wx.CallLater(300, self.load_terms)

    def load_terms(self):
        if self.status_bar:
            self.status_bar.show_message("Loading terms...")
        self.load_worker = LoadTermsWorker(
            self.repository,
            self.search_query,
            self.current_page,
            self.page_size,
            self.on_terms_callback,
        )
        self.load_worker.start()

    def update_total_label(self):
        plural = "s" if self.total_terms != 1 else ""
        self.records_label.SetLabel(f"{self.total_terms} Term{plural}")
        self.Layout()

    def update_pagination_controls(self):
        total_pages = max((self.total_terms + self.page_size - 1) // self.page_size, 1)
        self.page_label.SetLabel(f"Page {self.current_page} of {total_pages}")

        self.prev_button.Enable(self.current_page > 1)
        self.next_button.Enable(self.current_page < total_pages)

    def previous_page(self, event):
        if self.current_page > 1:
            self.current_page -= 1
            if self.status_bar:
                self.status_bar.show_message("Loading terms...")
            self.load_worker = LoadTermsWorker(
                self.repository,
                self.search_query,
                self.current_page,
                self.page_size,
                self.on_terms_callback,
            )
            self.load_worker.start()

    def next_page(self, event):
        total_pages = (self.total_terms + self.page_size - 1) // self.page_size
        if self.current_page < total_pages:
            self.current_page += 1
            if self.status_bar:
                self.status_bar.show_message("Loading terms...")
            self.load_worker = LoadTermsWorker(
                self.repository,
                self.search_query,
                self.current_page,
                self.page_size,
                self.on_terms_callback,
            )
            self.load_worker.start()

    def on_fetch_all(self, event):
        dialog = wx.MessageDialog(
            self,
            "This will fetch all terms from the CMS.\n\n"
            "The operation will scrape through all pages of the term list and save them to the database.\n"
            "Do you want to continue?",
            "Fetch All Terms - Warning",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
        )

        if dialog.ShowModal() == wx.ID_YES:
            self.fetch_all_button.Enable(False)

            worker = FetchAllTermsWorker(self.service, self.on_fetch_all_callback)
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
            self.fetch_all_button.Enable(True)
            self.load_terms()
            wx.MessageBox(
                "All terms have been fetched and saved successfully!",
                "Success",
                wx.OK | wx.ICON_INFORMATION,
            )
        elif event_type == "error":
            error_message = args[0] if args else "Unknown error"
            if self.status_bar:
                self.status_bar.clear()
            self.fetch_all_button.Enable(True)
            wx.MessageBox(
                f"Error fetching terms: {error_message}",
                "Error",
                wx.OK | wx.ICON_ERROR,
            )

    def on_terms_callback(self, event_type, *args):
        wx.CallAfter(self._handle_terms_event, event_type, *args)

    def _handle_terms_event(self, event_type, *args):
        if event_type == "terms_loaded":
            terms, total = args
            self.total_terms = total
            self.list_ctrl.DeleteAllItems()

            for row, term in enumerate(terms):
                index = self.list_ctrl.InsertItem(row, term.code or "")
                self.list_ctrl.SetItem(index, 1, term.name or "")
                self.list_ctrl.SetItem(index, 2, str(term.year) if term.year else "")
                self.list_ctrl.SetItem(index, 3, term.start_date or "")
                self.list_ctrl.SetItem(index, 4, term.end_date or "")
                self.list_ctrl.SetItem(index, 5, "Yes" if term.is_active else "No")
                self.list_ctrl.SetItemData(index, term.id)

            self.update_pagination_controls()
            self.update_total_label()
        elif event_type == "terms_error":
            error_msg = args[0]
            print(f"Error loading terms: {error_msg}")
            self.list_ctrl.DeleteAllItems()
            self.page_label.SetLabel("No data available")
            self.records_label.SetLabel("")

        if self.status_bar:
            self.status_bar.clear()
