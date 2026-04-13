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
        self._create_configuration_menu()
        self._create_help_menu()

    def _create_file_menu(self):
        file_menu = wx.Menu()

        upload_item = file_menu.Append(
            wx.ID_ANY, "Upload Data...", "Upload data from another database"
        )
        self.parent.Bind(wx.EVT_MENU, self._on_upload_data, upload_item)

        file_menu.AppendSeparator()

        exit_item = file_menu.Append(wx.ID_EXIT, "Exit", "Exit the application")
        self.parent.Bind(wx.EVT_MENU, self._on_exit, exit_item)

        self.menu_bar.Append(file_menu, "File")

    def _create_configuration_menu(self):
        configuration_menu = wx.Menu()

        forget_item = configuration_menu.Append(
            wx.ID_ANY,
            "Forget Saved Configuration...",
            "Remove the saved country and database connection for the next launch",
        )
        self.parent.Bind(wx.EVT_MENU, self._on_forget_configuration, forget_item)

        self.menu_bar.Append(configuration_menu, "Settings")

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

    def _on_forget_configuration(self, event):
        confirm = wx.MessageBox(
            "This will remove the saved country and database connection for the next launch. The current session will continue using the active configuration until you close the app.\n\nDo you want to continue?",
            "Forget Saved Configuration",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
            self.parent,
        )
        if confirm != wx.YES:
            return

        from base.runtime_config import forget_saved_runtime_settings

        removed = forget_saved_runtime_settings()
        if removed:
            wx.MessageBox(
                "The saved configuration has been removed. Restart the application when you want to choose a new country or database connection.",
                "Configuration Removed",
                wx.OK | wx.ICON_INFORMATION,
                self.parent,
            )
            self.parent.Close()
            return

        wx.MessageBox(
            "There is no saved configuration to remove.",
            "No Saved Configuration",
            wx.OK | wx.ICON_INFORMATION,
            self.parent,
        )
        self.parent.Close()

    def _on_upload_data(self, event):
        from features.upload.upload_dialog import UploadDataDialog

        dlg = UploadDataDialog(self.parent, self.parent.status_bar)
        dlg.ShowModal()
        dlg.Destroy()

    def _show_about(self, event):
        from base.__version__ import __version__

        info = wx.adv.AboutDialogInfo()
        info.SetName("Limkokwing Registry")
        info.SetVersion(__version__)
        info.SetDescription("Limkokwing Registry Desktop Application")
        wx.adv.AboutBox(info)

    def _on_exit(self, event):
        self.parent.Close()
