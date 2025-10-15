from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class CertificatesView(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)

        label = QLabel("Certificates Export View")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
