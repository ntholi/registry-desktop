import re
from dataclasses import dataclass
from typing import Any


@dataclass
class MarksRange:
    min: int
    max: int


@dataclass
class GradeDefinition:
    grade: str
    points: float | None
    description: str
    marks_range: MarksRange | None = None


GRADES = [
    GradeDefinition("A+", 4.0, "Pass with Distinction", MarksRange(90, 100)),
    GradeDefinition("A", 4.0, "Pass with Distinction", MarksRange(85, 89)),
    GradeDefinition("A-", 4.0, "Pass with Distinction", MarksRange(80, 84)),
    GradeDefinition("B+", 3.67, "Pass with Merit", MarksRange(75, 79)),
    GradeDefinition("B", 3.33, "Pass with Merit", MarksRange(70, 74)),
    GradeDefinition("B-", 3.0, "Pass with Merit", MarksRange(65, 69)),
    GradeDefinition("C+", 2.67, "Pass", MarksRange(60, 64)),
    GradeDefinition("C", 2.33, "Pass", MarksRange(55, 59)),
    GradeDefinition("C-", 2.0, "Pass", MarksRange(50, 54)),
    GradeDefinition("PP", 0.0, "Pass Provisional", MarksRange(45, 49)),
    GradeDefinition("F", 0.0, "Fail", MarksRange(0, 49)),
    GradeDefinition("EXP", None, "Exempted"),
    GradeDefinition("PC", 1.67, "Pass Conceded"),
    GradeDefinition("PX", 1.67, "Pass (supplementary work submitted)"),
    GradeDefinition("AP", 2.0, "Aegrotat Pass"),
    GradeDefinition("X", 0.0, "Outstanding Supplementary Assessment"),
    GradeDefinition("Def", None, "Deferred"),
    GradeDefinition("GNS", 0.0, "Grade Not Submitted"),
    GradeDefinition("ANN", 0.0, "Result Annulled Due To Misconduct"),
    GradeDefinition("FIN", 0.0, "Fail Incomplete"),
    GradeDefinition("FX", 0.0, "Fail (supplementary work submitted)"),
    GradeDefinition("DNC", 0.0, "Did Not Complete"),
    GradeDefinition("DNA", 0.0, "Did Not Attend"),
    GradeDefinition("DNS", 0.0, "Did Not Submit"),
    GradeDefinition("NM", None, "No Mark"),
]


def normalize_grade_symbol(grade: str) -> str:
    if not grade or not grade.strip():
        return "F"

    normalized = grade.strip()

    normalized = re.sub(r"[.\s]+$", "", normalized)
    normalized = re.sub(r"^[.\s]+", "", normalized)

    normalized_upper = normalized.upper()

    grade_aliases = {
        "DFR": "F",
        "W": "F",
        "P": "C-",
        "PASS": "C-",
        "FAIL": "F",
        "FAILED": "F",
        "DEF": "Def",
    }

    if normalized_upper in grade_aliases:
        return grade_aliases[normalized_upper]

    if normalized.replace(".", "").isdigit():
        try:
            marks = float(normalized)
            letter_grade = get_letter_grade(marks)
            return letter_grade
        except ValueError:
            pass

    valid_grades = {g.grade for g in GRADES}
    if normalized_upper in valid_grades:
        return normalized_upper

    for valid_grade in valid_grades:
        if valid_grade.upper() == normalized_upper:
            return valid_grade

    return "F"


def normalize_module_name(name: str) -> str:
    roman_to_arabic = {
        "i": "1",
        "ii": "2",
        "iii": "3",
        "iv": "4",
        "v": "5",
        "vi": "6",
        "vii": "7",
        "viii": "8",
        "ix": "9",
        "x": "10",
    }

    def replace_roman(match: re.Match[str]) -> str:
        return roman_to_arabic.get(match.group(0).lower(), match.group(0))

    normalized = name.strip().lower().replace("&", "and")
    normalized = re.sub(r"\b(i{1,3}|iv|v|vi{0,3}|ix|x)\b", replace_roman, normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def get_grade_by_symbol(grade: str) -> GradeDefinition | None:
    normalized = normalize_grade_symbol(grade)
    for g in GRADES:
        if g.grade == normalized:
            return g
    return None


def get_grade_by_points(points: float) -> GradeDefinition | None:
    grades_with_points = [g for g in GRADES if g.points is not None]
    sorted_grades = sorted(
        grades_with_points, key=lambda g: g.points or 0, reverse=True
    )
    for grade in sorted_grades:
        if grade.points is not None and points >= grade.points:
            return grade
    return sorted_grades[-1] if sorted_grades else None


def get_grade_by_marks(marks: float) -> GradeDefinition | None:
    for g in GRADES:
        if g.marks_range and g.marks_range.min <= marks <= g.marks_range.max:
            return g
    return None


def get_letter_grade(marks: float) -> str:
    grade_def = get_grade_by_marks(marks)
    return grade_def.grade if grade_def else "F"


def get_grade_points(grade: str) -> float:
    grade_def = get_grade_by_symbol(grade)
    return grade_def.points if grade_def and grade_def.points is not None else 0.0


def is_failing_grade(grade: str) -> bool:
    failing_grades = ["F", "X", "GNS", "ANN", "FIN", "FX", "DNC", "DNA", "DNS"]
    return normalize_grade_symbol(grade) in failing_grades


def is_passing_grade(grade: str) -> bool:
    passing_grades = [g.grade for g in GRADES if g.points is not None and g.points > 0]
    return normalize_grade_symbol(grade) in passing_grades


def is_supplementary_grade(grade: str) -> bool:
    return normalize_grade_symbol(grade) == "PP"


def is_failing_or_sup_grade(grade: str) -> bool:
    return is_failing_grade(grade) or is_supplementary_grade(grade)


@dataclass
class ModuleSummary:
    points: float
    credits_attempted: int
    credits_completed: int
    gpa: float
    is_no_marks: bool


def summarize_modules(modules: list[Any]) -> ModuleSummary:
    relevant = [m for m in modules if m.status not in ["Delete", "Drop"]]

    points = 0.0
    credits_attempted = 0
    credits_for_gpa = 0
    credits_completed = 0

    for m in relevant:
        normalized_grade = normalize_grade_symbol(m.grade or "")
        if normalized_grade and normalized_grade != "NM":
            grade_points = get_grade_points(m.grade)
            if grade_points > 0:
                credits_completed += m.semester_module.credits

    for m in relevant:
        normalized_grade = normalize_grade_symbol(m.grade or "")
        grade_points = get_grade_points(m.grade or "")
        grade_definition = get_grade_by_symbol(m.grade or "")

        credits_attempted += m.semester_module.credits

        if normalized_grade and normalized_grade != "NM":
            credits_for_gpa += m.semester_module.credits
            if grade_definition and grade_definition.points is not None:
                points += grade_points * m.semester_module.credits

    gpa = calculate_gpa(points, credits_for_gpa)

    return ModuleSummary(
        points=points,
        credits_attempted=credits_attempted,
        credits_completed=credits_completed,
        gpa=gpa,
        is_no_marks=False,
    )


def calculate_gpa(points: float, credits_for_gpa: int) -> float:
    return points / credits_for_gpa if credits_for_gpa > 0 else 0.0


@dataclass
class GradePoint:
    semester_id: int
    gpa: float
    cgpa: float
    credits_attempted: int
    credits_completed: int


@dataclass
class ModuleInfo:
    id: int
    code: str
    name: str


@dataclass
class FacultyRemarksResult:
    status: str
    failed_modules: list[ModuleInfo]
    supplementary_modules: list[ModuleInfo]
    message: str
    details: str
    total_modules: int
    total_credits_attempted: int
    total_credits_completed: int
    points: list[GradePoint]
    latest_points: GradePoint


def get_academic_remarks(programs: list[Any]) -> FacultyRemarksResult:
    semesters, student_modules = extract_data(programs)

    points = []
    cumulative_points = 0.0
    cumulative_credits_for_gpa = 0

    for semester in semesters:
        semester_summary = summarize_modules(semester.student_modules)
        cumulative_points += semester_summary.points

        semester_credits_for_gpa = sum(
            sm.semester_module.credits
            for sm in semester.student_modules
            if sm.status not in ["Delete", "Drop"] and sm.grade and sm.grade != "NM"
        )

        cumulative_credits_for_gpa += semester_credits_for_gpa
        cgpa = calculate_gpa(cumulative_points, cumulative_credits_for_gpa)

        points.append(
            GradePoint(
                semester_id=semester.id,
                gpa=semester_summary.gpa,
                cgpa=cgpa,
                credits_attempted=semester_summary.credits_attempted,
                credits_completed=semester_summary.credits_completed,
            )
        )

    total_credits_attempted = sum(p.credits_attempted for p in points)
    total_credits_completed = sum(p.credits_completed for p in points)

    if any(m.grade == "NM" for m in student_modules):
        return FacultyRemarksResult(
            status="No Marks",
            failed_modules=[],
            supplementary_modules=[],
            message="No Marks",
            details="One or more modules have no marks captured",
            total_modules=0,
            total_credits_attempted=total_credits_attempted,
            total_credits_completed=total_credits_completed,
            points=points,
            latest_points=points[-1] if points else GradePoint(0, 0, 0, 0, 0),
        )

    latest_failed_modules = []
    if semesters:
        latest_failed_modules = [
            m for m in semesters[-1].student_modules if is_failing_grade(m.grade or "")
        ]

    failed_modules = []
    for m in student_modules:
        if not is_failing_or_sup_grade(m.grade or ""):
            continue

        has_passed_later = any(
            other.semester_module.module.name == m.semester_module.module.name
            and other.id != m.id
            and is_passing_grade(other.grade or "")
            for other in student_modules
            if other.semester_module.module
        )

        if not has_passed_later:
            failed_modules.append(m)

    supplementary = [
        m for m in student_modules if is_supplementary_grade(m.grade or "")
    ]

    remain_in_semester = len(latest_failed_modules) >= 3
    status = "Remain in Semester" if remain_in_semester else "Proceed"

    message_parts = [status]

    if supplementary:
        supp_names = ", ".join(
            m.semester_module.module.name
            for m in supplementary
            if m.semester_module.module
        )
        message_parts.append(f"must supplement {supp_names}")

    if failed_modules:
        failed_names = ", ".join(
            m.semester_module.module.name
            for m in failed_modules
            if m.semester_module.module
        )
        message_parts.append(f"must repeat {failed_names}")

    message = ", ".join(message_parts)

    if remain_in_semester:
        details = f"Failed {len(latest_failed_modules)} modules in latest semester"
    else:
        details = "Student is eligible to proceed"

    return FacultyRemarksResult(
        status=status,
        failed_modules=get_unique_modules(failed_modules),
        supplementary_modules=get_unique_modules(supplementary),
        message=message,
        details=details,
        total_modules=len(student_modules),
        total_credits_attempted=total_credits_attempted,
        total_credits_completed=total_credits_completed,
        points=points,
        latest_points=points[-1] if points else GradePoint(0, 0, 0, 0, 0),
    )


def get_unique_modules(modules: list[Any]) -> list[ModuleInfo]:
    unique = []
    seen_names = set()

    for m in modules:
        if m.semester_module.module:
            module = m.semester_module.module
            if module.name not in seen_names:
                unique.append(
                    ModuleInfo(
                        id=module.id,
                        code=module.code,
                        name=module.name,
                    )
                )
                seen_names.add(module.name)

    return unique


def extract_data(programs: list[Any]) -> tuple[list[Any], list[Any]]:
    filtered_programs = sorted(programs, key=lambda p: p.id, reverse=True)
    active_programs = [p for p in filtered_programs if p.status == "Active"]

    if not active_programs:
        active_programs = [p for p in filtered_programs if p.status == "Completed"]

    if not active_programs:
        return [], []

    semesters = active_programs[0].semesters or []
    filtered_semesters = sorted(
        [
            s
            for s in semesters
            if s.status not in ["Deleted", "Deferred", "DroppedOut", "Withdrawn"]
        ],
        key=lambda s: s.id,
    )

    student_modules = [
        m
        for s in filtered_semesters
        for m in s.student_modules
        if m.status not in ["Delete", "Drop"]
    ]

    return filtered_semesters, student_modules


@dataclass
class StructureModuleInfo:
    id: int
    code: str
    name: str
    original_name: str
    type: str
    credits: int
    semester_number: str


@dataclass
class OutstandingModules:
    failed_never_repeated: list[StructureModuleInfo]
    never_attempted: list[StructureModuleInfo]


def get_outstanding_from_structure(
    programs: list[Any], structure_modules: list[Any]
) -> OutstandingModules:
    program = next((p for p in programs if p.status in ["Active", "Completed"]), None)
    if not program:
        raise ValueError("No active program found for student")

    required_modules = []
    for semester in structure_modules:
        for sm in semester.semester_modules:
            if sm.module and not sm.hidden:
                required_modules.append(
                    StructureModuleInfo(
                        id=sm.module.id,
                        code=sm.module.code,
                        name=normalize_module_name(sm.module.name),
                        original_name=sm.module.name,
                        type=sm.type,
                        credits=sm.credits,
                        semester_number=semester.semester_number,
                    )
                )

    _, student_modules = extract_data(programs)

    attempted_modules = {}
    for sm in student_modules:
        if sm.semester_module.module:
            name = normalize_module_name(sm.semester_module.module.name)
            if name not in attempted_modules:
                attempted_modules[name] = []
            attempted_modules[name].append(sm)

    failed_never_repeated = []
    never_attempted = []

    for md in required_modules:
        attempts = attempted_modules.get(md.name, [])

        if not attempts:
            never_attempted.append(
                StructureModuleInfo(
                    id=md.id,
                    code=md.code,
                    name=md.original_name,
                    original_name=md.original_name,
                    type=md.type,
                    credits=md.credits,
                    semester_number=md.semester_number,
                )
            )
        else:
            passed_attempts = [a for a in attempts if is_passing_grade(a.grade or "")]

            if not passed_attempts and len(attempts) == 1:
                failed_never_repeated.append(
                    StructureModuleInfo(
                        id=md.id,
                        code=md.code,
                        name=md.original_name,
                        original_name=md.original_name,
                        type=md.type,
                        credits=md.credits,
                        semester_number=md.semester_number,
                    )
                )

    return OutstandingModules(
        failed_never_repeated=failed_never_repeated,
        never_attempted=never_attempted,
    )
