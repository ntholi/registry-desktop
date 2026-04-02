import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from bs4 import BeautifulSoup

from base.browser import BASE_URL
from features.sync.structures import scraper as structures_scraper
from features.sync.structures.scraper import StructureScrapeIntegrityError


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


def _sample_path(*parts: str) -> Path:
    return Path(__file__).resolve().parents[1].joinpath("samples", "pages", *parts)


def _table_page(start: int, end: int, total: int, rows: list[str]) -> str:
    rows_html = "\n".join(rows)
    return f"""
        <html>
          <body>
            <form id="ewpagerform">Records {start} to {end} of {total}</form>
            <table id="ewlistmain">
              <tr>
                <td>Col 1</td>
                <td>Col 2</td>
                <td>Col 3</td>
                <td>Col 4</td>
                <td>Col 5</td>
                <td></td>
                <td></td>
                <td></td>
              </tr>
              {rows_html}
            </table>
          </body>
        </html>
    """


def _school_row(school_id: int, code: str, name: str) -> str:
    return f"""
        <tr>
          <td>{code}</td>
          <td>{name}</td>
          <td><a href="f_schoolview.php?SchoolID={school_id}">View</a></td>
        </tr>
    """


def _program_row(program_id: int, code: str, name: str, status: str = "Active") -> str:
    return f"""
        <tr>
          <td>{code}</td>
          <td>{name}</td>
          <td>{status}</td>
          <td><a href="f_programview.php?ProgramID={program_id}">View</a></td>
        </tr>
    """


def _structure_row(structure_id: int, code: str, desc: str) -> str:
    return f"""
        <tr>
          <td>{code}</td>
          <td>{desc}</td>
          <td>Y</td>
          <td>0</td>
          <td>N</td>
          <td><a href="f_structureview.php?StructureID={structure_id}">View</a></td>
        </tr>
    """


def _semester_row(semester_id: int, code: str, credits: str) -> str:
    return f"""
        <tr>
          <td>{code}</td>
          <td>{credits}</td>
          <td></td>
          <td></td>
          <td><a href="f_semesterview.php?SemesterID={semester_id}">View</a></td>
        </tr>
    """


def _semester_module_row(
    sem_module_id: int,
    module_text: str,
    module_type: str,
    credits: str,
) -> str:
    return f"""
        <tr>
          <td>{module_text}</td>
          <td>{module_type}</td>
          <td></td>
          <td>{credits}</td>
          <td></td>
          <td><a href="f_semmoduleview.php?SemModuleID={sem_module_id}">View</a></td>
        </tr>
    """


def _program_view_page(category: str) -> str:
    return f"""
        <html>
          <body>
            <table class="ewTable">
              <tr>
                <td>Category</td>
                <td>{category}</td>
              </tr>
            </table>
          </body>
        </html>
    """


def _semester_module_view_page(module_text: str) -> str:
    return f"""
        <html>
          <body>
            <table class="ewTable">
              <tr>
                <td>Module</td>
                <td>{module_text}</td>
              </tr>
            </table>
          </body>
        </html>
    """


class StructureScraperTests(unittest.TestCase):
    def test_extract_schools_from_sample_page(self):
        page = BeautifulSoup(
            _sample_path("schools", "f_schoollist.php").read_text(encoding="utf-8"),
            "lxml",
        )

        schools = structures_scraper._extract_schools_from_page(page)

        self.assertGreaterEqual(len(schools), 10)
        self.assertIn(
            {
                "cms_id": 4,
                "code": "FDI",
                "name": "Faculty of Design and Innovation",
            },
            schools,
        )

    def test_extract_structures_from_sample_page(self):
        page = BeautifulSoup(
            _sample_path("schools", "f_structurelist.php").read_text(encoding="utf-8"),
            "lxml",
        )

        structures = structures_scraper._extract_structures_from_page(page)

        self.assertGreaterEqual(len(structures), 3)
        self.assertEqual(structures[0]["cms_id"], 3)
        self.assertEqual(structures[0]["code"], "0802-AT")
        self.assertEqual(structures[1]["cms_id"], 182)

    def test_extract_semesters_from_sample_page(self):
        page = BeautifulSoup(
            _sample_path(
                "schools",
                "programs",
                "semesters",
                "f_semesterlist.php",
            ).read_text(encoding="utf-8"),
            "lxml",
        )

        semesters = structures_scraper._extract_semesters_from_page(page)

        self.assertGreaterEqual(len(semesters), 5)
        self.assertEqual(
            semesters[0],
            {
                "cms_id": 13,
                "semester_number": "01",
                "name": "Year 1 Sem 1",
                "total_credits": 18.0,
            },
        )

    def test_extract_semester_modules_from_sample_page(self):
        page = BeautifulSoup(
            _sample_path("schools", "f_semmodulelist.php").read_text(encoding="utf-8"),
            "lxml",
        )
        browser = Mock()

        semester_modules = structures_scraper._extract_semester_modules_from_page(
            page,
            browser,
            {},
        )

        self.assertGreaterEqual(len(semester_modules), 6)
        self.assertEqual(
            semester_modules[0],
            {
                "cms_id": 2,
                "module_code": "CRET101",
                "module_name": "Creative and Innovation Studies",
                "type": "Core",
                "credits": 3.0,
                "hidden": False,
            },
        )
        browser.fetch.assert_not_called()

    def test_scrape_programs_reads_levels_from_detail_pages(self):
        school_id = 33
        base_url = f"{BASE_URL}/f_programlist.php?showmaster=1&SchoolID={school_id}"
        browser = _SequencedBrowser(
            {
                base_url: _table_page(
                    1,
                    2,
                    2,
                    [
                        _program_row(301, "DIP1", "Diploma Program"),
                        _program_row(302, "DEG1", "Degree Program"),
                    ],
                ),
                f"{BASE_URL}/f_programview.php?ProgramID=301": _program_view_page(
                    "Diploma"
                ),
                f"{BASE_URL}/f_programview.php?ProgramID=302": _program_view_page(
                    "Bachelor Degree"
                ),
            }
        )

        with patch.object(structures_scraper, "Browser", return_value=browser):
            programs = structures_scraper.scrape_programs(
                school_id,
                verify=False,
                max_attempts=1,
            )

        self.assertEqual(
            programs,
            [
                {
                    "cms_id": 301,
                    "code": "DIP1",
                    "name": "Diploma Program",
                    "level": "diploma",
                },
                {
                    "cms_id": 302,
                    "code": "DEG1",
                    "name": "Degree Program",
                    "level": "degree",
                },
            ],
        )

    def test_scrape_programs_follows_pager_bounds_and_verifies_snapshot(self):
        school_id = 34
        base_url = f"{BASE_URL}/f_programlist.php?showmaster=1&SchoolID={school_id}"
        page_one = _table_page(
            1,
            2,
            3,
            [
                _program_row(311, "DIP1", "Diploma Program"),
                _program_row(312, "DEG1", "Degree Program"),
            ],
        )
        page_two = _table_page(
            3,
            3,
            3,
            [_program_row(313, "SC1", "Short Course Program")],
        )
        browser = _SequencedBrowser(
            {
                base_url: [page_one, page_one],
                f"{base_url}&start=3": [page_two, page_two],
                f"{BASE_URL}/f_programview.php?ProgramID=311": _program_view_page(
                    "Diploma"
                ),
                f"{BASE_URL}/f_programview.php?ProgramID=312": _program_view_page(
                    "Degree"
                ),
                f"{BASE_URL}/f_programview.php?ProgramID=313": _program_view_page(
                    "Short Course"
                ),
            }
        )

        with patch.object(structures_scraper, "Browser", return_value=browser):
            programs = structures_scraper.scrape_programs(school_id)

        self.assertEqual([program["cms_id"] for program in programs], [311, 312, 313])
        self.assertEqual(
            [program["level"] for program in programs],
            ["diploma", "degree", "short_course"],
        )

    def test_scrape_structures_follows_pager_bounds_and_verifies_snapshot(self):
        program_id = 57
        base_url = f"{BASE_URL}/f_structurelist.php?showmaster=1&ProgramID={program_id}"
        browser = _SequencedBrowser(
            {
                base_url: [
                    _table_page(
                        1,
                        2,
                        3,
                        [
                            _structure_row(571, "2026-A", "2026-A"),
                            _structure_row(572, "2026-B", "2026-B"),
                        ],
                    ),
                    _table_page(
                        1,
                        2,
                        3,
                        [
                            _structure_row(571, "2026-A", "2026-A"),
                            _structure_row(572, "2026-B", "2026-B"),
                        ],
                    ),
                ],
                f"{base_url}&start=3": [
                    _table_page(
                        3,
                        3,
                        3,
                        [_structure_row(573, "2026-C", "2026-C")],
                    ),
                    _table_page(
                        3,
                        3,
                        3,
                        [_structure_row(573, "2026-C", "2026-C")],
                    ),
                ],
            }
        )

        with patch.object(structures_scraper, "Browser", return_value=browser):
            structures = structures_scraper.scrape_structures(program_id)

        self.assertEqual(
            structures,
            [
                {"cms_id": 571, "code": "2026-A", "desc": "2026-A"},
                {"cms_id": 572, "code": "2026-B", "desc": "2026-B"},
                {"cms_id": 573, "code": "2026-C", "desc": "2026-C"},
            ],
        )

    def test_scrape_semesters_follows_pager_bounds_and_verifies_snapshot(self):
        structure_id = 67
        base_url = (
            f"{BASE_URL}/f_semesterlist.php?showmaster=1&StructureID={structure_id}"
        )
        browser = _SequencedBrowser(
            {
                base_url: [
                    _table_page(
                        1,
                        2,
                        3,
                        [
                            _semester_row(671, "01 Year 1 Sem 1", "18.0"),
                            _semester_row(672, "02 Year 1 Sem 2", "16.0"),
                        ],
                    ),
                    _table_page(
                        1,
                        2,
                        3,
                        [
                            _semester_row(671, "01 Year 1 Sem 1", "18.0"),
                            _semester_row(672, "02 Year 1 Sem 2", "16.0"),
                        ],
                    ),
                ],
                f"{base_url}&start=3": [
                    _table_page(
                        3,
                        3,
                        3,
                        [_semester_row(673, "03 Year 2 Sem 1", "12.0")],
                    ),
                    _table_page(
                        3,
                        3,
                        3,
                        [_semester_row(673, "03 Year 2 Sem 1", "12.0")],
                    ),
                ],
            }
        )

        with patch.object(structures_scraper, "Browser", return_value=browser):
            semesters = structures_scraper.scrape_semesters(structure_id)

        self.assertEqual(
            semesters,
            [
                {
                    "cms_id": 671,
                    "semester_number": "01",
                    "name": "Year 1 Sem 1",
                    "total_credits": 18.0,
                },
                {
                    "cms_id": 672,
                    "semester_number": "02",
                    "name": "Year 1 Sem 2",
                    "total_credits": 16.0,
                },
                {
                    "cms_id": 673,
                    "semester_number": "03",
                    "name": "Year 2 Sem 1",
                    "total_credits": 12.0,
                },
            ],
        )

    def test_school_lookup_helpers_match_case_insensitive_codes(self):
        schools = [{"cms_id": 101, "code": "SCI", "name": "School of Science"}]

        with patch.object(
            structures_scraper, "scrape_all_schools", return_value=schools
        ):
            school = structures_scraper.scrape_school_details("sci")
            school_id = structures_scraper.scrape_school_id("ScI")

        self.assertEqual(school, schools[0])
        self.assertEqual(school_id, 101)

    def test_scrape_all_schools_retries_when_first_attempt_is_incomplete(self):
        base_url = f"{BASE_URL}/f_schoollist.php?cmd=resetall"
        page_one = _table_page(
            1,
            2,
            3,
            [
                _school_row(101, "SCI", "School of Science"),
                _school_row(102, "BUS", "School of Business"),
            ],
        )
        bad_page_two = _table_page(
            3,
            3,
            3,
            [_school_row(102, "BUS", "School of Business")],
        )
        good_page_two = _table_page(
            3,
            3,
            3,
            [_school_row(103, "ART", "School of Arts")],
        )
        browser = _SequencedBrowser(
            {
                base_url: [page_one, page_one],
                f"{base_url}&start=3": [bad_page_two, good_page_two],
            }
        )

        with patch.object(structures_scraper, "Browser", return_value=browser):
            schools = structures_scraper.scrape_all_schools(
                verify=False,
                max_attempts=2,
            )

        self.assertEqual([school["cms_id"] for school in schools], [101, 102, 103])

    def test_scrape_all_schools_raises_when_verification_snapshot_changes(self):
        base_url = f"{BASE_URL}/f_schoollist.php?cmd=resetall"
        first_snapshot = _table_page(
            1,
            2,
            2,
            [
                _school_row(101, "SCI", "School of Science"),
                _school_row(102, "BUS", "School of Business"),
            ],
        )
        second_snapshot = _table_page(
            1,
            2,
            2,
            [
                _school_row(101, "SCI", "School of Science"),
                _school_row(103, "ART", "School of Arts"),
            ],
        )
        browser = _SequencedBrowser({base_url: [first_snapshot, second_snapshot]})

        with patch.object(structures_scraper, "Browser", return_value=browser):
            with self.assertRaises(StructureScrapeIntegrityError):
                structures_scraper.scrape_all_schools(max_attempts=1)

    def test_scrape_programs_raises_when_page_is_shorter_than_pager(self):
        school_id = 44
        base_url = f"{BASE_URL}/f_programlist.php?showmaster=1&SchoolID={school_id}"
        browser = _SequencedBrowser(
            {
                base_url: _table_page(
                    1,
                    2,
                    2,
                    [_program_row(401, "PRG1", "Program One")],
                ),
                f"{BASE_URL}/f_programview.php?ProgramID=401": _program_view_page(
                    "Degree"
                ),
            }
        )

        with patch.object(structures_scraper, "Browser", return_value=browser):
            with self.assertRaises(StructureScrapeIntegrityError):
                structures_scraper.scrape_programs(
                    school_id,
                    verify=False,
                    max_attempts=1,
                )

    def test_scrape_structures_raises_when_total_changes_mid_scrape(self):
        program_id = 55
        base_url = f"{BASE_URL}/f_structurelist.php?showmaster=1&ProgramID={program_id}"
        browser = _SequencedBrowser(
            {
                base_url: _table_page(
                    1,
                    1,
                    2,
                    [_structure_row(501, "STR-1", "Structure One")],
                ),
                f"{base_url}&start=2": _table_page(
                    2,
                    2,
                    3,
                    [_structure_row(502, "STR-2", "Structure Two")],
                ),
            }
        )

        with patch.object(structures_scraper, "Browser", return_value=browser):
            with self.assertRaises(StructureScrapeIntegrityError):
                structures_scraper.scrape_structures(
                    program_id,
                    verify=False,
                    max_attempts=1,
                )

    def test_scrape_semesters_raises_when_page_is_shorter_than_pager(self):
        structure_id = 66
        base_url = (
            f"{BASE_URL}/f_semesterlist.php?showmaster=1&StructureID={structure_id}"
        )
        browser = _SequencedBrowser(
            {
                base_url: _table_page(
                    1,
                    2,
                    2,
                    [_semester_row(601, "01 Year 1 Sem 1", "18.0")],
                )
            }
        )

        with patch.object(structures_scraper, "Browser", return_value=browser):
            with self.assertRaises(StructureScrapeIntegrityError):
                structures_scraper.scrape_semesters(
                    structure_id,
                    verify=False,
                    max_attempts=1,
                )

    def test_scrape_semesters_raises_when_verification_snapshot_changes(self):
        structure_id = 77
        base_url = (
            f"{BASE_URL}/f_semesterlist.php?showmaster=1&StructureID={structure_id}"
        )
        first_snapshot = _table_page(
            1,
            1,
            1,
            [_semester_row(701, "01 Year 1 Sem 1", "18.0")],
        )
        second_snapshot = _table_page(
            1,
            1,
            1,
            [_semester_row(702, "01 Year 1 Sem 1", "18.0")],
        )
        browser = _SequencedBrowser({base_url: [first_snapshot, second_snapshot]})

        with patch.object(structures_scraper, "Browser", return_value=browser):
            with self.assertRaises(StructureScrapeIntegrityError):
                structures_scraper.scrape_semesters(structure_id, max_attempts=1)

    def test_scrape_semester_modules_follows_pager_bounds_and_resolves_detail_rows(
        self,
    ):
        semester_id = 88
        base_url = (
            f"{BASE_URL}/f_semmodulelist.php?showmaster=1&SemesterID={semester_id}"
        )
        browser = _SequencedBrowser(
            {
                base_url: [
                    _table_page(
                        1,
                        1,
                        2,
                        [_semester_module_row(801, "380", "Core", "3.0")],
                    ),
                    _table_page(
                        1,
                        1,
                        2,
                        [_semester_module_row(801, "380", "Core", "3.0")],
                    ),
                ],
                f"{base_url}&start=2": [
                    _table_page(
                        2,
                        2,
                        2,
                        [
                            _semester_module_row(
                                802,
                                "ACC101 Accounting",
                                "Elective",
                                "4.0",
                            )
                        ],
                    ),
                    _table_page(
                        2,
                        2,
                        2,
                        [
                            _semester_module_row(
                                802,
                                "ACC101 Accounting",
                                "Elective",
                                "4.0",
                            )
                        ],
                    ),
                ],
                f"{BASE_URL}/f_semmoduleview.php?SemModuleID=801": _semester_module_view_page(
                    "BMGMT1201 Operational Management"
                ),
            }
        )

        with patch.object(structures_scraper, "Browser", return_value=browser):
            semester_modules = structures_scraper.scrape_semester_modules(semester_id)

        self.assertEqual(
            semester_modules,
            [
                {
                    "cms_id": 801,
                    "module_code": "BMGMT1201",
                    "module_name": "Operational Management",
                    "type": "Core",
                    "credits": 3.0,
                    "hidden": False,
                },
                {
                    "cms_id": 802,
                    "module_code": "ACC101",
                    "module_name": "Accounting",
                    "type": "Elective",
                    "credits": 4.0,
                    "hidden": False,
                },
            ],
        )

    def test_scrape_semester_modules_raises_when_total_changes_mid_scrape(self):
        semester_id = 99
        base_url = (
            f"{BASE_URL}/f_semmodulelist.php?showmaster=1&SemesterID={semester_id}"
        )
        browser = _SequencedBrowser(
            {
                base_url: _table_page(
                    1,
                    1,
                    2,
                    [_semester_module_row(901, "MOD101 One", "Core", "3.0")],
                ),
                f"{base_url}&start=2": _table_page(
                    2,
                    2,
                    3,
                    [_semester_module_row(902, "MOD102 Two", "Core", "3.0")],
                ),
            }
        )

        with patch.object(structures_scraper, "Browser", return_value=browser):
            with self.assertRaises(StructureScrapeIntegrityError):
                structures_scraper.scrape_semester_modules(
                    semester_id,
                    verify=False,
                    max_attempts=1,
                )


if __name__ == "__main__":
    unittest.main()
