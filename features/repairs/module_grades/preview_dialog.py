from dataclasses import dataclass
from typing import Optional

import wx

from .repository import StudentModuleGradeRow


def is_borderline_marks(marks: str) -> bool:
    if not marks:
        return False
    try:
        marks_int = int(marks)
        last_digit = marks_int % 10
        return last_digit == 4 or last_digit == 9
    except ValueError:
        return False


@dataclass
class GradePreviewItem:
    std_no: str
    name: str
    module_code: str
    module_name: str
    old_marks: str
    old_grade: str
    new_marks: str
    new_grade: str
    student_module: StudentModuleGradeRow
    skip_reason: Optional[str] = None


class RecalculatePreviewDialog(wx.Dialog):
    def __init__(
        self,
        parent,
        preview_items: list[GradePreviewItem],
        skip_pp_default: bool = True,
        skip_borderline_default: bool = True,
    ):
        super().__init__(
            parent,
            title="Grade Recalculation Preview",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
            size=wx.Size(800, 600),
        )

        self.preview_items = preview_items
        self.skip_pp = skip_pp_default
        self.skip_borderline = skip_borderline_default
        self.filtered_items: list[GradePreviewItem] = []

        self.init_ui()
        self.update_list()
        self.CenterOnParent()

    def init_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        main_sizer.AddSpacer(15)

        header_label = wx.StaticText(
            self, label="Review the grade changes before applying"
        )
        font = header_label.GetFont()
        font.PointSize = 11
        font = font.Bold()
        header_label.SetFont(font)
        main_sizer.Add(header_label, 0, wx.LEFT | wx.RIGHT, 20)

        main_sizer.AddSpacer(15)

        options_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.skip_pp_checkbox = wx.CheckBox(self, label="Skip PP grades")
        self.skip_pp_checkbox.SetValue(self.skip_pp)
        self.skip_pp_checkbox.Bind(wx.EVT_CHECKBOX, self.on_skip_option_changed)
        options_sizer.Add(
            self.skip_pp_checkbox, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 20
        )

        self.skip_borderline_checkbox = wx.CheckBox(
            self, label="Skip Borderline (44, 49, 54, 59, etc.)"
        )
        self.skip_borderline_checkbox.SetValue(self.skip_borderline)
        self.skip_borderline_checkbox.Bind(wx.EVT_CHECKBOX, self.on_skip_option_changed)
        options_sizer.Add(self.skip_borderline_checkbox, 0, wx.ALIGN_CENTER_VERTICAL)

        options_sizer.AddStretchSpacer()

        self.summary_label = wx.StaticText(self, label="")
        options_sizer.Add(self.summary_label, 0, wx.ALIGN_CENTER_VERTICAL)

        main_sizer.Add(options_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)

        main_sizer.AddSpacer(10)

        self.list_ctrl = wx.ListCtrl(self, style=wx.LC_REPORT | wx.BORDER_SIMPLE)

        self.list_ctrl.AppendColumn("Student No", width=100)
        self.list_ctrl.AppendColumn("Name", width=180)
        self.list_ctrl.AppendColumn("Module Code", width=100)
        self.list_ctrl.AppendColumn("Module Name", width=200)
        self.list_ctrl.AppendColumn("Old Grade", width=90)
        self.list_ctrl.AppendColumn("New Grade", width=90)

        main_sizer.Add(self.list_ctrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)

        main_sizer.AddSpacer(10)

        info_panel = wx.Panel(self)
        info_sizer = wx.BoxSizer(wx.VERTICAL)

        skip_info = wx.StaticText(
            info_panel,
            label="The following grades are always skipped: ANN, DNS, EXP, DEF",
        )
        skip_info.SetForegroundColour(wx.Colour(100, 100, 100))
        info_sizer.Add(skip_info, 0)

        info_panel.SetSizer(info_sizer)
        main_sizer.Add(info_panel, 0, wx.LEFT | wx.RIGHT, 20)

        main_sizer.AddSpacer(15)

        button_sizer = wx.StdDialogButtonSizer()

        self.apply_button = wx.Button(self, wx.ID_OK, "Apply Changes")
        self.apply_button.SetDefault()
        button_sizer.AddButton(self.apply_button)

        cancel_button = wx.Button(self, wx.ID_CANCEL, "Cancel")
        button_sizer.AddButton(cancel_button)

        button_sizer.Realize()

        main_sizer.Add(
            button_sizer, 0, wx.ALIGN_RIGHT | wx.LEFT | wx.RIGHT | wx.BOTTOM, 20
        )

        self.SetSizer(main_sizer)

    def on_skip_option_changed(self, event):
        self.skip_pp = self.skip_pp_checkbox.GetValue()
        self.skip_borderline = self.skip_borderline_checkbox.GetValue()
        self.update_list()

    def update_list(self):
        self.list_ctrl.DeleteAllItems()
        self.filtered_items = []

        will_update = 0
        will_skip = 0
        no_change = 0

        for item in self.preview_items:
            if item.skip_reason:
                if "PP" in item.skip_reason and not self.skip_pp:
                    pass
                else:
                    will_skip += 1
                    continue

            if self.skip_pp and item.old_grade and item.old_grade.upper() == "PP":
                will_skip += 1
                continue

            if self.skip_borderline and is_borderline_marks(item.new_marks):
                will_skip += 1
                continue

            if item.old_marks == item.new_marks and item.old_grade == item.new_grade:
                no_change += 1
                continue

            self.filtered_items.append(item)

            old_grade_display = (
                f"{item.old_marks}/{item.old_grade}"
                if item.old_marks or item.old_grade
                else ""
            )
            new_grade_display = (
                f"{item.new_marks}/{item.new_grade}"
                if item.new_marks or item.new_grade
                else ""
            )

            index = self.list_ctrl.InsertItem(
                self.list_ctrl.GetItemCount(), item.std_no
            )
            self.list_ctrl.SetItem(index, 1, item.name or "")
            self.list_ctrl.SetItem(index, 2, item.module_code or "")
            self.list_ctrl.SetItem(index, 3, item.module_name or "")
            self.list_ctrl.SetItem(index, 4, old_grade_display)
            self.list_ctrl.SetItem(index, 5, new_grade_display)

            will_update += 1

        self.summary_label.SetLabel(
            f"Will update: {will_update} | Skipped: {will_skip} | No change: {no_change}"
        )

        self.apply_button.Enable(will_update > 0)
        self.Layout()

    def get_skip_pp(self) -> bool:
        return self.skip_pp

    def get_items_to_update(self) -> list[GradePreviewItem]:
        return self.filtered_items
