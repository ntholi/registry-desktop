import unittest
from unittest.mock import Mock, patch

from features.sync.students.scraper import (
    parse_semester_name,
    scrape_student_semester_data,
)


SEMESTER_VIEW_HTML = """
<table class="ewTable">
  <tr>
    <td class="ewTableHeader"><span>Term</span></td>
    <td class="ewTableAltRow"><span>2011-02</span></td>
  </tr>
  <tr>
    <td class="ewTableHeader"><span>Semester</span></td>
    <td class="ewTableAltRow"><span>07 Year 4 Sem 1</span></td>
  </tr>
  <tr>
    <td class="ewTableHeader"><span>SemStatus</span></td>
    <td class="ewTableAltRow"><span>Active</span></td>
  </tr>
</table>
"""


class StudentSemesterScraperTests(unittest.TestCase):
    def test_parse_semester_name_strips_number_prefix(self):
        self.assertEqual(
            parse_semester_name("07 Year 4 Sem 1", "07"),
            "Year 4 Sem 1",
        )

    def test_scrape_student_semester_data_creates_placeholder_when_lookup_fails(self):
        repository = Mock()
        repository.lookup_structure_semester_id.side_effect = [None, None]
        repository.refresh_structure_semesters.return_value = 0
        repository.ensure_structure_semester.return_value = 321

        with patch("features.sync.students.scraper.Browser") as browser_cls:
            browser_cls.return_value.fetch.return_value = Mock(text=SEMESTER_VIEW_HTML)

            data = scrape_student_semester_data(
                "14478",
                structure_id=29,
                repository=repository,
            )

        self.assertEqual(data["term"], "2011-02")
        self.assertEqual(data["structure_semester_id"], 321)
        repository.refresh_structure_semesters.assert_called_once_with(29)
        repository.ensure_structure_semester.assert_called_once_with(
            29,
            "07",
            "Year 4 Sem 1",
        )


if __name__ == "__main__":
    unittest.main()
