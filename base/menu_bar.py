from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction, QColor, QPalette
from PySide6.QtWidgets import QApplication, QMenuBar, QMessageBox, QStyleFactory


class AppMenuBar:
    def __init__(self, parent):
        self.parent = parent
        self.settings = QSettings("Limkokwing", "Registry")
        self.menu_bar = parent.menuBar()
        self._create_menus()
        self._apply_saved_theme()

    def _is_system_dark_mode(self):
        app = QApplication.instance()
        if isinstance(app, QApplication):
            palette = app.palette()
            window_color = palette.color(QPalette.ColorRole.Window)
            return window_color.lightness() < 128
        return False

    def _create_menus(self):
        self._create_file_menu()
        self._create_theme_menu()

    def _create_file_menu(self):
        file_menu = self.menu_bar.addMenu("File")

        about_action = QAction("About", self.parent)
        about_action.triggered.connect(self._show_about)
        file_menu.addAction(about_action)

        file_menu.addSeparator()

        exit_action = QAction("Exit", self.parent)
        exit_action.triggered.connect(self.parent.close)
        file_menu.addAction(exit_action)

    def _create_theme_menu(self):
        theme_menu = self.menu_bar.addMenu("Theme")

        system_action = QAction("System", self.parent)
        system_action.triggered.connect(lambda: self._set_theme("system"))
        theme_menu.addAction(system_action)

        theme_menu.addSeparator()

        light_action = QAction("Light", self.parent)
        light_action.triggered.connect(lambda: self._set_theme("light"))
        theme_menu.addAction(light_action)

        dark_action = QAction("Dark", self.parent)
        dark_action.triggered.connect(lambda: self._set_theme("dark"))
        theme_menu.addAction(dark_action)

    def _show_about(self):
        QMessageBox.about(
            self.parent,
            "About Limkokwing Registry",
            "Limkokwing Registry Desktop Application\n\nVersion 1.0",
        )

    def _set_theme(self, theme: str):
        app = QApplication.instance()
        if not isinstance(app, QApplication):
            return

        app.setStyleSheet("")

        if theme == "system":
            if "windowsvista" in QStyleFactory.keys():
                app.setStyle("windowsvista")
            app.setPalette(app.style().standardPalette())
            if self._is_system_dark_mode():
                app.setProperty("colorScheme", Qt.ColorScheme.Dark)
            else:
                app.setProperty("colorScheme", Qt.ColorScheme.Light)
        else:
            if "Fusion" in QStyleFactory.keys():
                app.setStyle("Fusion")
            palette = self._dark_palette() if theme == "dark" else self._light_palette()
            app.setPalette(palette)
            if theme == "dark":
                app.setProperty("colorScheme", Qt.ColorScheme.Dark)
            else:
                app.setProperty("colorScheme", Qt.ColorScheme.Light)

        self.settings.setValue("theme", theme)

    def _apply_saved_theme(self):
        saved_theme = self.settings.value("theme", "system")
        if isinstance(saved_theme, str):
            self._set_theme(saved_theme)
        else:
            self._set_theme("system")

    def _dark_palette(self) -> QPalette:
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(37, 37, 38))
        palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Base, QColor(30, 30, 30))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(45, 45, 48))
        palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Button, QColor(45, 45, 48))
        palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 122, 204))
        palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(53, 53, 53))
        palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Link, QColor(0, 122, 204))
        palette.setColor(
            QPalette.ColorGroup.Disabled,
            QPalette.ColorRole.Text,
            QColor(127, 127, 127),
        )
        palette.setColor(
            QPalette.ColorGroup.Disabled,
            QPalette.ColorRole.ButtonText,
            QColor(127, 127, 127),
        )
        palette.setColor(
            QPalette.ColorGroup.Disabled,
            QPalette.ColorRole.WindowText,
            QColor(127, 127, 127),
        )
        return palette

    def _light_palette(self) -> QPalette:
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(245, 245, 245))
        palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.black)
        palette.setColor(QPalette.ColorRole.Base, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(233, 233, 233))
        palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.black)
        palette.setColor(QPalette.ColorRole.Button, QColor(245, 245, 245))
        palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.black)
        palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 120, 215))
        palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.black)
        palette.setColor(QPalette.ColorRole.Link, QColor(0, 120, 215))
        palette.setColor(
            QPalette.ColorGroup.Disabled,
            QPalette.ColorRole.Text,
            QColor(160, 160, 160),
        )
        palette.setColor(
            QPalette.ColorGroup.Disabled,
            QPalette.ColorRole.ButtonText,
            QColor(160, 160, 160),
        )
        palette.setColor(
            QPalette.ColorGroup.Disabled,
            QPalette.ColorRole.WindowText,
            QColor(160, 160, 160),
        )
        return palette
