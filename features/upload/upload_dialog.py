import threading
from collections import defaultdict

import wx

from base import get_logger
from base.status.status_bar import StatusBar
from tools.upload_data import (
    AnalysisResult,
    Conflict,
    analyze_differences,
    create_source_engine,
    run_merge,
)

logger = get_logger(__name__)


class ConflictDetailDialog(wx.Dialog):
    def __init__(
        self,
        parent: wx.Window,
        field_name: str,
        conflicts: list[Conflict],
        use_source: set[tuple[int, str]],
    ):
        super().__init__(
            parent,
            title=f"Conflicts: {field_name} ({len(conflicts)})",
            size=wx.Size(750, 500),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self.conflicts = conflicts
        self.use_source = use_source.copy()

        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.AddSpacer(15)

        header = wx.StaticText(self, label=f"Conflicts for '{field_name}'")
        header_font = header.GetFont()
        header_font.PointSize = 12
        header_font = header_font.Bold()
        header.SetFont(header_font)
        sizer.Add(header, 0, wx.LEFT | wx.RIGHT, 20)

        sizer.AddSpacer(8)

        desc = wx.StaticText(
            self,
            label=f"{len(conflicts)} records have different values in source and live databases. "
            "Check items to use the source value. Unchecked items keep the live database value.",
        )
        desc.Wrap(700)
        desc.SetForegroundColour(wx.Colour(100, 100, 100))
        sizer.Add(desc, 0, wx.LEFT | wx.RIGHT, 20)

        sizer.AddSpacer(12)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        select_all_btn = wx.Button(self, label="Select All")
        deselect_all_btn = wx.Button(self, label="Deselect All")
        btn_sizer.Add(select_all_btn, 0, wx.RIGHT, 8)
        btn_sizer.Add(deselect_all_btn, 0)
        sizer.Add(btn_sizer, 0, wx.LEFT | wx.RIGHT, 20)

        sizer.AddSpacer(8)

        self.list_ctrl = wx.ListCtrl(self, style=wx.LC_REPORT | wx.BORDER_SIMPLE)
        self.list_ctrl.EnableCheckBoxes(True)
        self.list_ctrl.AppendColumn("Student No", width=100)
        self.list_ctrl.AppendColumn("Name", width=210)
        self.list_ctrl.AppendColumn("Live Value", width=170)
        self.list_ctrl.AppendColumn("Source Value", width=170)

        for i, c in enumerate(conflicts):
            idx = self.list_ctrl.InsertItem(i, str(c.std_no))
            self.list_ctrl.SetItem(idx, 1, c.student_name)
            self.list_ctrl.SetItem(idx, 2, c.target_value)
            self.list_ctrl.SetItem(idx, 3, c.source_value)
            if (c.std_no, c.field_name) in self.use_source:
                self.list_ctrl.CheckItem(idx, True)

        sizer.Add(self.list_ctrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)

        sizer.AddSpacer(15)

        dialog_btn_sizer = wx.StdDialogButtonSizer()
        ok_btn = wx.Button(self, wx.ID_OK)
        ok_btn.SetDefault()
        cancel_btn = wx.Button(self, wx.ID_CANCEL)
        dialog_btn_sizer.AddButton(ok_btn)
        dialog_btn_sizer.AddButton(cancel_btn)
        dialog_btn_sizer.Realize()
        sizer.Add(
            dialog_btn_sizer, 0, wx.ALIGN_RIGHT | wx.LEFT | wx.RIGHT | wx.BOTTOM, 20
        )

        self.SetSizer(sizer)
        self.CenterOnParent()

        select_all_btn.Bind(wx.EVT_BUTTON, self._on_select_all)
        deselect_all_btn.Bind(wx.EVT_BUTTON, self._on_deselect_all)

    def _on_select_all(self, event: wx.CommandEvent) -> None:
        for i in range(self.list_ctrl.GetItemCount()):
            self.list_ctrl.CheckItem(i, True)

    def _on_deselect_all(self, event: wx.CommandEvent) -> None:
        for i in range(self.list_ctrl.GetItemCount()):
            self.list_ctrl.CheckItem(i, False)

    def get_use_source(self) -> set[tuple[int, str]]:
        result: set[tuple[int, str]] = set()
        for i, c in enumerate(self.conflicts):
            if self.list_ctrl.IsItemChecked(i):
                result.add((c.std_no, c.field_name))
        return result


class UploadDataDialog(wx.Dialog):
    def __init__(self, parent: wx.Window, status_bar: StatusBar):
        super().__init__(
            parent,
            title="Upload Data",
            size=wx.Size(680, 680),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self.status_bar = status_bar
        self.analysis: AnalysisResult | None = None
        self.source_engine = None
        self.target_engine = None
        self.use_source: set[tuple[int, str]] = set()
        self.conflicts_by_field: dict[str, list[Conflict]] = {}
        self.field_actions: dict[str, str] = {}

        main_sizer = wx.BoxSizer(wx.VERTICAL)

        main_sizer.AddSpacer(20)

        title = wx.StaticText(self, label="Upload Data")
        title_font = title.GetFont()
        title_font.PointSize = 14
        title_font = title_font.Bold()
        title.SetFont(title_font)
        main_sizer.Add(title, 0, wx.LEFT | wx.RIGHT, 20)

        main_sizer.AddSpacer(6)

        subtitle = wx.StaticText(
            self,
            label="Upload student data from the local registry to the live database.",
        )
        subtitle.SetForegroundColour(wx.Colour(100, 100, 100))
        main_sizer.Add(subtitle, 0, wx.LEFT | wx.RIGHT, 20)

        main_sizer.AddSpacer(15)

        separator_top = wx.StaticLine(self, style=wx.LI_HORIZONTAL)
        main_sizer.Add(separator_top, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)

        main_sizer.AddSpacer(15)

        url_label = wx.StaticText(self, label="Live Database URL")
        url_label_font = url_label.GetFont()
        url_label_font = url_label_font.Bold()
        url_label.SetFont(url_label_font)
        main_sizer.Add(url_label, 0, wx.LEFT | wx.RIGHT, 20)

        main_sizer.AddSpacer(6)

        url_row = wx.BoxSizer(wx.HORIZONTAL)
        self.url_input = wx.TextCtrl(self, size=wx.Size(350, -1))
        self.url_input.SetHint("postgresql://user:pass@host/dbname")
        url_row.Add(self.url_input, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        self.analyze_btn = wx.Button(self, label="Analyze")
        url_row.Add(self.analyze_btn, 0)
        main_sizer.Add(url_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)

        main_sizer.AddSpacer(15)

        self.progress_label = wx.StaticText(self, label="")
        main_sizer.Add(self.progress_label, 0, wx.LEFT | wx.RIGHT, 20)
        self.progress_gauge = wx.Gauge(self, range=100, size=wx.Size(-1, 18))
        main_sizer.Add(
            self.progress_gauge, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 20
        )
        self.progress_label.Hide()
        self.progress_gauge.Hide()

        self.results_panel = wx.Panel(self)
        results_sizer = wx.BoxSizer(wx.VERTICAL)

        summary_label = wx.StaticText(self.results_panel, label="Analysis Summary")
        summary_font = summary_label.GetFont()
        summary_font.PointSize = 11
        summary_font = summary_font.Bold()
        summary_label.SetFont(summary_font)
        results_sizer.Add(summary_label, 0, wx.BOTTOM, 10)

        self.summary_grid = wx.FlexGridSizer(cols=2, vgap=6, hgap=20)
        self.summary_grid.AddGrowableCol(1, 1)

        self.summary_labels: dict[str, wx.StaticText] = {}
        for key, label_text in [
            ("students", "Students to add"),
            ("fields", "Fields to fill"),
            ("education", "Education records to add"),
            ("kins", "Next of Kin records to add"),
        ]:
            label = wx.StaticText(self.results_panel, label=label_text)
            label.SetForegroundColour(wx.Colour(100, 100, 100))
            value = wx.StaticText(self.results_panel, label="0")
            value_font = value.GetFont()
            value_font = value_font.Bold()
            value.SetFont(value_font)
            self.summary_grid.Add(label, 0, wx.ALIGN_LEFT)
            self.summary_grid.Add(value, 0, wx.ALIGN_LEFT)
            self.summary_labels[key] = value

        results_sizer.Add(self.summary_grid, 0, wx.EXPAND | wx.BOTTOM, 15)

        conflicts_header = wx.StaticText(self.results_panel, label="Conflicts")
        conflicts_font = conflicts_header.GetFont()
        conflicts_font.PointSize = 11
        conflicts_font = conflicts_font.Bold()
        conflicts_header.SetFont(conflicts_font)
        results_sizer.Add(conflicts_header, 0, wx.BOTTOM, 8)

        self.conflicts_desc = wx.StaticText(self.results_panel, label="")
        self.conflicts_desc.SetForegroundColour(wx.Colour(100, 100, 100))
        self.conflicts_desc.Wrap(600)
        results_sizer.Add(self.conflicts_desc, 0, wx.BOTTOM, 8)

        self.conflict_list = wx.ListCtrl(
            self.results_panel,
            style=wx.LC_REPORT | wx.BORDER_SIMPLE,
            size=wx.Size(-1, 140),
        )
        self.conflict_list.AppendColumn("Field", width=150)
        self.conflict_list.AppendColumn("Conflicts", width=80)
        self.conflict_list.AppendColumn("Action", width=160)
        results_sizer.Add(self.conflict_list, 1, wx.EXPAND | wx.BOTTOM, 8)

        conflict_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.toggle_action_btn = wx.Button(self.results_panel, label="Toggle Action")
        self.review_btn = wx.Button(self.results_panel, label="Review Details\u2026")
        conflict_btn_sizer.Add(self.toggle_action_btn, 0, wx.RIGHT, 8)
        conflict_btn_sizer.Add(self.review_btn, 0)
        results_sizer.Add(conflict_btn_sizer, 0)

        self.results_panel.SetSizer(results_sizer)
        main_sizer.Add(
            self.results_panel, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 20
        )
        self.results_panel.Hide()

        main_sizer.AddStretchSpacer()

        separator_btm = wx.StaticLine(self, style=wx.LI_HORIZONTAL)
        main_sizer.Add(separator_btm, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)

        main_sizer.AddSpacer(12)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_sizer.AddStretchSpacer()
        self.upload_btn = wx.Button(self, label="Upload")
        self.upload_btn.Disable()
        close_btn = wx.Button(self, wx.ID_CANCEL, label="Close")
        btn_sizer.Add(self.upload_btn, 0, wx.RIGHT, 8)
        btn_sizer.Add(close_btn, 0)
        main_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 20)

        self.SetSizer(main_sizer)
        self.CenterOnParent()

        self.analyze_btn.Bind(wx.EVT_BUTTON, self._on_analyze)
        self.upload_btn.Bind(wx.EVT_BUTTON, self._on_upload)
        self.toggle_action_btn.Bind(wx.EVT_BUTTON, self._on_toggle_action)
        self.review_btn.Bind(wx.EVT_BUTTON, self._on_review)

    def _show_progress(self, message: str, current: int, total: int) -> None:
        wx.CallAfter(self._show_progress_impl, message, current, total)

    def _show_progress_impl(self, message: str, current: int, total: int) -> None:
        self.progress_label.SetLabel(message)
        self.progress_label.Show()
        self.progress_gauge.Show()
        if total > 0:
            self.progress_gauge.SetValue(int(current / total * 100))
        self.Layout()

    def _hide_progress(self) -> None:
        self.progress_label.Hide()
        self.progress_gauge.Hide()
        self.Layout()

    def _on_analyze(self, event: wx.CommandEvent) -> None:
        url = self.url_input.GetValue().strip()
        if not url:
            wx.MessageBox(
                "Please enter a database URL.",
                "Error",
                wx.OK | wx.ICON_ERROR,
                self,
            )
            return

        self.analyze_btn.Disable()
        self.upload_btn.Disable()
        self._show_progress_impl("Connecting to source database...", 0, 0)

        thread = threading.Thread(target=self._run_analysis, args=(url,), daemon=True)
        thread.start()

    def _run_analysis(self, url: str) -> None:
        try:
            from database.connection import get_engine

            self.source_engine = get_engine()
            self.target_engine = create_source_engine(url)

            wx.CallAfter(self._show_progress_impl, "Analyzing differences...", 0, 0)
            analysis = analyze_differences(self.source_engine, self.target_engine)
            wx.CallAfter(self._show_analysis, analysis)
        except Exception as e:
            logger.exception("Analysis failed")
            wx.CallAfter(self._show_error, f"Analysis failed: {e}")
        finally:
            wx.CallAfter(self._hide_progress)
            wx.CallAfter(self.analyze_btn.Enable)

    def _show_error(self, message: str) -> None:
        wx.MessageBox(message, "Error", wx.OK | wx.ICON_ERROR, self)

    def _show_analysis(self, analysis: AnalysisResult) -> None:
        self.analysis = analysis
        self.use_source.clear()
        self.field_actions.clear()

        fields_total = sum(analysis.fields_to_fill.values())
        self.summary_labels["students"].SetLabel(str(analysis.students_to_add))
        self.summary_labels["fields"].SetLabel(str(fields_total))
        self.summary_labels["education"].SetLabel(str(analysis.education_to_add))
        self.summary_labels["kins"].SetLabel(str(analysis.kins_to_add))

        self.conflicts_by_field = defaultdict(list)
        for c in analysis.conflicts:
            self.conflicts_by_field[c.field_name].append(c)

        self.conflict_list.DeleteAllItems()
        total_conflicts = len(analysis.conflicts)
        if total_conflicts > 0:
            self.conflicts_desc.SetLabel(
                f"Found {total_conflicts} conflicts where both databases have different "
                "non-empty values. Default: Keep Live Data values. Toggle or review to change."
            )
            self.conflicts_desc.Wrap(600)
            for field_name, conflicts in sorted(
                self.conflicts_by_field.items(), key=lambda x: -len(x[1])
            ):
                idx = self.conflict_list.InsertItem(
                    self.conflict_list.GetItemCount(), field_name
                )
                self.conflict_list.SetItem(idx, 1, str(len(conflicts)))
                self.conflict_list.SetItem(idx, 2, "Keep Live Data")
                self.field_actions[field_name] = "keep"
        else:
            self.conflicts_desc.SetLabel(
                "No conflicts found. All changes are safe to apply."
            )

        self.results_panel.Show()
        self.upload_btn.Enable()
        self.Layout()

    def _on_toggle_action(self, event: wx.CommandEvent) -> None:
        selected = self.conflict_list.GetFirstSelected()
        if selected == -1:
            wx.MessageBox(
                "Select a field first.",
                "Info",
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            return

        field_name = self.conflict_list.GetItemText(selected, 0)
        current = self.field_actions.get(field_name, "keep")
        new_action = "source" if current == "keep" else "keep"
        self.field_actions[field_name] = new_action

        label = "Use Source" if new_action == "source" else "Keep Live Data"
        self.conflict_list.SetItem(selected, 2, label)

        for c in self.conflicts_by_field.get(field_name, []):
            key = (c.std_no, c.field_name)
            if new_action == "source":
                self.use_source.add(key)
            else:
                self.use_source.discard(key)

    def _on_review(self, event: wx.CommandEvent) -> None:
        selected = self.conflict_list.GetFirstSelected()
        if selected == -1:
            wx.MessageBox(
                "Select a field first.",
                "Info",
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            return

        field_name = self.conflict_list.GetItemText(selected, 0)
        conflicts = self.conflicts_by_field.get(field_name, [])
        if not conflicts:
            return

        dlg = ConflictDetailDialog(self, field_name, conflicts, self.use_source)
        if dlg.ShowModal() == wx.ID_OK:
            new_use_source = dlg.get_use_source()
            for c in conflicts:
                key = (c.std_no, c.field_name)
                self.use_source.discard(key)
            self.use_source.update(new_use_source)

            source_count = len(new_use_source)
            if source_count == 0:
                self.field_actions[field_name] = "keep"
                self.conflict_list.SetItem(selected, 2, "Keep Live Data")
            elif source_count == len(conflicts):
                self.field_actions[field_name] = "source"
                self.conflict_list.SetItem(selected, 2, "Use Source")
            else:
                self.field_actions[field_name] = "mixed"
                self.conflict_list.SetItem(
                    selected, 2, f"Mixed ({source_count} source)"
                )
        dlg.Destroy()

    def _build_resolutions(self) -> dict[tuple[int, str], str]:
        resolutions: dict[tuple[int, str], str] = {}
        if self.analysis is None:
            return resolutions
        for c in self.analysis.conflicts:
            if (c.std_no, c.field_name) in self.use_source:
                resolutions[(c.std_no, c.field_name)] = c.source_value
        return resolutions

    def _on_upload(self, event: wx.CommandEvent) -> None:
        if self.source_engine is None or self.target_engine is None:
            return

        confirm = wx.MessageBox(
            "This will upload data from the local database to the live "
            "database. Continue?",
            "Confirm Upload",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
            self,
        )
        if confirm != wx.YES:
            return

        self.upload_btn.Disable()
        self.analyze_btn.Disable()
        resolutions = self._build_resolutions()

        thread = threading.Thread(
            target=self._run_upload, args=(resolutions,), daemon=True
        )
        thread.start()

    def _run_upload(self, resolutions: dict[tuple[int, str], str]) -> None:
        try:
            assert self.source_engine is not None
            assert self.target_engine is not None
            stats = run_merge(
                self.source_engine,
                self.target_engine,
                self._show_progress,
                resolutions,
            )
            wx.CallAfter(self._show_upload_result, stats.summary())
        except Exception as e:
            logger.exception("Upload failed")
            wx.CallAfter(self._show_error, f"Upload failed: {e}")
        finally:
            wx.CallAfter(self._hide_progress)
            wx.CallAfter(self.analyze_btn.Enable)

    def _show_upload_result(self, summary: str) -> None:
        wx.MessageBox(summary, "Upload Complete", wx.OK | wx.ICON_INFORMATION, self)
