from PySide6.QtCore import QSettings
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMessageBox


class AppMenuBar:
    def __init__(self, parent):
        self.parent = parent
        self.settings = QSettings("Limkokwing", "Registry")
        self.menu_bar = parent.menuBar()
        self._create_menus()

    def _create_menus(self):
        self._create_file_menu()

    def _create_file_menu(self):
        file_menu = self.menu_bar.addMenu("File")

        about_action = QAction("About", self.parent)
        about_action.triggered.connect(self._show_about)
        file_menu.addAction(about_action)

        file_menu.addSeparator()

        exit_action = QAction("Exit", self.parent)
        exit_action.triggered.connect(self.parent.close)
        file_menu.addAction(exit_action)

    def _show_about(self):
        QMessageBox.about(
            self.parent,
            "About Limkokwing Registry",
            "Limkokwing Registry Desktop Application\n\nVersion 1.0",
        )
