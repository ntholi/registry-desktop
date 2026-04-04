import json
import logging
import os
import threading
from pathlib import Path

import wx

from base.__version__ import __version__
from base.auto_update import AutoUpdater
from base.logging_config import setup_logging
from base.menu_bar import AppMenuBar
from base.nav import AccordionNavigation
from base.runtime_config import get_current_country_code, get_current_country_label
from base.splash_screen import SplashScreen
from base.status.status_bar import StatusBar
from base.widgets.country_selection_dialog import CountrySelectionDialog
from base.widgets.loading_panel import LoadingPanel
from base.widgets.update_dialog import UpdateDialog
from database.connection import configure_database_urls_for_country
from features.bulk.student_modules import StudentModulesView
from features.bulk.student_programs import StudentProgramsView
from features.bulk.student_semesters import StudentSemestersView
from features.enrollments.module.module_view import ModuleView
from features.enrollments.requests.requests_view import RequestsView
from features.enrollments.student.student_view import StudentView
from features.export.certificates.certificates_view import CertificatesView
from features.export.reports.reports_view import ReportsView
from features.repairs.module_grades import ModuleGradesView
from features.sync.modules.modules_view import ModulesView
from features.sync.structures.structures_view import StructuresView
from features.sync.students import StudentsView
from features.sync.terms.terms_view import TermsView

logger = logging.getLogger(__name__)


class MainWindow(wx.Frame):
    def __init__(self):
        super().__init__(
            None,
            title=f"Limkokwing Registry v{__version__} ({get_current_country_label()})",
            size=wx.Size(1100, 750),
        )

        logger.info("Main window initialized")

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
            "sync_terms": TermsView,
            "bulk_student_modules": StudentModulesView,
            "bulk_student_semesters": StudentSemestersView,
            "bulk_student_programs": StudentProgramsView,
            "enrollment_requests": RequestsView,
            "enrollments_module": ModuleView,
            "enrollments_student": StudentView,
            "repair_module_grades": ModuleGradesView,
            "export_certificates": CertificatesView,
            "export_reports": ReportsView,
        }

        self.view_titles = self._load_view_titles()

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

    def _load_view_titles(self) -> dict[str, str]:
        config_path = Path(__file__).parent / "base" / "nav" / "menu.json"
        titles = {}

        def collect_titles(items):
            for item in items:
                action = item.get("action")
                if action:
                    titles[action] = item["title"]
                submenu = item.get("submenu")
                if submenu:
                    collect_titles(submenu)

        try:
            with open(config_path, "r") as f:
                config = json.load(f)

            collect_titles(config["menu_items"])
        except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
            print(f"Error loading menu titles: {e}")

        return titles

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


def show_main_window():
    try:
        window = MainWindow()
        window.Maximize()
        window.Show()

        check_for_updates_async(window)
    except Exception as e:
        logger.exception(f"Fatal error in application: {e}")
        wx.MessageBox(
            f"Failed to start application: {str(e)}",
            "Application Error",
            wx.OK | wx.ICON_ERROR,
        )
        raise


def select_runtime_country() -> bool:
    dialog = CountrySelectionDialog(None, get_current_country_code())
    result = dialog.ShowModal()

    if result != wx.ID_OK:
        dialog.Destroy()
        return False

    selected_country = dialog.get_selected_country_code()
    dialog.Destroy()

    try:
        configure_database_urls_for_country(selected_country)
    except Exception as exc:
        wx.MessageBox(
            f"Failed to load the {selected_country.title()} configuration: {exc}",
            "Configuration Error",
            wx.OK | wx.ICON_ERROR,
        )
        return False

    return True


def check_for_updates_async(parent_window):
    def check_updates():
        updater = AutoUpdater()
        has_update = updater.check_for_updates()

        if has_update:
            wx.CallAfter(show_update_dialog, parent_window, updater)

    update_thread = threading.Thread(target=check_updates, daemon=True)
    update_thread.start()


def show_update_dialog(parent, updater: AutoUpdater):
    dialog = UpdateDialog(parent, updater)
    result = dialog.ShowModal()
    dialog.Destroy()

    if result == wx.ID_IGNORE:
        logger.info(f"User skipped version {updater.get_latest_version()}")


def check_for_updates_manual(parent):
    from base.widgets.update_dialog import UpdateCheckDialog

    checking_dialog = UpdateCheckDialog(parent)

    def check_updates():
        updater = AutoUpdater()
        has_update = updater.check_for_updates()

        wx.CallAfter(checking_dialog.close_dialog)

        if has_update:
            wx.CallAfter(show_update_dialog, parent, updater)
        else:
            wx.CallAfter(
                wx.MessageBox,
                f"You are running the latest version ({updater.current_version}).",
                "No Updates Available",
                wx.OK | wx.ICON_INFORMATION,
            )

    update_thread = threading.Thread(target=check_updates, daemon=True)
    update_thread.start()

    checking_dialog.ShowModal()
    checking_dialog.Destroy()


def main():
    setup_logging()

    logger.info("Starting Limkokwing Registry Desktop Application")

    database_env = os.getenv("DATABASE_ENV", "local").strip().lower()
    desktop_env = os.getenv("DESKTOP_ENV", "prod").strip().lower()

    if (database_env == "remote" or desktop_env == "prod") and desktop_env == "dev":
        print("\n" + "=" * 60)
        print("WARNING: Using REMOTE database!")
        print("=" * 60 + "\n")
        input("Press any key to continue...")

    app = wx.App()

    if not select_runtime_country():
        return

    splash = SplashScreen(__version__)
    splash.Show()

    wx.Yield()

    splash.close()

    show_main_window()

    app.MainLoop()


if __name__ == "__main__":
    main()
