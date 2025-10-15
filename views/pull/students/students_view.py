from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox,
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
from sqlalchemy import distinct, or_
from sqlalchemy.orm import Session

from database import (
    Program,
    School,
    Structure,
    Student,
    StudentProgram,
    StudentSemester,
    get_engine,
)


class StudentsView(QWidget):
    def __init__(self):
        super().__init__()
        self.current_page = 1
        self.page_size = 30
        self.total_students = 0
        self.search_query = ""
        self.selected_school_id = None
        self.selected_program_id = None
        self.selected_term = None
        self.selected_semester_number = None
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

        filters_container = QFrame()
        filters_layout = QHBoxLayout(filters_container)
        filters_layout.setContentsMargins(0, 0, 0, 0)
        filters_layout.setSpacing(10)

        filters_label = QLabel("Filters:")
        filters_layout.addWidget(filters_label)

        self.school_filter = QComboBox()
        self.school_filter.addItem("All Schools", None)
        self.school_filter.currentIndexChanged.connect(self.on_school_changed)
        self.school_filter.setMinimumWidth(150)
        filters_layout.addWidget(self.school_filter)

        self.program_filter = QComboBox()
        self.program_filter.addItem("All Programs", None)
        self.program_filter.currentIndexChanged.connect(self.on_filter_changed)
        self.program_filter.setMinimumWidth(150)
        filters_layout.addWidget(self.program_filter)

        self.term_filter = QComboBox()
        self.term_filter.addItem("All Terms", None)
        self.term_filter.currentIndexChanged.connect(self.on_filter_changed)
        self.term_filter.setMinimumWidth(150)
        filters_layout.addWidget(self.term_filter)

        self.semester_filter = QComboBox()
        self.semester_filter.addItem("All Semesters", None)
        self.semester_filter.currentIndexChanged.connect(self.on_filter_changed)
        self.semester_filter.setMinimumWidth(150)
        filters_layout.addWidget(self.semester_filter)

        self.clear_filters_button = QPushButton("Clear Filters")
        self.clear_filters_button.clicked.connect(self.clear_filters)
        filters_layout.addWidget(self.clear_filters_button)

        filters_layout.addStretch()

        layout.addWidget(filters_container)

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
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            [
                "Student No",
                "Name",
                "Gender",
                "Faculty Code",
                "Program Name",
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

        self.load_filter_options()
        self.load_students()

    def load_filter_options(self):
        try:
            engine = get_engine(use_local=True)
            with Session(engine) as session:
                schools = (
                    session.query(School.id, School.name)
                    .filter(School.is_active == True)
                    .order_by(School.name)
                    .all()
                )
                for school in schools:
                    self.school_filter.addItem(str(school.name))
                    self.school_filter.setItemData(
                        self.school_filter.count() - 1, school.id
                    )

                self.load_programs_for_school(None)

                terms = (
                    session.query(distinct(StudentSemester.term))
                    .filter(StudentSemester.term.isnot(None))
                    .order_by(StudentSemester.term.desc())
                    .all()
                )
                for term_tuple in terms:
                    term = term_tuple[0]
                    self.term_filter.addItem(str(term))
                    self.term_filter.setItemData(self.term_filter.count() - 1, term)

                semesters = (
                    session.query(distinct(StudentSemester.semester_number))
                    .filter(StudentSemester.semester_number.isnot(None))
                    .order_by(StudentSemester.semester_number)
                    .all()
                )
                for sem_tuple in semesters:
                    sem = sem_tuple[0]
                    self.semester_filter.addItem(f"Semester {sem}")
                    self.semester_filter.setItemData(
                        self.semester_filter.count() - 1, sem
                    )

        except Exception as e:
            print(f"Error loading filter options: {str(e)}")

    def load_programs_for_school(self, school_id):
        try:
            while self.program_filter.count() > 1:
                self.program_filter.removeItem(1)

            engine = get_engine(use_local=True)
            with Session(engine) as session:
                q = session.query(Program.id, Program.name)
                if school_id:
                    q = q.filter(Program.school_id == school_id)
                programs = q.order_by(Program.name).all()

                for program in programs:
                    self.program_filter.addItem(str(program.name))
                    self.program_filter.setItemData(
                        self.program_filter.count() - 1, program.id
                    )
        except Exception as e:
            print(f"Error loading programs: {str(e)}")

    def on_school_changed(self, index):
        self.selected_school_id = self.school_filter.currentData()
        self.load_programs_for_school(self.selected_school_id)
        self.term_filter.setCurrentIndex(0)
        self.semester_filter.setCurrentIndex(0)
        self.selected_program_id = None
        self.selected_term = None
        self.selected_semester_number = None
        self.current_page = 1
        self.load_students()

    def on_filter_changed(self):
        self.selected_school_id = self.school_filter.currentData()
        self.selected_program_id = self.program_filter.currentData()
        self.selected_term = self.term_filter.currentData()
        self.selected_semester_number = self.semester_filter.currentData()
        self.current_page = 1
        self.load_students()

    def clear_filters(self):
        self.school_filter.setCurrentIndex(0)
        self.program_filter.setCurrentIndex(0)
        self.term_filter.setCurrentIndex(0)
        self.semester_filter.setCurrentIndex(0)
        self.selected_school_id = None
        self.selected_program_id = None
        self.selected_term = None
        self.selected_semester_number = None
        self.current_page = 1
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

                query = (
                    session.query(
                        Student.std_no,
                        Student.name,
                        Student.gender,
                        School.code.label("faculty_code"),
                        Program.name.label("program_name"),
                    )
                    .outerjoin(
                        StudentProgram,
                        (Student.std_no == StudentProgram.std_no)
                        & (StudentProgram.status == "Active"),
                    )
                    .outerjoin(Structure, StudentProgram.structure_id == Structure.id)
                    .outerjoin(Program, Structure.program_id == Program.id)
                    .outerjoin(School, Program.school_id == School.id)
                    .distinct()
                )

                if self.selected_school_id:
                    query = query.filter(Program.school_id == self.selected_school_id)

                if self.selected_program_id:
                    query = query.filter(Program.id == self.selected_program_id)

                if self.selected_term or self.selected_semester_number:
                    query = query.join(
                        StudentSemester,
                        StudentProgram.id == StudentSemester.student_program_id,
                    )

                    if self.selected_term:
                        query = query.filter(StudentSemester.term == self.selected_term)

                    if self.selected_semester_number:
                        query = query.filter(
                            StudentSemester.semester_number
                            == self.selected_semester_number
                        )

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
                        row, 2, QTableWidgetItem(str(student.gender or ""))
                    )
                    self.table.setItem(
                        row, 3, QTableWidgetItem(str(student.faculty_code or ""))
                    )
                    self.table.setItem(
                        row, 4, QTableWidgetItem(str(student.program_name or ""))
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
