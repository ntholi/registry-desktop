import wx
import wx.adv

from base.auth.session_manager import SessionManager


class AppMenuBar:
    def __init__(self, parent):
        self.parent = parent
        self.menu_bar = wx.MenuBar()
        self._create_menus()
        parent.SetMenuBar(self.menu_bar)

    def _create_menus(self):
        self._create_file_menu()

    def _create_file_menu(self):
        file_menu = wx.Menu()

        about_item = file_menu.Append(wx.ID_ABOUT, "About", "About Limkokwing Registry")
        self.parent.Bind(wx.EVT_MENU, self._show_about, about_item)

        file_menu.AppendSeparator()

        logout_item = file_menu.Append(wx.ID_ANY, "Logout\tCtrl+L", "Logout from the application")
        self.parent.Bind(wx.EVT_MENU, self._on_logout, logout_item)

        exit_item = file_menu.Append(wx.ID_EXIT, "Exit", "Exit the application")
        self.parent.Bind(wx.EVT_MENU, self._on_exit, exit_item)

        self.menu_bar.Append(file_menu, "File")

    def _show_about(self, event):
        info = wx.adv.AboutDialogInfo()
        info.SetName("Limkokwing Registry")
        info.SetVersion("1.0")
        info.SetDescription("Limkokwing Registry Desktop Application")
        wx.adv.AboutBox(info)

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
