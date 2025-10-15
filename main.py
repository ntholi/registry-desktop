import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from navigation import AccordionNavigation
from views.enrollments.approved.approved_view import ApprovedView
from views.enrollments.module.module_view import ModuleView
from views.enrollments.student.student_view import StudentView
from views.export.certificates.certificates_view import CertificatesView
from views.export.reports.reports_view import ReportsView
from views.pull.modules.modules_view import ModulesView
from views.pull.structures.structures_view import StructuresView
from views.pull.students.students_view import StudentsView


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

        # Content area with stacked widget
        self.content_stack = QStackedWidget()

        # Welcome page
        welcome_widget = QWidget()
        welcome_layout = QVBoxLayout(welcome_widget)
        welcome_layout.setContentsMargins(40, 40, 40, 40)
        welcome_label = QLabel(
            "Welcome to Limkokwing Registry\n\nSelect an item from the navigation menu to get started"
        )
        welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_label.setWordWrap(True)
        content_font = QFont()
        content_font.setPointSize(12)
        welcome_label.setFont(content_font)
        welcome_layout.addWidget(welcome_label)

        self.content_stack.addWidget(welcome_widget)

        # Initialize all views
        self.views = {
            "pull_students": StudentsView(),
            "pull_structures": StructuresView(),
            "pull_modules": ModulesView(),
            "enrollments_approved": ApprovedView(),
            "enrollments_module": ModuleView(),
            "enrollments_student": StudentView(),
            "export_certificates": CertificatesView(),
            "export_reports": ReportsView(),
        }

        # Add all views to stack
        for view in self.views.values():
            self.content_stack.addWidget(view)

        main_layout.addWidget(self.content_stack, 1)

    def on_navigation_clicked(self, action):
        """Handle navigation item clicks"""
        if action in self.views:
            view = self.views[action]
            self.content_stack.setCurrentWidget(view)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
