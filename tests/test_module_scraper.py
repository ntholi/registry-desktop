import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from bs4 import BeautifulSoup

from base.browser import BASE_URL
from features.sync.modules import scraper as modules_scraper
from features.sync.modules.scraper import (
    ModuleScrapeIntegrityError,
    _extract_modules_from_page,
)
from features.sync.modules.service import ModuleSyncService


class _FakeResponse:
    def __init__(self, text: str):
        self.text = text


class _SequencedBrowser:
    def __init__(self, pages: dict[str, list[str] | str]):
        self._pages: dict[str, list[str]] = {}
        for url, value in pages.items():
            if isinstance(value, list):
                self._pages[url] = list(value)
            else:
                self._pages[url] = [value]

    def fetch(self, url: str):
        if url not in self._pages:
            raise AssertionError(f"Unexpected URL: {url}")

        queue = self._pages[url]
        if len(queue) > 1:
            return _FakeResponse(queue.pop(0))

        return _FakeResponse(queue[0])


def _module_row(
    module_id: int, code: str, name: str, status: str, timestamp: str
) -> str:
    return f"""
        <tr>
          <td>{code}</td>
          <td>{name}</td>
          <td>{status}</td>
          <td>0</td>
          <td>{timestamp}</td>
          <td><a href="f_moduleview.php?ModuleID={module_id}">View</a></td>
        </tr>
    """


def _module_page(start: int, end: int, total: int, rows: list[str]) -> str:
    rows_html = "\n".join(rows)
    return f"""
        <html>
          <body>
            <form id="ewpagerform">Records {start} to {end} of {total}</form>
            <table id="ewlistmain">
              <tr>
                <td>Code</td>
                <td>Name</td>
                <td>Status</td>
                <td>Total</td>
                <td>Date Stamp</td>
              </tr>
              {rows_html}
            </table>
          </body>
        </html>
    """


class ModuleScraperTests(unittest.TestCase):
    def test_extract_modules_from_sample_page(self):
        sample_path = (
            Path(__file__).resolve().parents[1]
            / "samples/pages/modules/f_modulelist.php"
        )
        page = BeautifulSoup(sample_path.read_text(encoding="utf-8"), "lxml")

        modules = _extract_modules_from_page(page)

        self.assertEqual(len(modules), 3)
        self.assertEqual(modules[0]["cms_id"], 2636)
        self.assertEqual(modules[0]["code"], "AAAC112")
        self.assertEqual(modules[1]["cms_id"], 2990)
        self.assertEqual(modules[2]["cms_id"], 2922)

    def test_scrape_all_modules_raises_when_page_is_shorter_than_pager(self):
        base_url = f"{BASE_URL}/f_modulelist.php?cmd=resetall"
        browser = _SequencedBrowser(
            {
                base_url: _module_page(
                    1,
                    20,
                    21,
                    [_module_row(101, "AAA101", "Alpha", "Active", "2024-01-01")],
                )
            }
        )

        with patch.object(modules_scraper, "Browser", return_value=browser):
            with self.assertRaises(ModuleScrapeIntegrityError):
                modules_scraper.scrape_all_modules(verify=False, max_attempts=1)

    def test_scrape_all_modules_retries_when_first_attempt_is_incomplete(self):
        base_url = f"{BASE_URL}/f_modulelist.php?cmd=resetall"
        first_page = _module_page(
            1,
            20,
            21,
            [
                _module_row(
                    module_id,
                    f"MOD{module_id:04d}",
                    f"Module {module_id}",
                    "Active",
                    "2024-01-01",
                )
                for module_id in range(1, 21)
            ],
        )
        bad_second_page = _module_page(
            21,
            21,
            21,
            [_module_row(20, "MOD0020", "Module 20", "Active", "2024-01-01")],
        )
        good_second_page = _module_page(
            21,
            21,
            21,
            [_module_row(21, "MOD0021", "Module 21", "Active", "2024-01-01")],
        )
        browser = _SequencedBrowser(
            {
                base_url: [first_page, first_page, first_page],
                f"{base_url}&start=21": [
                    bad_second_page,
                    good_second_page,
                    good_second_page,
                ],
            }
        )

        with patch.object(modules_scraper, "Browser", return_value=browser):
            modules = modules_scraper.scrape_all_modules(max_attempts=2)

        self.assertEqual(len(modules), 21)
        self.assertEqual(modules[-1]["cms_id"], 21)

    def test_scrape_all_modules_raises_when_total_changes_mid_scrape(self):
        base_url = f"{BASE_URL}/f_modulelist.php?cmd=resetall"
        browser = _SequencedBrowser(
            {
                base_url: _module_page(
                    1,
                    20,
                    40,
                    [
                        _module_row(
                            module_id,
                            f"MOD{module_id:04d}",
                            f"Module {module_id}",
                            "Active",
                            "2024-01-01",
                        )
                        for module_id in range(1, 21)
                    ],
                ),
                f"{base_url}&start=21": _module_page(
                    21,
                    40,
                    41,
                    [
                        _module_row(
                            module_id,
                            f"MOD{module_id:04d}",
                            f"Module {module_id}",
                            "Active",
                            "2024-01-01",
                        )
                        for module_id in range(21, 41)
                    ],
                ),
            }
        )

        with patch.object(modules_scraper, "Browser", return_value=browser):
            with self.assertRaises(ModuleScrapeIntegrityError):
                modules_scraper.scrape_all_modules(verify=False, max_attempts=1)

    def test_scrape_all_modules_raises_when_verification_snapshot_changes(self):
        base_url = f"{BASE_URL}/f_modulelist.php?cmd=resetall"
        first_snapshot = _module_page(
            1,
            2,
            2,
            [
                _module_row(101, "AAA101", "Alpha", "Active", "2024-01-01"),
                _module_row(202, "BBB202", "Beta", "Active", "2024-01-02"),
            ],
        )
        second_snapshot = _module_page(
            1,
            2,
            2,
            [
                _module_row(101, "AAA101", "Alpha", "Active", "2024-01-01"),
                _module_row(303, "CCC303", "Gamma", "Active", "2024-01-03"),
            ],
        )
        browser = _SequencedBrowser({base_url: [first_snapshot, second_snapshot]})

        with patch.object(modules_scraper, "Browser", return_value=browser):
            with self.assertRaises(ModuleScrapeIntegrityError):
                modules_scraper.scrape_all_modules(max_attempts=1)


class ModuleSyncServiceTests(unittest.TestCase):
    def test_fetch_and_save_all_modules_raises_when_save_fails(self):
        repository = Mock()
        repository.save_module.side_effect = [None, RuntimeError("db failure")]
        repository.find_missing_cms_ids.return_value = []
        service = ModuleSyncService(repository)

        modules = [
            {
                "cms_id": 101,
                "code": "AAA101",
                "name": "Alpha",
                "status": "Active",
                "timestamp": "2024-01-01",
            },
            {
                "cms_id": 202,
                "code": "BBB202",
                "name": "Beta",
                "status": "Active",
                "timestamp": "2024-01-02",
            },
        ]

        with patch(
            "features.sync.modules.service.scrape_all_modules", return_value=modules
        ):
            with self.assertRaises(RuntimeError):
                service.fetch_and_save_all_modules(lambda *_: None)

    def test_fetch_and_save_all_modules_raises_when_saved_rows_cannot_be_verified(self):
        repository = Mock()
        repository.find_missing_cms_ids.return_value = [202]
        service = ModuleSyncService(repository)

        modules = [
            {
                "cms_id": 101,
                "code": "AAA101",
                "name": "Alpha",
                "status": "Active",
                "timestamp": "2024-01-01",
            },
            {
                "cms_id": 202,
                "code": "BBB202",
                "name": "Beta",
                "status": "Active",
                "timestamp": "2024-01-02",
            },
        ]

        with patch(
            "features.sync.modules.service.scrape_all_modules", return_value=modules
        ):
            with self.assertRaises(RuntimeError):
                service.fetch_and_save_all_modules(lambda *_: None)

    def test_fetch_and_save_all_modules_returns_count_after_verification(self):
        repository = Mock()
        repository.find_missing_cms_ids.return_value = []
        service = ModuleSyncService(repository)
        progress = Mock()

        modules = [
            {
                "cms_id": 101,
                "code": "AAA101",
                "name": "Alpha",
                "status": "Active",
                "timestamp": "2024-01-01",
            },
            {
                "cms_id": 202,
                "code": "BBB202",
                "name": "Beta",
                "status": "Defunct",
                "timestamp": "2024-01-02",
            },
        ]

        with patch(
            "features.sync.modules.service.scrape_all_modules", return_value=modules
        ):
            saved_count = service.fetch_and_save_all_modules(progress)

        self.assertEqual(saved_count, 2)
        self.assertEqual(repository.save_module.call_count, 2)
        repository.find_missing_cms_ids.assert_called_once_with([101, 202])
        self.assertEqual(
            progress.call_args_list[-1].args,
            ("Successfully saved and verified 2/2 modules", 2, 2),
        )


if __name__ == "__main__":
    unittest.main()
