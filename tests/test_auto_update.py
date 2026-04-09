import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import requests

from base.auto_update import AutoUpdater


class FakeResponse:
    def __init__(self, payload=None, headers=None, chunks=None, error=None):
        self._payload = payload or {}
        self.headers = headers or {}
        self._chunks = chunks or []
        self._error = error

    def raise_for_status(self):
        if self._error is not None:
            raise self._error

    def json(self):
        return self._payload

    def iter_content(self, chunk_size=8192):
        del chunk_size
        for chunk in self._chunks:
            yield chunk


class AutoUpdaterTests(unittest.TestCase):
    def test_check_for_updates_returns_true_for_newer_windows_release(self):
        response = FakeResponse(
            payload={
                "tag_name": "v0.5.0",
                "body": "Important fixes",
                "assets": [
                    {
                        "name": "registry-desktop.exe",
                        "browser_download_url": "https://example.com/registry-desktop.exe",
                    }
                ],
            }
        )

        with (
            patch("base.auto_update.requests.get", return_value=response),
            patch("base.auto_update.platform.system", return_value="Windows"),
        ):
            updater = AutoUpdater()
            updater.current_version = "0.3.0"
            has_update = updater.check_for_updates()

        self.assertTrue(has_update)
        self.assertEqual(updater.get_latest_version(), "0.5.0")
        self.assertEqual(
            updater.download_url,
            "https://example.com/registry-desktop.exe",
        )
        self.assertEqual(updater.get_release_notes(), "Important fixes")
        self.assertIsNone(updater.get_last_error())

    def test_check_for_updates_sets_error_on_request_failure(self):
        with patch(
            "base.auto_update.requests.get",
            side_effect=requests.RequestException("network down"),
        ):
            updater = AutoUpdater()
            has_update = updater.check_for_updates()

        self.assertFalse(has_update)
        self.assertEqual(
            updater.get_last_error(),
            "Failed to check for updates: network down",
        )

    def test_check_for_updates_sets_error_when_asset_is_missing(self):
        response = FakeResponse(
            payload={
                "tag_name": "v0.5.0",
                "assets": [
                    {
                        "name": "registry-desktop.zip",
                        "browser_download_url": "https://example.com/registry-desktop.zip",
                    }
                ],
            }
        )

        with (
            patch("base.auto_update.requests.get", return_value=response),
            patch("base.auto_update.platform.system", return_value="Windows"),
        ):
            updater = AutoUpdater()
            has_update = updater.check_for_updates()

        self.assertFalse(has_update)
        self.assertEqual(
            updater.get_last_error(),
            "No suitable download found for Windows",
        )

    def test_download_and_install_update_prepares_windows_self_replace(self):
        response = FakeResponse(
            headers={"content-length": "6"},
            chunks=[b"abc", b"def"],
        )
        progress_events: list[tuple[int, int, int]] = []

        with TemporaryDirectory() as temp_dir:
            current_exe = Path(temp_dir) / "registry-desktop.exe"
            current_exe.write_bytes(b"old")

            with (
                patch("base.auto_update.requests.get", return_value=response),
                patch("base.auto_update.platform.system", return_value="Windows"),
                patch("base.auto_update.subprocess.Popen") as popen,
                patch("base.auto_update.os._exit") as exit_app,
                patch("base.auto_update.sys.executable", str(current_exe)),
                patch.object(__import__("sys"), "frozen", True, create=True),
            ):
                updater = AutoUpdater()
                updater.download_url = "https://example.com/registry-desktop.exe"
                success = updater.download_and_install_update(
                    lambda progress, downloaded, total: progress_events.append(
                        (progress, downloaded, total)
                    )
                )

        self.assertTrue(success)
        self.assertIsNone(updater.get_last_error())
        exit_app.assert_called_once_with(0)
        popen.assert_called_once()
        command = popen.call_args.args[0]
        self.assertEqual(command[0], "cmd.exe")
        self.assertEqual(command[1], "/c")

        script_path = Path(command[2])
        script_text = script_path.read_text(encoding="utf-8")

        self.assertIn(str(current_exe), script_text)
        self.assertIn('move /Y "%SOURCE%" "%TARGET%" >NUL', script_text)
        self.assertIn('start "" "%TARGET%"', script_text)
        self.assertEqual(progress_events[-1], (100, 6, 6))

        source_line = next(
            line for line in script_text.splitlines() if line.startswith('set "SOURCE=')
        )
        source_path = Path(source_line.removeprefix('set "SOURCE=').removesuffix('"'))
        script_path.unlink(missing_ok=True)
        source_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
