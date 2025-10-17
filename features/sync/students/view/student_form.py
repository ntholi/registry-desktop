from datetime import datetime

from PySide6.QtCore import QDate, Signal
from PySide6.QtWidgets import (
    QDateEdit,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)


class StudentFormDialog(QDialog):
    student_updated = Signal(dict)

    def __init__(self, student_data, parent=None, status_bar=None):
        super().__init__(parent)
        self.student_data = student_data
        self.status_bar = status_bar
        self.setWindowTitle(f"Update Student: {student_data.get('std_no', '')}")
        self.setModal(True)
        self.setMinimumWidth(400)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        form_layout = QFormLayout()
        form_layout.setSpacing(10)

        student_no_label = QLabel(str(self.student_data.get("std_no", "")))
        form_layout.addRow("Student Number:", student_no_label)

        self.name_input = QLineEdit()
        self.name_input.setText(self.student_data.get("name", "") or "")
        form_layout.addRow("Name:", self.name_input)

        self.gender_input = QLineEdit()
        self.gender_input.setText(self.student_data.get("gender", "") or "")
        form_layout.addRow("Gender:", self.gender_input)

        self.dob_input = QDateEdit()
        self.dob_input.setCalendarPopup(True)
        date_of_birth = self.student_data.get("date_of_birth")
        if date_of_birth:
            if isinstance(date_of_birth, str):
                dt = datetime.fromisoformat(date_of_birth)
                self.dob_input.setDate(QDate(dt.year, dt.month, dt.day))
            else:
                self.dob_input.setDate(
                    QDate(date_of_birth.year, date_of_birth.month, date_of_birth.day)
                )
        else:
            today = datetime.now()
            self.dob_input.setDate(QDate(today.year, today.month, today.day))
        form_layout.addRow("Date of Birth:", self.dob_input)

        self.email_input = QLineEdit()
        self.email_input.setText(self.student_data.get("email", "") or "")
        self.email_input.setPlaceholderText("user@example.com")
        form_layout.addRow("Email:", self.email_input)

        layout.addLayout(form_layout)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.save_student)
        button_layout.addWidget(self.save_button)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

    def save_student(self):
        name = self.name_input.text().strip()
        gender = self.gender_input.text().strip()
        email = self.email_input.text().strip()
        dob = self.dob_input.date().toPython()

        if not name:
            QMessageBox.warning(self, "Validation Error", "Name cannot be empty")
            return

        if email and "@" not in email:
            QMessageBox.warning(self, "Validation Error", "Please enter a valid email")
            return

        updated_data = {
            "std_no": self.student_data.get("std_no"),
            "name": name,
            "gender": gender,
            "date_of_birth": dob,
            "email": email,
        }

        self.student_updated.emit(updated_data)
        self.accept()

    def get_updated_data(self):
        return {
            "std_no": self.student_data.get("std_no"),
            "name": self.name_input.text().strip(),
            "gender": self.gender_input.text().strip(),
            "date_of_birth": self.dob_input.date().toPython(),
            "email": self.email_input.text().strip(),
        }
