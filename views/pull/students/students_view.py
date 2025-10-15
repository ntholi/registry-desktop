from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import or_
from sqlalchemy.orm import Session

from database import Student, get_engine


class StudentsView(QWidget):
    def __init__(self):
        super().__init__()
        self.current_page = 1
        self.page_size = 30
        self.total_students = 0
        self.search_query = ""
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.perform_search)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(20)

        title = QLabel("Students")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        self.total_label = QLabel()
        self.total_label.setStyleSheet("font-size: 14px; color: #666;")
        header_layout.addWidget(self.total_label)

        layout.addLayout(header_layout)

        search_container = QFrame()
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(10)

        search_label = QLabel("Search:")
        search_layout.addWidget(search_label)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "Search by student number, name, or national ID..."
        )
        self.search_input.textChanged.connect(self.on_search_changed)
        self.search_input.setMinimumWidth(400)
        search_layout.addWidget(self.search_input)

        self.clear_search_button = QPushButton("Clear")
        self.clear_search_button.clicked.connect(self.clear_search)
        self.clear_search_button.setEnabled(False)
        search_layout.addWidget(self.clear_search_button)

        search_layout.addStretch()

        layout.addWidget(search_container)

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
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

        pagination_layout = QHBoxLayout()
        pagination_layout.addStretch()

        self.prev_button = QPushButton("Previous")
        self.prev_button.clicked.connect(self.previous_page)
        self.prev_button.setEnabled(False)
        pagination_layout.addWidget(self.prev_button)

        self.page_label = QLabel()
        self.page_label.setStyleSheet("margin: 0 15px;")
        pagination_layout.addWidget(self.page_label)

        self.next_button = QPushButton("Next")
        self.next_button.clicked.connect(self.next_page)
        pagination_layout.addWidget(self.next_button)

        pagination_layout.addStretch()
        layout.addLayout(pagination_layout)

        self.load_students()

    def on_search_changed(self, text):
        self.clear_search_button.setEnabled(bool(text))
        self.search_timer.stop()
        self.search_timer.start(500)

    def clear_search(self):
        self.search_input.clear()
        self.search_query = ""
        self.current_page = 1
        self.load_students()

    def perform_search(self):
        self.search_query = self.search_input.text().strip()
        self.current_page = 1
        self.load_students()

    def load_students(self):
        try:
            engine = get_engine(use_local=True)
            with Session(engine) as session:
                offset = (self.current_page - 1) * self.page_size

                query = session.query(Student)

                if self.search_query:
                    search_term = f"%{self.search_query}%"
                    query = query.filter(
                        or_(
                            Student.std_no.like(search_term),
                            Student.name.like(search_term),
                            Student.national_id.like(search_term),
                        )
                    )

                query = query.order_by(Student.std_no)
                self.total_students = query.count()

                students = query.offset(offset).limit(self.page_size).all()

                self.table.setRowCount(len(students))

                for row, student in enumerate(students):
                    self.table.setItem(row, 0, QTableWidgetItem(str(student.std_no)))
                    self.table.setItem(
                        row, 1, QTableWidgetItem(str(student.name or ""))
                    )
                    self.table.setItem(
                        row, 2, QTableWidgetItem(str(student.national_id or ""))
                    )
                    self.table.setItem(
                        row, 3, QTableWidgetItem(str(student.gender or ""))
                    )
                    self.table.setItem(
                        row, 4, QTableWidgetItem(str(student.phone1 or ""))
                    )
                    self.table.setItem(
                        row, 5, QTableWidgetItem(str(student.marital_status or ""))
                    )
                    self.table.setItem(
                        row, 6, QTableWidgetItem(str(student.religion or ""))
                    )

                self.update_pagination_controls()
                self.update_total_label()

        except Exception as e:
            print(f"Error loading students: {str(e)}")
            self.table.setRowCount(0)
            self.page_label.setText("No data available")
            self.total_label.setText("")

    def update_total_label(self):
        if self.search_query:
            self.total_label.setText(
                f"Found {self.total_students} student{'s' if self.total_students != 1 else ''}"
            )
        else:
            self.total_label.setText(
                f"Total: {self.total_students} student{'s' if self.total_students != 1 else ''}"
            )

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
