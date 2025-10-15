from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.orm import Session

from database import Student, get_engine


class StudentsView(QWidget):
    def __init__(self):
        super().__init__()
        self.current_page = 1
        self.page_size = 30
        self.total_students = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)

        title = QLabel("Students")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            [
                "Student No",
                "Name",
                "National ID",
                "Gender",
                "Phone",
                "Marital Status",
                "Religion",
            ]
        )
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

        pagination_layout = QHBoxLayout()
        pagination_layout.addStretch()

        self.prev_button = QPushButton("Previous")
        self.prev_button.clicked.connect(self.previous_page)
        self.prev_button.setEnabled(False)
        pagination_layout.addWidget(self.prev_button)

        self.page_label = QLabel()
        pagination_layout.addWidget(self.page_label)

        self.next_button = QPushButton("Next")
        self.next_button.clicked.connect(self.next_page)
        pagination_layout.addWidget(self.next_button)

        pagination_layout.addStretch()
        layout.addLayout(pagination_layout)

        self.load_students()

    def load_students(self):
        try:
            engine = get_engine(use_local=True)
            with Session(engine) as session:
                offset = (self.current_page - 1) * self.page_size

                query = session.query(Student).order_by(Student.stdNo)
                self.total_students = query.count()

                students = query.offset(offset).limit(self.page_size).all()

                self.table.setRowCount(len(students))

                for row, student in enumerate(students):
                    self.table.setItem(row, 0, QTableWidgetItem(str(student.stdNo)))
                    self.table.setItem(
                        row, 1, QTableWidgetItem(str(student.name or ""))
                    )
                    self.table.setItem(
                        row, 2, QTableWidgetItem(str(student.nationalId or ""))
                    )
                    self.table.setItem(
                        row, 3, QTableWidgetItem(str(student.gender or ""))
                    )
                    self.table.setItem(
                        row, 4, QTableWidgetItem(str(student.phone1 or ""))
                    )
                    self.table.setItem(
                        row, 5, QTableWidgetItem(str(student.maritalStatus or ""))
                    )
                    self.table.setItem(
                        row, 6, QTableWidgetItem(str(student.religion or ""))
                    )

                self.update_pagination_controls()

        except Exception as e:
            print(f"Error loading students: {str(e)}")
            self.table.setRowCount(0)
            self.page_label.setText("No data available")

    def update_pagination_controls(self):
        total_pages = (self.total_students + self.page_size - 1) // self.page_size
        self.page_label.setText(f"Page {self.current_page} of {total_pages}")

        self.prev_button.setEnabled(self.current_page > 1)
        self.next_button.setEnabled(self.current_page < total_pages)

    def previous_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.load_students()

    def next_page(self):
        total_pages = (self.total_students + self.page_size - 1) // self.page_size
        if self.current_page < total_pages:
            self.current_page += 1
            self.load_students()
