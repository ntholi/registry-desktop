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
        top_sizer.Add(self.program_combobox, 0, wx.RIGHT, 10)

        self.close_button = wx.Button(self, label="Close", size=wx.Size(80, -1))
        self.close_button.Bind(wx.EVT_BUTTON, self.on_close)
        top_sizer.Add(self.close_button, 0)

        main_sizer.Add(top_sizer, 0, wx.LEFT | wx.RIGHT, 20)

        main_sizer.AddSpacer(20)

        main_sizer.AddStretchSpacer()

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

        except Exception as e:
            print(f"Error loading student programs: {str(e)}")
            self.program_combobox.Append("Error loading programs", None)
            self.program_combobox.SetSelection(0)
            self.program_combobox.Enable(False)

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
