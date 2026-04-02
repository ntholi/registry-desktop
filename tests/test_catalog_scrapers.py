import unittest
from unittest.mock import patch

from bs4 import BeautifulSoup

from base.browser import BASE_URL
from features.sync.modules import scraper as modules_scraper
from features.sync.modules.scraper import _extract_modules_from_page
from features.sync.structures import scraper as structures_scraper


class _FakeResponse:
    def __init__(self, text: str):
        self.text = text


class _FakeBrowser:
    def __init__(self, pages: dict[str, str]):
        self._pages = pages

    def fetch(self, url: str):
        if url not in self._pages:
            raise AssertionError(f"Unexpected URL: {url}")
        return _FakeResponse(self._pages[url])


class CatalogScraperTests(unittest.TestCase):
    def test_extract_modules_keeps_blank_name_rows(self):
        page = BeautifulSoup(
            """
            <html>
              <body>
                <table id="ewlistmain">
                  <tr>
                    <td>Code</td>
                    <td>Name</td>
                    <td>Status</td>
                    <td>Total</td>
                    <td>Date Stamp</td>
                    <td></td>
                    <td></td>
                    <td></td>
                  </tr>
                  <tr>
                    <td>BCC2723123</td>
                    <td></td>
                    <td>Active</td>
                    <td>0</td>
                    <td>2018-07-31</td>
                    <td><a href="f_moduleview.php?ModuleID=3175">View</a></td>
                    <td><a href="f_moduleedit.php?ModuleID=3175">Edit</a></td>
                    <td><a href="f_programlist.php?showmaster=1&ModuleID=3175">Programs</a></td>
                  </tr>
                </table>
              </body>
            </html>
            """,
            "lxml",
        )

        modules = _extract_modules_from_page(page)

        self.assertEqual(len(modules), 1)
        self.assertEqual(modules[0]["cms_id"], 3175)
        self.assertEqual(modules[0]["code"], "BCC2723123")
        self.assertEqual(modules[0]["name"], "")
        self.assertEqual(modules[0]["status"], "Active")

    def test_scrape_semester_modules_resolves_code_only_rows_from_detail_page(self):
        semester_id = 1140
        sem_module_id = 5389
        list_url = (
            f"{BASE_URL}/f_semmodulelist.php?showmaster=1&SemesterID={semester_id}"
        )
        detail_url = f"{BASE_URL}/f_semmoduleview.php?SemModuleID={sem_module_id}"
        browser = _FakeBrowser(
            {
                list_url: """
                    <html>
                      <body>
                        <table id="ewlistmain">
                          <tr>
                            <td>Module</td>
                            <td>Type</td>
                            <td>Optn?</td>
                            <td>Credits</td>
                            <td>Prerequisite</td>
                            <td></td>
                            <td></td>
                          </tr>
                          <tr>
                            <td><span>380</span></td>
                            <td><span>Core</span></td>
                            <td><span></span></td>
                            <td><span><div align="center">3.0</div></span></td>
                            <td><span></span></td>
                            <td><a href="f_semmoduleview.php?SemModuleID=5389">View</a></td>
                            <td><a href="f_semmoduleedit.php?SemModuleID=5389">Edit</a></td>
                          </tr>
                          <tr>
                            <td></td>
                            <td></td>
                            <td></td>
                            <td>15.0</td>
                            <td></td>
                            <td></td>
                            <td></td>
                          </tr>
                        </table>
                      </body>
                    </html>
                """,
                detail_url: """
                    <html>
                      <body>
                        <table class="ewTable">
                          <tr>
                            <td>Module</td>
                            <td>BMGMT1201 Operational Management</td>
                          </tr>
                        </table>
                      </body>
                    </html>
                """,
            }
        )

        with patch.object(structures_scraper, "Browser", return_value=browser):
            semester_modules = structures_scraper.scrape_semester_modules(semester_id)

        self.assertEqual(
            semester_modules,
            [
                {
                    "cms_id": sem_module_id,
                    "module_code": "BMGMT1201",
                    "module_name": "Operational Management",
                    "type": "Core",
                    "credits": 3.0,
                    "hidden": False,
                }
            ],
        )

    def test_scrape_all_modules_follows_pager_bounds(self):
        base_url = f"{BASE_URL}/f_modulelist.php?cmd=resetall"
        browser = _FakeBrowser(
            {
                base_url: """
                    <html>
                      <body>
                        <form id="ewpagerform">Records 1 to 1 of 2</form>
                        <table id="ewlistmain">
                          <tr>
                            <td>Code</td>
                            <td>Name</td>
                            <td>Status</td>
                            <td>Total</td>
                            <td>Date Stamp</td>
                          </tr>
                          <tr>
                            <td>AAA101</td>
                            <td>Alpha</td>
                            <td>Active</td>
                            <td>0</td>
                            <td>2024-01-01</td>
                            <td><a href="f_moduleview.php?ModuleID=101">View</a></td>
                          </tr>
                        </table>
                      </body>
                    </html>
                """,
                f"{base_url}&start=2": """
                    <html>
                      <body>
                        <form id="ewpagerform">Records 2 to 2 of 2</form>
                        <table id="ewlistmain">
                          <tr>
                            <td>Code</td>
                            <td>Name</td>
                            <td>Status</td>
                            <td>Total</td>
                            <td>Date Stamp</td>
                          </tr>
                          <tr>
                            <td>BBB202</td>
                            <td>Beta</td>
                            <td>Defunct</td>
                            <td>0</td>
                            <td>2024-02-02</td>
                            <td><a href="f_moduleview.php?ModuleID=202">View</a></td>
                          </tr>
                        </table>
                      </body>
                    </html>
                """,
            }
        )

        with patch.object(modules_scraper, "Browser", return_value=browser):
            modules = modules_scraper.scrape_all_modules()

        self.assertEqual([module["cms_id"] for module in modules], [101, 202])
        self.assertEqual([module["code"] for module in modules], ["AAA101", "BBB202"])

    def test_normalize_program_level_handles_short_course(self):
        self.assertEqual(
            structures_scraper._normalize_program_level("Short Course"),
            "short_course",
        )


if __name__ == "__main__":
    unittest.main()
