import unittest

from tools.student_audit import (
    CandidateProfile,
    build_page_starts,
    canonical_contact_rows,
    canonical_education_rows,
    canonical_program_rows,
    canonical_semester_rows,
    diff_summary,
    select_audit_students,
)


class StudentAuditHelpersTests(unittest.TestCase):
    def test_build_page_starts_spreads_evenly_across_pages(self):
        starts = build_page_starts(total_records=14529, page_size=10, sample_pages=5)

        self.assertEqual(starts[0], 1)
        self.assertEqual(starts[-1], 14521)
        self.assertEqual(len(starts), 5)
        self.assertEqual(sorted(starts), starts)

    def test_select_audit_students_prefers_rich_records_and_keeps_unique(self):
        candidates = [
            CandidateProfile(
                "902000001",
                programs=1,
                educations=0,
                addresses=0,
                semesters=0,
                modules=0,
            ),
            CandidateProfile(
                "902000002",
                programs=1,
                educations=0,
                addresses=0,
                semesters=1,
                modules=4,
            ),
            CandidateProfile(
                "902000003",
                programs=1,
                educations=1,
                addresses=1,
                semesters=3,
                modules=12,
            ),
            CandidateProfile(
                "902000004",
                programs=2,
                educations=0,
                addresses=2,
                semesters=2,
                modules=5,
            ),
            CandidateProfile(
                "902000005",
                programs=1,
                educations=0,
                addresses=0,
                semesters=0,
                modules=1,
            ),
            CandidateProfile(
                "902000006",
                programs=1,
                educations=2,
                addresses=1,
                semesters=4,
                modules=15,
            ),
        ]

        selected = select_audit_students(candidates, limit=4)
        selected_numbers = [candidate.student_number for candidate in selected]

        self.assertEqual(len(selected_numbers), 4)
        self.assertEqual(len(set(selected_numbers)), 4)
        self.assertIn("902000006", selected_numbers)
        self.assertIn("902000003", selected_numbers)

    def test_diff_summary_reports_missing_and_extra_rows(self):
        expected = {(1, "A"), (2, "B")}
        actual = {(2, "B"), (3, "C")}

        summary = diff_summary(expected, actual)

        self.assertEqual(summary["expected_count"], 2)
        self.assertEqual(summary["actual_count"], 2)
        self.assertEqual(summary["missing_count"], 1)
        self.assertEqual(summary["extra_count"], 1)
        self.assertEqual(summary["missing_samples"], [[1, "A"]])
        self.assertEqual(summary["extra_samples"], [[3, "C"]])

    def test_canonical_program_rows_prefers_resolved_structure_code(self):
        canonical = canonical_program_rows(
            [
                {
                    "cms_id": 11710,
                    "std_no": "902000502",
                    "program_code": "BBIB",
                    "structure_code": "2022-11",
                    "resolved_structure_code": "2022-IBM",
                    "reg_date": "2023-03-17",
                    "intake_date": "2022-06-06",
                    "start_term": "2022-11",
                    "stream": "AdvStdg",
                    "status": "Active",
                }
            ]
        )

        self.assertEqual(
            canonical,
            {
                (
                    11710,
                    "902000502",
                    "BBIB",
                    "2022-IBM",
                    "2023-03-17",
                    "2022-06-06",
                    "2022-11",
                    "AdvStdg",
                    "Active",
                    "",
                    "",
                )
            },
        )

    def test_canonical_education_rows_keeps_rows_without_school_name(self):
        canonical = canonical_education_rows(
            [
                {
                    "cms_id": 9,
                    "std_no": "901000008",
                    "school_name": "",
                    "type": "Secondary",
                    "level": "Cambridge Oversea School Certificate",
                    "end_date": "2002-11-01",
                }
            ]
        )

        self.assertEqual(
            canonical,
            {
                (
                    9,
                    "901000008",
                    "",
                    "Secondary",
                    "Cambridge Oversea School Certificate",
                    "",
                    "2002-11-01",
                )
            },
        )

    def test_canonical_contact_rows_merges_duplicate_contact_sources(self):
        canonical = canonical_contact_rows(
            [
                {
                    "name": "Malesekele Ntsohi",
                    "relationship": "Guardian",
                    "phone": "+26651676104",
                },
                {
                    "name": "Malesekele Ntsohi",
                    "relationship": "Guardian",
                    "phone": "+26651676104",
                    "occupation": "Pensioner",
                    "country": "Lesotho",
                },
            ]
        )

        self.assertEqual(
            canonical,
            {
                (
                    "Malesekele Ntsohi",
                    "Guardian",
                    "+26651676104",
                    "",
                    "Pensioner",
                    "",
                    "Lesotho",
                )
            },
        )

    def test_canonical_semester_rows_uses_sponsor_id(self):
        canonical = canonical_semester_rows(
            [
                {
                    "student_program_cms_id": 5018,
                    "cms_id": 34936,
                    "term": "2019-01",
                    "structure_semester_id": 1013,
                    "status": "Repeat",
                    "caf_date": "2019-02-22",
                    "sponsor_code": "Self Sponsor",
                    "sponsor_id": 2,
                }
            ]
        )

        self.assertEqual(
            canonical,
            {
                (
                    5018,
                    34936,
                    "2019-01",
                    1013,
                    "Repeat",
                    "2019-02-22",
                    2,
                )
            },
        )


if __name__ == "__main__":
    unittest.main()
