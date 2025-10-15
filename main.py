import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)

from navigation import AccordionNavigation


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Limkokwing Registry")
        self.setMinimumSize(1100, 750)

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Navigation panel
        self.navigation = AccordionNavigation()
        self.navigation.navigation_clicked.connect(self.on_navigation_clicked)
        main_layout.addWidget(self.navigation)

        # Vertical separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setLineWidth(1)
        main_layout.addWidget(separator)

        # Content area
        self.content_area = QWidget()
        content_layout = QVBoxLayout(self.content_area)
        content_layout.setContentsMargins(40, 40, 40, 40)

        # Welcome message
        self.content_label = QLabel(
            "Welcome to Limkokwing Registry\n\nSelect an item from the navigation menu to get started"
        )
        self.content_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.content_label.setWordWrap(True)

        content_font = QFont()
        content_font.setPointSize(12)
        self.content_label.setFont(content_font)

        content_layout.addWidget(self.content_label)

        main_layout.addWidget(self.content_area, 1)

    def on_navigation_clicked(self, action):
        """Handle navigation item clicks"""
        action_text = action.replace("_", " ").title()
        self.content_label.setText(
            f"📄 {action_text}\n\nContent for {action_text} will be displayed here.\nThis is where you'll manage {action_text.lower()}."
        )


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
