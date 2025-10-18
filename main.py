import sys

import wx

from base.menu_bar import AppMenuBar
from base.nav import AccordionNavigation
from base.status.status_bar import StatusBar
from features.enrollments.approved.approved_view import ApprovedView
from features.enrollments.module.module_view import ModuleView
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

        self.status_bar = StatusBar(panel)

        self.views = {
            "sync_students": StudentsView(self.content_panel, self.status_bar),
            "sync_structures": StructuresView(self.content_panel),
            "sync_modules": ModulesView(self.content_panel),
            "enrollments_approved": ApprovedView(self.content_panel),
            "enrollments_module": ModuleView(self.content_panel),
            "enrollments_student": StudentView(self.content_panel),
            "export_certificates": CertificatesView(self.content_panel),
            "export_reports": ReportsView(self.content_panel),
        }

        self.current_view = self.views["sync_students"]

        for view in self.views.values():
            self.content_sizer.Add(view, 1, wx.EXPAND)
            if view is self.current_view:
                view.Show()
            else:
                view.Hide()

        self.content_panel.SetSizer(self.content_sizer)
        main_sizer.Add(self.content_panel, 1, wx.EXPAND)

        root_sizer.Add(main_sizer, 1, wx.EXPAND)

        separator = wx.StaticLine(panel, style=wx.LI_HORIZONTAL)
        root_sizer.Add(separator, 0, wx.EXPAND)

        root_sizer.Add(self.status_bar, 0, wx.EXPAND)

        panel.SetSizer(root_sizer)

    def on_navigation_clicked(self, action):
        if action in self.views:
            self.current_view.Hide()
            view = self.views[action]
            view.Show()
            self.current_view = view
            self.content_panel.Layout()


def main():
    app = wx.App()
    window = MainWindow()
    window.Maximize()
    window.Show()
    app.MainLoop()


if __name__ == "__main__":
    main()
