from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class ReportsView(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)

        label = QLabel("Reports Export View")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
