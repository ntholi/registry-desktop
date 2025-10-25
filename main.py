import wx

from base.menu_bar import AppMenuBar
from base.nav import AccordionNavigation
from base.splash_screen import SplashScreen
from base.status.status_bar import StatusBar
from base.widgets.loading_panel import LoadingPanel
from features.enrollments.module.module_view import ModuleView
from features.enrollments.requests.requests_view import RequestsView
from features.enrollments.student.student_view import StudentView
from features.export.certificates.certificates_view import CertificatesView
from features.export.reports.reports_view import ReportsView
from features.sync.modules.modules_view import ModulesView
from features.sync.structures.structures_view import StructuresView
from features.sync.students import StudentsView


class MainWindow(wx.Frame):
    def __init__(self):
        super().__init__(None, title="Limkokwing Registry", size=wx.Size(1100, 750))

        self.menu_bar = AppMenuBar(self)

        panel = wx.Panel(self)
        root_sizer = wx.BoxSizer(wx.VERTICAL)

        main_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.navigation = AccordionNavigation(panel, self.on_navigation_clicked)
        main_sizer.Add(self.navigation, 0, wx.EXPAND)

        separator = wx.StaticLine(panel, style=wx.LI_VERTICAL)
        main_sizer.Add(separator, 0, wx.EXPAND)

        self.content_panel = wx.Panel(panel)
        self.content_sizer = wx.BoxSizer(wx.VERTICAL)
        self.content_panel.SetSizer(self.content_sizer)

        self.status_bar = StatusBar(panel)

        self.view_classes = {
            "sync_students": StudentsView,
            "sync_structures": StructuresView,
            "sync_modules": ModulesView,
            "enrollment_requests": RequestsView,
            "enrollments_module": ModuleView,
            "enrollments_student": StudentView,
            "export_certificates": CertificatesView,
            "export_reports": ReportsView,
        }

        self.view_titles = {
            "sync_students": "Students",
            "sync_structures": "Structures",
            "sync_modules": "Modules",
            "enrollment_requests": "Enrollment Requests",
            "enrollments_module": "Enrollment Modules",
            "enrollments_student": "Student Enrollments",
            "export_certificates": "Certificates",
            "export_reports": "Reports",
        }

        self.views = {}

        self.loading_panel = LoadingPanel(self.content_panel, "Loading view...")
        self.content_sizer.Add(self.loading_panel, 1, wx.EXPAND)
        self.loading_panel.Hide()

        self.current_view = None
        self.current_action = None
        self.pending_action = None
        self._is_loading_view = False
        self._show_loading("sync_students")
        try:
            self.current_view = self._get_or_create_view("sync_students")
            self.current_action = "sync_students"
            self.current_view.Show()
            self.content_panel.Layout()
        finally:
            self._hide_loading()

        self.navigation.select_action("sync_students")

        main_sizer.Add(self.content_panel, 1, wx.EXPAND)

        root_sizer.Add(main_sizer, 1, wx.EXPAND)

        separator = wx.StaticLine(panel, style=wx.LI_HORIZONTAL)
        root_sizer.Add(separator, 0, wx.EXPAND)

        root_sizer.Add(self.status_bar, 0, wx.EXPAND)

        panel.SetSizer(root_sizer)

    def on_navigation_clicked(self, action):
        if action not in self.view_classes:
            return

        if action == self.current_action:
            return

        if self._is_loading_view:
            self.pending_action = action
            return

        self._show_loading(action)
        wx.CallAfter(self._activate_view, action)

    def _get_or_create_view(self, action):
        view = self.views.get(action)
        if view is None:
            view_class = self.view_classes[action]
            view = view_class(self.content_panel, self.status_bar)
            self.views[action] = view
            self.content_sizer.Add(view, 1, wx.EXPAND)
            view.Hide()
            self.content_panel.Layout()
        return view

    def _activate_view(self, action):
        try:
            view = self._get_or_create_view(action)
            if self.current_view:
                self.current_view.Hide()
            view.Show()
            self.current_view = view
            self.current_action = action
            self.content_panel.Layout()
        finally:
            self._hide_loading()
            if self.pending_action and self.pending_action != action:
                next_action = self.pending_action
                self.pending_action = None
                self.on_navigation_clicked(next_action)
            else:
                self.pending_action = None

    def _show_loading(self, action):
        title = self.view_titles.get(action, "data")
        self.loading_panel.set_message(f"Loading {title}...")
        if self.current_view and self.current_view.IsShown():
            self.current_view.Hide()
        if not self.loading_panel.IsShown():
            self.loading_panel.Show()
        self.loading_panel.start()
        self.loading_panel.Raise()
        self.content_panel.Layout()
        self._is_loading_view = True
        wx.SafeYield()

    def _hide_loading(self):
        if self.loading_panel.IsShown():
            self.loading_panel.Hide()
        self.loading_panel.stop()
        self.content_panel.Layout()
        self._is_loading_view = False
        wx.SafeYield()


def main():
    app = wx.App()

    splash = SplashScreen()
    splash.Show()

    wx.Yield()

    window = MainWindow()

    splash.close()

    window.Maximize()
    window.Show()
    app.MainLoop()


if __name__ == "__main__":
    main()
