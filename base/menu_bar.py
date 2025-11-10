import wx
import wx.adv

from base.auth.session_manager import SessionManager
from base.auth.user_details_dialog import UserDetailsDialog


class AppMenuBar:
    def __init__(self, parent, current_user):
        self.parent = parent
        self.current_user = current_user
        self.menu_bar = wx.MenuBar()
        self._create_menus()
        parent.SetMenuBar(self.menu_bar)

    def _create_menus(self):
        self._create_file_menu()
        self._create_help_menu()
        self._create_account_menu()

    def _create_file_menu(self):
        file_menu = wx.Menu()

        exit_item = file_menu.Append(wx.ID_EXIT, "Exit", "Exit the application")
        self.parent.Bind(wx.EVT_MENU, self._on_exit, exit_item)

        self.menu_bar.Append(file_menu, "File")

    def _create_help_menu(self):
        help_menu = wx.Menu()

        check_updates_item = help_menu.Append(
            wx.ID_ANY,
            "Check for Updates...",
            "Check for application updates"
        )
        self.parent.Bind(wx.EVT_MENU, self._on_check_updates, check_updates_item)

        help_menu.AppendSeparator()

        about_item = help_menu.Append(wx.ID_ABOUT, "About", "About Limkokwing Registry")
        self.parent.Bind(wx.EVT_MENU, self._show_about, about_item)

        self.menu_bar.Append(help_menu, "Help")

    def _create_account_menu(self):
        account_menu = wx.Menu()

        user_name_item = account_menu.Append(wx.ID_ANY, self.current_user.name, "Current user")
        user_name_item.Enable(False)

        account_menu.AppendSeparator()

        details_item = account_menu.Append(wx.ID_ANY, "Details", "View account details")
        self.parent.Bind(wx.EVT_MENU, self._on_details, details_item)

        logout_item = account_menu.Append(wx.ID_ANY, "Logout\tCtrl+L", "Logout from the application")
        self.parent.Bind(wx.EVT_MENU, self._on_logout, logout_item)

        self.menu_bar.Append(account_menu, "Account")

    def _on_check_updates(self, event):
        from main import check_for_updates_manual
        check_for_updates_manual(self.parent)

    def _show_about(self, event):
        from base.__version__ import __version__
        info = wx.adv.AboutDialogInfo()
        info.SetName("Limkokwing Registry")
        info.SetVersion(__version__)
        info.SetDescription("Limkokwing Registry Desktop Application")
        wx.adv.AboutBox(info)

    def _on_details(self, event):
        dialog = UserDetailsDialog(self.parent, self.current_user)
        dialog.ShowModal()
        dialog.Destroy()

    def _on_logout(self, event):
        result = wx.MessageBox(
            "Are you sure you want to logout?",
            "Confirm Logout",
            wx.YES_NO | wx.ICON_QUESTION
        )

        if result == wx.YES:
            SessionManager.clear_session()
            wx.MessageBox(
                "You have been logged out. Please restart the application to login again.",
                "Logged Out",
                wx.OK | wx.ICON_INFORMATION
            )
            self.parent.Close()

    def _on_exit(self, event):
        self.parent.Close()
