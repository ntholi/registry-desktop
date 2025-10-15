from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class StudentView(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)

        label = QLabel("Student Enrollment View")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
