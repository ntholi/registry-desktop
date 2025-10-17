from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QWidget


class StatusBar(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedHeight(30)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(10)

        self.message_label = QLabel()
        layout.addWidget(self.message_label)

        layout.addStretch()

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedWidth(200)
        self.progress_bar.setFixedHeight(18)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        self.hide()

    @Slot(str, int, int)
    def show_progress(self, message: str, current: int, total: int):
        self.message_label.setText(message)
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.progress_bar.show()
        self.show()

    @Slot(str)
    def show_message(self, message: str):
        self.message_label.setText(message)
        self.progress_bar.hide()
        self.show()

    @Slot()
    def clear(self):
        self.message_label.clear()
        self.progress_bar.hide()
        self.hide()
