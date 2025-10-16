from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..repository import StudentRepository
from ..service import StudentSyncService
from .student_form import StudentFormDialog


class PullStudentsWorker(QThread):
    progress = Signal(int, int, str)
    finished = Signal(int, int)
    error = Signal(str)

    def __init__(self, student_numbers, sync_service):
        super().__init__()
        self.student_numbers = student_numbers
        self.sync_service = sync_service
        self.should_stop = False

    def run(self):
        success_count = 0
        failed_count = 0

        for idx, std_no in enumerate(self.student_numbers):
            if self.should_stop:
                break

            try:
                self.progress.emit(idx + 1, len(self.student_numbers), std_no)

                was_updated = self.sync_service.pull_student(std_no)

                if was_updated:
                    success_count += 1
                else:
                    failed_count += 1

            except Exception as e:
                self.error.emit(f"Error pulling student {std_no}: {str(e)}")
                failed_count += 1

        self.finished.emit(success_count, failed_count)

    def stop(self):
        self.should_stop = True


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
        self.pull_worker = None
        self.repository = StudentRepository()
        self.sync_service = StudentSyncService(self.repository)

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

        self.pull_button = QPushButton("Pull")
        self.pull_button.setIcon(
            self.style().standardIcon(self.style().StandardPixmap.SP_ArrowDown)
        )
        self.pull_button.clicked.connect(self.pull_students)
        self.pull_button.setEnabled(False)
        search_layout.addWidget(self.pull_button)

        self.push_button = QPushButton("Push")
        self.push_button.setIcon(
            self.style().standardIcon(self.style().StandardPixmap.SP_ArrowUp)
        )
        self.push_button.clicked.connect(self.push_students)
        self.push_button.setEnabled(False)
        search_layout.addWidget(self.push_button)

        layout.addWidget(search_container)

        selection_container = QFrame()
        selection_layout = QHBoxLayout(selection_container)
        selection_layout.setContentsMargins(0, 0, 0, 0)
        selection_layout.setSpacing(10)

        self.select_all_checkbox = QCheckBox("Select All")
        self.select_all_checkbox.stateChanged.connect(self.on_select_all_changed)
        selection_layout.addWidget(self.select_all_checkbox)

        self.selection_label = QLabel("0 selected")
        self.selection_label.setStyleSheet("color: #666; margin-left: 10px;")
        selection_layout.addWidget(self.selection_label)

        self.progress_label = QLabel("")
        self.progress_label.setStyleSheet(
            "color: #0066cc; margin-left: 20px; font-weight: bold;"
        )
        self.progress_label.hide()
        selection_layout.addWidget(self.progress_label)

        selection_layout.addStretch()

        layout.addWidget(selection_container)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            [
                "",
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
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Fixed
        )
        self.table.setColumnWidth(0, 40)
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
            schools = self.repository.list_active_schools()
            for school in schools:
                self.school_filter.addItem(str(school.name))
                self.school_filter.setItemData(
                    self.school_filter.count() - 1, school.id
                )

            self.load_programs_for_school(None)

            terms = self.repository.list_terms()
            for term in terms:
                self.term_filter.addItem(str(term))
                self.term_filter.setItemData(self.term_filter.count() - 1, term)

            semesters = self.repository.list_semesters()
            for sem in semesters:
                self.semester_filter.addItem(f"Semester {sem}")
                self.semester_filter.setItemData(self.semester_filter.count() - 1, sem)

        except Exception as e:
            print(f"Error loading filter options: {str(e)}")

    def load_programs_for_school(self, school_id):
        try:
            while self.program_filter.count() > 1:
                self.program_filter.removeItem(1)

            programs = self.repository.list_programs(school_id)

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
            students, total = self.repository.fetch_students(
                school_id=self.selected_school_id,
                program_id=self.selected_program_id,
                term=self.selected_term,
                semester_number=self.selected_semester_number,
                search_query=self.search_query,
                page=self.current_page,
                page_size=self.page_size,
            )

            self.total_students = total
            self.table.setRowCount(len(students))

            for row, student in enumerate(students):
                checkbox = QCheckBox()
                checkbox.setStyleSheet("margin-left: 12px;")
                checkbox.stateChanged.connect(self.on_row_selection_changed)
                checkbox_widget = QWidget()
                checkbox_layout = QHBoxLayout(checkbox_widget)
                checkbox_layout.addWidget(checkbox)
                checkbox_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                checkbox_layout.setContentsMargins(0, 0, 0, 0)
                self.table.setCellWidget(row, 0, checkbox_widget)

                self.table.setItem(row, 1, QTableWidgetItem(student.std_no))
                self.table.setItem(row, 2, QTableWidgetItem(student.name or ""))
                self.table.setItem(row, 3, QTableWidgetItem(student.gender or ""))
                self.table.setItem(row, 4, QTableWidgetItem(student.faculty_code or ""))
                self.table.setItem(row, 5, QTableWidgetItem(student.program_name or ""))

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

    def on_select_all_changed(self, state):
        check_state = Qt.CheckState(state)
        if check_state == Qt.CheckState.PartiallyChecked:
            return

        is_checked = check_state == Qt.CheckState.Checked
        for row in range(self.table.rowCount()):
            checkbox_widget = self.table.cellWidget(row, 0)
            if checkbox_widget:
                checkbox = checkbox_widget.findChild(QCheckBox)
                if checkbox:
                    checkbox.setChecked(is_checked)

    def on_row_selection_changed(self):
        selected_count = self.get_selected_count()
        self.selection_label.setText(f"{selected_count} selected")
        self.pull_button.setEnabled(selected_count > 0)
        self.push_button.setEnabled(selected_count > 0)

        self.select_all_checkbox.blockSignals(True)
        if selected_count == 0:
            self.select_all_checkbox.setCheckState(Qt.CheckState.Unchecked)
        elif selected_count == self.table.rowCount():
            self.select_all_checkbox.setCheckState(Qt.CheckState.Checked)
        else:
            self.select_all_checkbox.setCheckState(Qt.CheckState.PartiallyChecked)
        self.select_all_checkbox.blockSignals(False)

    def get_selected_count(self):
        count = 0
        for row in range(self.table.rowCount()):
            checkbox_widget = self.table.cellWidget(row, 0)
            if checkbox_widget:
                checkbox = checkbox_widget.findChild(QCheckBox)
                if checkbox and checkbox.isChecked():
                    count += 1
        return count

    def get_selected_student_numbers(self):
        selected_students = []
        for row in range(self.table.rowCount()):
            checkbox_widget = self.table.cellWidget(row, 0)
            if checkbox_widget:
                checkbox = checkbox_widget.findChild(QCheckBox)
                if checkbox and checkbox.isChecked():
                    student_no_item = self.table.item(row, 1)
                    if student_no_item:
                        selected_students.append(student_no_item.text())
        return selected_students

    def get_selected_students_data(self):
        selected_data = []
        for row in range(self.table.rowCount()):
            checkbox_widget = self.table.cellWidget(row, 0)
            if checkbox_widget:
                checkbox = checkbox_widget.findChild(QCheckBox)
                if checkbox and checkbox.isChecked():
                    std_no_item = self.table.item(row, 1)
                    name_item = self.table.item(row, 2)
                    gender_item = self.table.item(row, 3)
                    if std_no_item and name_item and gender_item:
                        student_data = {
                            "std_no": std_no_item.text(),
                            "name": name_item.text(),
                            "gender": gender_item.text(),
                        }
                        selected_data.append(student_data)
        return selected_data

    def pull_students(self):
        selected_students = self.get_selected_student_numbers()
        if not selected_students:
            return

        reply = QMessageBox.question(
            self,
            "Confirm Pull",
            f"Pull data for {len(selected_students)} student(s) from the web?\n\nThis will update the local database with data from the registry system.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        self.pull_button.setEnabled(False)
        self.push_button.setEnabled(False)
        self.progress_label.show()

        self.pull_worker = PullStudentsWorker(selected_students, self.sync_service)
        self.pull_worker.progress.connect(self.on_pull_progress)
        self.pull_worker.finished.connect(self.on_pull_finished)
        self.pull_worker.error.connect(self.on_pull_error)
        self.pull_worker.start()

    def on_pull_progress(self, current, total, std_no):
        self.progress_label.setText(f"Pulling student {current}/{total}: {std_no}...")

    def on_pull_finished(self, success_count, failed_count):
        self.progress_label.hide()
        self.pull_button.setEnabled(True)
        self.push_button.setEnabled(True)

        if failed_count > 0:
            QMessageBox.information(
                self,
                "Pull Complete",
                f"Successfully pulled {success_count} student(s).\n{failed_count} failed.",
            )
        else:
            QMessageBox.information(
                self,
                "Pull Complete",
                f"Successfully pulled data for {success_count} student(s).",
            )

        self.load_students()

    def on_pull_error(self, error_msg):
        QMessageBox.warning(self, "Error", error_msg)

    def push_students(self):
        selected_students = self.get_selected_students_data()
        if not selected_students:
            return

        if len(selected_students) == 1:
            student_data = selected_students[0]
            dialog = StudentFormDialog(student_data, self)
            if dialog.exec():
                updated_data = dialog.get_updated_data()
                try:
                    success, message = self.sync_service.push_student(
                        updated_data["std_no"],
                        {
                            "name": updated_data["name"],
                            "gender": updated_data["gender"],
                            "date_of_birth": updated_data["date_of_birth"],
                            "email": updated_data["email"],
                        },
                    )

                    if success:
                        QMessageBox.information(
                            self,
                            "Success",
                            f"Student {updated_data['std_no']} updated successfully.",
                        )
                        self.load_students()
                    else:
                        QMessageBox.critical(self, "Update Failed", message)
                except Exception as e:
                    QMessageBox.critical(
                        self, "Error", f"Failed to update student: {str(e)}"
                    )
        else:
            QMessageBox.information(
                self,
                "Multiple Students",
                "Please select only one student to update.",
            )
