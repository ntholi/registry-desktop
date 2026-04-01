import wx
import wx.adv


class AppMenuBar:
    def __init__(self, parent):
        self.parent = parent
        self.menu_bar = wx.MenuBar()
        self._create_menus()
        parent.SetMenuBar(self.menu_bar)

    def _create_menus(self):
        self._create_file_menu()
        self._create_help_menu()

    def _create_file_menu(self):
        file_menu = wx.Menu()

        exit_item = file_menu.Append(wx.ID_EXIT, "Exit", "Exit the application")
        self.parent.Bind(wx.EVT_MENU, self._on_exit, exit_item)

        self.menu_bar.Append(file_menu, "File")

    def _create_help_menu(self):
        help_menu = wx.Menu()

        check_updates_item = help_menu.Append(
            wx.ID_ANY, "Check for Updates...", "Check for application updates"
        )
        self.parent.Bind(wx.EVT_MENU, self._on_check_updates, check_updates_item)

        help_menu.AppendSeparator()

        about_item = help_menu.Append(wx.ID_ABOUT, "About", "About Limkokwing Registry")
        self.parent.Bind(wx.EVT_MENU, self._show_about, about_item)

        self.menu_bar.Append(help_menu, "Help")

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

    def _on_exit(self, event):
        self.parent.Close()
