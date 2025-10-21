import wx

from ..repository import StudentRepository


class StudentDetailPanel(wx.Panel):
    def __init__(self, parent, on_close_callback):
        super().__init__(parent)
        self.on_close_callback = on_close_callback
        self.repository = StudentRepository()
        self.current_student_no = None

        self.init_ui()

    def init_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        top_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.program_combobox = wx.ComboBox(
            self, style=wx.CB_READONLY, size=wx.Size(300, -1)
        )
        self.program_combobox.Bind(wx.EVT_COMBOBOX, self.on_program_selected)
        top_sizer.Add(self.program_combobox, 0, wx.RIGHT, 10)

        top_sizer.AddStretchSpacer()

        self.close_button = wx.Button(self, label="Close", size=wx.Size(80, -1))
        self.close_button.Bind(wx.EVT_BUTTON, self.on_close)
        top_sizer.Add(self.close_button, 0)

        main_sizer.Add(top_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)

        main_sizer.AddSpacer(15)

        semesters_label = wx.StaticText(self, label="Semesters")
        font = semesters_label.GetFont()
        font.PointSize = 10
        font = font.Bold()
        semesters_label.SetFont(font)
        main_sizer.Add(semesters_label, 0, wx.LEFT | wx.RIGHT, 20)

        main_sizer.AddSpacer(10)

        self.semesters_list = wx.ListCtrl(
            self, style=wx.LC_REPORT | wx.BORDER_SIMPLE, size=wx.Size(-1, 110)
        )
        self.semesters_list.AppendColumn("Term", width=100)
        self.semesters_list.AppendColumn("Semester", width=80)
        self.semesters_list.AppendColumn("Status", width=100)
        self.semesters_list.AppendColumn("", width=60)

        main_sizer.Add(self.semesters_list, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)

        main_sizer.AddSpacer(20)

        modules_label = wx.StaticText(self, label="Modules")
        font = modules_label.GetFont()
        font.PointSize = 10
        font = font.Bold()
        modules_label.SetFont(font)
        main_sizer.Add(modules_label, 0, wx.LEFT | wx.RIGHT, 20)

        main_sizer.AddSpacer(10)

        self.modules_list = wx.ListCtrl(
            self, style=wx.LC_REPORT | wx.BORDER_SIMPLE, size=wx.Size(-1, 300)
        )
        self.modules_list.AppendColumn("Code", width=100)
        self.modules_list.AppendColumn("Name", width=200)
        self.modules_list.AppendColumn("Status", width=100)
        self.modules_list.AppendColumn("Marks", width=70)
        self.modules_list.AppendColumn("Grade", width=70)
        self.modules_list.AppendColumn("", width=60)

        main_sizer.Add(self.modules_list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)

        main_sizer.AddSpacer(20)

        self.SetSizer(main_sizer)

    def load_student_programs(self, student_no):
        self.current_student_no = student_no
        self.program_combobox.Clear()

        try:
            programs = self.repository.get_student_programs(student_no)

            if not programs:
                self.program_combobox.Append("No programs found", None)
                self.program_combobox.SetSelection(0)
                self.program_combobox.Enable(False)
                return

            self.program_combobox.Enable(True)
            for program in programs:
                display_text = self._format_program_display(program)
                self.program_combobox.Append(display_text, program)

            if programs:
                self.program_combobox.SetSelection(0)
                self.load_program_data()

        except Exception as e:
            print(f"Error loading student programs: {str(e)}")
            self.program_combobox.Append("Error loading programs", None)
            self.program_combobox.SetSelection(0)
            self.program_combobox.Enable(False)

    def on_program_selected(self, event):
        self.load_program_data()

    def load_program_data(self):
        program = self.get_selected_program()
        if not program or not hasattr(program, "id"):
            self.clear_tables()
            return

        student_program_id = program.id
        self.load_semesters(student_program_id)
        self.load_modules(student_program_id)

    def load_semesters(self, student_program_id):
        self.semesters_list.DeleteAllItems()

        try:
            semesters = self.repository.get_student_semesters(student_program_id)

            for row, semester in enumerate(semesters):
                index = self.semesters_list.InsertItem(row, str(semester.term or ""))
                self.semesters_list.SetItem(
                    index, 1, str(semester.semester_number or "")
                )
                self.semesters_list.SetItem(index, 2, str(semester.status or ""))
                self.semesters_list.SetItem(index, 3, "Edit")

        except Exception as e:
            print(f"Error loading semesters: {str(e)}")

    def load_modules(self, student_program_id):
        self.modules_list.DeleteAllItems()

        try:
            modules = self.repository.get_student_modules(student_program_id)

            for row, module in enumerate(modules):
                index = self.modules_list.InsertItem(row, str(module.module_code or ""))
                self.modules_list.SetItem(index, 1, str(module.module_name or ""))
                self.modules_list.SetItem(index, 2, str(module.status or ""))
                self.modules_list.SetItem(index, 3, str(module.marks or ""))
                self.modules_list.SetItem(index, 4, str(module.grade or ""))
                self.modules_list.SetItem(index, 5, "Edit")

        except Exception as e:
            print(f"Error loading modules: {str(e)}")

    def clear_tables(self):
        self.semesters_list.DeleteAllItems()
        self.modules_list.DeleteAllItems()

    def _format_program_display(self, program):
        parts = []

        if hasattr(program, "program_name") and program.program_name:
            parts.append(program.program_name)

        if hasattr(program, "status") and program.status:
            parts.append(f"({program.status})")

        return " ".join(parts) if parts else "Unknown Program"

    def get_selected_program(self):
        selection = self.program_combobox.GetSelection()
        if selection != wx.NOT_FOUND:
            return self.program_combobox.GetClientData(selection)
        return None

    def on_close(self, event):
        if self.on_close_callback:
            self.on_close_callback()
