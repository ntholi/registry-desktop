import unittest
from unittest.mock import Mock, patch

import wx

from features.sync.students.view.importer.importer_dialog import ImporterDialog
from features.sync.students.view.importer.importer_project import ImporterProjectManager


class ImporterDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = wx.App()

    @classmethod
    def tearDownClass(cls):
        cls.app.Destroy()

    def setUp(self):
        self.parent = wx.Frame(None)
        self.sync_service = Mock()
        self.status_bar = Mock()
        with patch.object(ImporterProjectManager, "load_project", return_value=None):
            self.dialog = ImporterDialog(
                self.parent,
                self.sync_service,
                self.status_bar,
            )

    def tearDown(self):
        self.dialog.Destroy()
        self.parent.Destroy()

    def test_get_import_options_includes_addresses(self):
        options = self.dialog.get_import_options()

        self.assertIn("addresses", options)
        self.assertTrue(options["addresses"])

    def test_select_all_checkbox_updates_addresses_checkbox(self):
        self.dialog.select_all_checkbox.Set3StateValue(wx.CHK_UNCHECKED)

        self.dialog.on_select_all_checkbox(None)

        self.assertFalse(self.dialog.addresses_checkbox.GetValue())

    def test_start_import_requires_real_data_selection(self):
        self.dialog.start_student_input.SetValue("901000001")
        self.dialog.end_student_input.SetValue("901000500")
        self.dialog.student_info_checkbox.SetValue(False)
        self.dialog.personal_info_checkbox.SetValue(False)
        self.dialog.education_history_checkbox.SetValue(False)
        self.dialog.enrollment_data_checkbox.SetValue(False)
        self.dialog.addresses_checkbox.SetValue(False)
        self.dialog.skip_active_term_checkbox.SetValue(True)

        with (
            patch(
                "features.sync.students.view.importer.importer_dialog.wx.MessageBox"
            ) as message_box,
            patch.object(ImporterProjectManager, "create_project") as create_project,
        ):
            self.dialog.on_start_import(None)

        message_box.assert_called_once()
        create_project.assert_not_called()

    def test_on_close_uses_end_modal_for_modal_dialog(self):
        event = Mock()

        with (
            patch.object(self.dialog, "IsModal", return_value=True),
            patch.object(self.dialog, "EndModal") as end_modal,
        ):
            self.dialog.on_close(event)

        end_modal.assert_called_once_with(wx.ID_OK)
        event.CanVeto.assert_not_called()
