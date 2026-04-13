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

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        desc = wx.StaticText(
            panel,
            label=f"Review {len(conflicts)} conflicts for '{field_name}'. "
            "Checked items will use the source value. Unchecked keep the live database value.",
        )
        desc.Wrap(700)
        sizer.Add(desc, 0, wx.ALL, 10)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        select_all_btn = wx.Button(panel, label="Select All (Use Source)")
        deselect_all_btn = wx.Button(panel, label="Deselect All (Keep Live)")
        btn_sizer.Add(select_all_btn, 0, wx.RIGHT, 5)
        btn_sizer.Add(deselect_all_btn, 0)
        sizer.Add(btn_sizer, 0, wx.LEFT | wx.BOTTOM, 10)

        self.list_ctrl = wx.ListCtrl(panel, style=wx.LC_REPORT)
        self.list_ctrl.EnableCheckBoxes(True)
        self.list_ctrl.AppendColumn("Student No", width=100)
        self.list_ctrl.AppendColumn("Name", width=200)
        self.list_ctrl.AppendColumn("Live Value", width=180)
        self.list_ctrl.AppendColumn("Source Value", width=180)

        for i, c in enumerate(conflicts):
            idx = self.list_ctrl.InsertItem(i, str(c.std_no))
            self.list_ctrl.SetItem(idx, 1, c.student_name)
            self.list_ctrl.SetItem(idx, 2, c.target_value)
            self.list_ctrl.SetItem(idx, 3, c.source_value)
            if (c.std_no, c.field_name) in self.use_source:
                self.list_ctrl.CheckItem(idx, True)

        sizer.Add(self.list_ctrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        dialog_btn_sizer = wx.StdDialogButtonSizer()
        ok_btn = wx.Button(panel, wx.ID_OK)
        cancel_btn = wx.Button(panel, wx.ID_CANCEL)
        dialog_btn_sizer.AddButton(ok_btn)
        dialog_btn_sizer.AddButton(cancel_btn)
        dialog_btn_sizer.Realize()
        sizer.Add(dialog_btn_sizer, 0, wx.EXPAND | wx.ALL, 10)

        panel.SetSizer(sizer)

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
            size=wx.Size(650, 550),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self.status_bar = status_bar
        self.analysis: AnalysisResult | None = None
        self.source_engine = None
        self.target_engine = None
        self.use_source: set[tuple[int, str]] = set()
        self.conflicts_by_field: dict[str, list[Conflict]] = {}
        self.field_actions: dict[str, str] = {}

        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        url_sizer = wx.BoxSizer(wx.HORIZONTAL)
        url_label = wx.StaticText(panel, label="Source Database URL:")
        url_sizer.Add(url_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        self.url_input = wx.TextCtrl(panel, size=wx.Size(350, -1))
        url_sizer.Add(self.url_input, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        self.analyze_btn = wx.Button(panel, label="Analyze")
        url_sizer.Add(self.analyze_btn, 0)
        main_sizer.Add(url_sizer, 0, wx.EXPAND | wx.ALL, 15)

        separator = wx.StaticLine(panel, style=wx.LI_HORIZONTAL)
        main_sizer.Add(separator, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)

        self.progress_label = wx.StaticText(panel, label="")
        main_sizer.Add(self.progress_label, 0, wx.LEFT | wx.TOP, 15)
        self.progress_gauge = wx.Gauge(panel, range=100, size=wx.Size(-1, 18))
        main_sizer.Add(
            self.progress_gauge, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 15
        )
        self.progress_label.Hide()
        self.progress_gauge.Hide()

        self.results_panel = wx.Panel(panel)
        results_sizer = wx.BoxSizer(wx.VERTICAL)

        summary_label = wx.StaticText(self.results_panel, label="Analysis Summary")
        summary_font = summary_label.GetFont()
        summary_font.PointSize = 11
        summary_font = summary_font.Bold()
        summary_label.SetFont(summary_font)
        results_sizer.Add(summary_label, 0, wx.TOP | wx.BOTTOM, 8)

        self.summary_text = wx.StaticText(self.results_panel, label="")
        results_sizer.Add(self.summary_text, 0, wx.BOTTOM, 10)

        conflicts_label = wx.StaticText(self.results_panel, label="Conflicts")
        conflicts_font = conflicts_label.GetFont()
        conflicts_font.PointSize = 11
        conflicts_font = conflicts_font.Bold()
        conflicts_label.SetFont(conflicts_font)
        results_sizer.Add(conflicts_label, 0, wx.BOTTOM, 8)

        self.conflicts_desc = wx.StaticText(self.results_panel, label="")
        self.conflicts_desc.Wrap(580)
        results_sizer.Add(self.conflicts_desc, 0, wx.BOTTOM, 8)

        self.conflict_list = wx.ListCtrl(
            self.results_panel, style=wx.LC_REPORT, size=wx.Size(-1, 150)
        )
        self.conflict_list.AppendColumn("Field", width=120)
        self.conflict_list.AppendColumn("Conflicts", width=80)
        self.conflict_list.AppendColumn("Action", width=150)
        results_sizer.Add(self.conflict_list, 1, wx.EXPAND | wx.BOTTOM, 8)

        conflict_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.toggle_action_btn = wx.Button(self.results_panel, label="Toggle Action")
        self.review_btn = wx.Button(self.results_panel, label="Review Details...")
        conflict_btn_sizer.Add(self.toggle_action_btn, 0, wx.RIGHT, 5)
        conflict_btn_sizer.Add(self.review_btn, 0)
        results_sizer.Add(conflict_btn_sizer, 0, wx.BOTTOM, 10)

        self.results_panel.SetSizer(results_sizer)
        main_sizer.Add(
            self.results_panel, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 15
        )
        self.results_panel.Hide()

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_sizer.AddStretchSpacer()
        self.upload_btn = wx.Button(panel, label="Upload")
        self.upload_btn.Disable()
        close_btn = wx.Button(panel, wx.ID_CANCEL, label="Close")
        btn_sizer.Add(self.upload_btn, 0, wx.RIGHT, 8)
        btn_sizer.Add(close_btn, 0)
        main_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 15)

        panel.SetSizer(main_sizer)

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

            self.source_engine = create_source_engine(url)
            self.target_engine = get_engine()

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
        lines = [
            f"Students to add: {analysis.students_to_add}",
            f"Student fields to fill: {fields_total}",
            f"Education records to add: {analysis.education_to_add}",
            f"Next of Kin records to add: {analysis.kins_to_add}",
        ]
        self.summary_text.SetLabel("\n".join(lines))

        self.conflicts_by_field = defaultdict(list)
        for c in analysis.conflicts:
            self.conflicts_by_field[c.field_name].append(c)

        self.conflict_list.DeleteAllItems()
        total_conflicts = len(analysis.conflicts)
        if total_conflicts > 0:
            self.conflicts_desc.SetLabel(
                f"Found {total_conflicts} fields where both databases have different "
                "non-empty values. Default: keep live database values. Toggle to use source "
                "values, or review individual conflicts."
            )
            self.conflicts_desc.Wrap(580)
            for field_name, conflicts in sorted(
                self.conflicts_by_field.items(), key=lambda x: -len(x[1])
            ):
                idx = self.conflict_list.InsertItem(
                    self.conflict_list.GetItemCount(), field_name
                )
                self.conflict_list.SetItem(idx, 1, str(len(conflicts)))
                self.conflict_list.SetItem(idx, 2, "Keep Live")
                self.field_actions[field_name] = "keep"
        else:
            self.conflicts_desc.SetLabel(
                "No conflicts found. All changes are safe to apply."
            )

        self.results_panel.Show()
        self.upload_btn.Enable()
        self.GetParent()
        panel = self.results_panel.GetParent()
        if panel:
            panel.Layout()

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

        label = "Use Source" if new_action == "source" else "Keep Live"
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
                self.conflict_list.SetItem(selected, 2, "Keep Live")
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
            "This will merge data from the source database into the registry "
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
