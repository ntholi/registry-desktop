import re
from datetime import datetime
from typing import Optional


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
        "DEFER": "Def",
        "DEFERRED": "Def",
        "DEFFERED": "Def",
        "DEFERED": "Def",
        "EXEMPTED": "EXP",
        "EXEMPT": "EXP",
        "EXEMPTION": "EXP",
        "NOTSUBMITTED": "DNS",
        "NOT SUBMITTED": "DNS",
        "DIDNOTSUBMIT": "DNS",
        "DID NOT SUBMIT": "DNS",
        "NOTATTEND": "DNA",
        "NOT ATTEND": "DNA",
        "DIDNOTATTEND": "DNA",
        "DID NOT ATTEND": "DNA",
        "NOTCOMPLETE": "DNC",
        "NOT COMPLETE": "DNC",
        "DIDNOTCOMPLETE": "DNC",
        "DID NOT COMPLETE": "DNC",
        "GRADENOTSUBMITTED": "GNS",
        "GRADE NOT SUBMITTED": "GNS",
        "NO MARK": "NM",
        "NOMARK": "NM",
        "NO MARKS": "NM",
        "NOMARKS": "NM",
        "OUTSTANDING": "X",
        "OUTSTANDING SUPPLEMENTARY": "X",
        "ANNULLED": "ANN",
        "ANNUL": "ANN",
        "FAILINCOMPLETE": "FIN",
        "FAIL INCOMPLETE": "FIN",
        "PROVISIONAL": "PP",
        "PASS PROVISIONAL": "PP",
        "PROVISIONALPASS": "PP",
        "PASSCONCEDED": "PC",
        "PASS CONCEDED": "PC",
        "CONCEDED": "PC",
        "AEGROTAT": "AP",
        "AEGROTAT PASS": "AP",
        "AEGROTATPASS": "AP",
    }

    if normalized_upper in grade_aliases:
        return grade_aliases[normalized_upper]

    if normalized.replace(".", "").replace("-", "").isdigit():
        try:
            marks = float(normalized)
            if marks >= 90:
                return "A+"
            elif marks >= 85:
                return "A"
            elif marks >= 80:
                return "A-"
            elif marks >= 75:
                return "B+"
            elif marks >= 70:
                return "B"
            elif marks >= 65:
                return "B-"
            elif marks >= 60:
                return "C+"
            elif marks >= 55:
                return "C"
            elif marks >= 50:
                return "C-"
            elif marks >= 45:
                return "PP"
            else:
                return "F"
        except ValueError:
            pass

    valid_grades = {
        "A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-",
        "F", "PC", "PX", "AP", "X", "DEF", "GNS", "ANN",
        "FIN", "FX", "DNC", "DNA", "PP", "DNS", "EXP", "NM"
    }

    if normalized_upper in valid_grades:
        found_grade = next((g for g in valid_grades if g == normalized_upper), None)
        return found_grade if found_grade else normalized_upper

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


def normalize_student_module_status(status: str | None) -> str:
    STATUS_ALIASES: dict[str, str] = {
        "ACTIVE": "Compulsory",
        "COMP": "Compulsory",
        "COMPULSARY": "Compulsory",
        "REQ": "Compulsory",
        "REQUIRED": "Compulsory",
        "DROPPED": "Drop",
        "DROPPED OUT": "Drop",
        "DROPED": "Drop",
        "DELETED": "Delete",
        "EXEMPT": "Exempted",
        "EXEMPTION": "Exempted",
    }
    DEFAULT_STUDENT_MODULE_STATUS = "Compulsory"
    VALID_STUDENT_MODULE_STATUSES = {
        "Add", "Compulsory", "Delete", "Drop", "Exempted", "Ineligible",
        "Repeat1", "Repeat2", "Repeat3", "Repeat4", "Repeat5", "Repeat6", "Repeat7",
        "Resit1", "Resit2", "Resit3", "Resit4", "Supplementary"
    }

    if not status:
        return DEFAULT_STUDENT_MODULE_STATUS

    candidate = status.strip()
    if not candidate:
        return DEFAULT_STUDENT_MODULE_STATUS

    if candidate in VALID_STUDENT_MODULE_STATUSES:
        return candidate

    upper_candidate = candidate.upper()
    if upper_candidate in STATUS_ALIASES:
        return STATUS_ALIASES[upper_candidate]

    if candidate.lower().startswith("repeat"):
        suffix = candidate[6:].strip()
        try:
            repeat_number = int(suffix)
        except ValueError:
            repeat_number = None

        if repeat_number is not None and 1 <= repeat_number <= 7:
            return f"Repeat{repeat_number}"

    if candidate.lower().startswith("resit"):
        suffix = candidate[5:].strip()
        try:
            resit_number = int(suffix)
        except ValueError:
            resit_number = None

        if resit_number is not None and 1 <= resit_number <= 4:
            return f"Resit{resit_number}"

    return DEFAULT_STUDENT_MODULE_STATUS


def normalize_module_type(module_type: str) -> str:
    type_mapping = {
        "standard": "Core",
        "core": "Core",
        "compulsory": "Core",
        "required": "Core",
        "major": "Major",
        "minor": "Minor",
        "elective": "Elective",
        "optional": "Elective",
        "delete": "Delete",
        "deleted": "Delete",
        "removed": "Delete",
    }

    return type_mapping.get(module_type.lower().strip(), "Core")


def normalize_gender(gender: str | None) -> str | None:
    if not gender:
        return None

    gender_mapping = {
        "m": "Male",
        "male": "Male",
        "man": "Male",
        "boy": "Male",
        "f": "Female",
        "female": "Female",
        "woman": "Female",
        "girl": "Female",
        "u": "Unknown",
        "unknown": "Unknown",
        "other": "Unknown",
        "n/a": "Unknown",
        "na": "Unknown",
        "not specified": "Unknown",
        "prefer not to say": "Unknown",
    }

    normalized = gender.strip().lower()
    return gender_mapping.get(normalized, "Unknown")


def normalize_marital_status(status: str | None) -> str | None:
    if not status:
        return None

    status_mapping = {
        "s": "Single",
        "single": "Single",
        "unmarried": "Single",
        "never married": "Single",
        "m": "Married",
        "married": "Married",
        "d": "Divorced",
        "divorced": "Divorced",
        "w": "Windowed",
        "windowed": "Windowed",
        "widow": "Windowed",
        "widower": "Windowed",
        "widowed": "Windowed",
        "o": "Other",
        "other": "Other",
        "separated": "Other",
        "n/a": "Other",
        "na": "Other",
    }

    normalized = status.strip().lower()
    return status_mapping.get(normalized, "Other")


def normalize_student_status(status: str | None) -> str:
    if not status:
        return "Active"

    status_mapping = {
        "active": "Active",
        "enrolled": "Active",
        "current": "Active",
        "applied": "Applied",
        "application": "Applied",
        "deceased": "Deceased",
        "dead": "Deceased",
        "passed away": "Deceased",
        "deleted": "Deleted",
        "removed": "Deleted",
        "graduated": "Graduated",
        "graduate": "Graduated",
        "completed": "Graduated",
        "suspended": "Suspended",
        "suspend": "Suspended",
        "terminated": "Terminated",
        "terminate": "Terminated",
        "withdrawn": "Withdrawn",
        "withdraw": "Withdrawn",
        "dropout": "Withdrawn",
        "dropped out": "Withdrawn",
    }

    normalized = status.strip().lower()
    return status_mapping.get(normalized, "Active")


def normalize_semester_status(status: str | None) -> str:
    if not status:
        return "Active"

    status_mapping = {
        "active": "Active",
        "current": "Active",
        "enrolled": "Enrolled",
        "outstanding": "Outstanding",
        "deferred": "Deferred",
        "defer": "Deferred",
        "deleted": "Deleted",
        "dnr": "DNR",
        "did not register": "DNR",
        "droppedout": "DroppedOut",
        "dropped out": "DroppedOut",
        "dropout": "DroppedOut",
        "withdrawn": "Withdrawn",
        "withdraw": "Withdrawn",
        "exempted": "Exempted",
        "exempt": "Exempted",
        "exemption": "Exempted",
        "inactive": "Inactive",
        "repeat": "Repeat",
    }

    normalized = status.strip().lower()
    return status_mapping.get(normalized, "Active")


def normalize_program_status(status: str | None) -> str:
    if not status:
        return "Active"

    status_mapping = {
        "active": "Active",
        "current": "Active",
        "changed": "Changed",
        "change": "Changed",
        "completed": "Completed",
        "complete": "Completed",
        "finished": "Completed",
        "deleted": "Deleted",
        "removed": "Deleted",
        "inactive": "Inactive",
    }

    normalized = status.strip().lower()
    return status_mapping.get(normalized, "Active")


def normalize_education_type(edu_type: str | None) -> str | None:
    if not edu_type:
        return None

    type_mapping = {
        "primary": "Primary",
        "elementary": "Primary",
        "secondary": "Secondary",
        "high school": "Secondary",
        "higher secondary": "Secondary",
        "tertiary": "Tertiary",
        "higher education": "Tertiary",
        "university": "Tertiary",
        "college": "Tertiary",
    }

    normalized = edu_type.strip().lower()
    return type_mapping.get(normalized, edu_type.strip())


def normalize_education_level(level: str | None) -> str | None:
    if not level:
        return None

    level_mapping = {
        "jce": "JCE",
        "j.c.e": "JCE",
        "j.c.e.": "JCE",
        "junior certificate": "JCE",
        "bjce": "BJCE",
        "b.j.c.e": "BJCE",
        "b.j.c.e.": "BJCE",
        "bggse": "BGGSE",
        "b.g.g.s.e": "BGGSE",
        "b.g.g.s.e.": "BGGSE",
        "bgcse": "BGCSE",
        "b.g.c.s.e": "BGCSE",
        "b.g.c.s.e.": "BGCSE",
        "lgcse": "LGCSE",
        "l.g.c.s.e": "LGCSE",
        "l.g.c.s.e.": "LGCSE",
        "igcse": "IGCSE",
        "i.g.c.s.e": "IGCSE",
        "i.g.c.s.e.": "IGCSE",
        "o-levels": "O-Levels",
        "o level": "O-Levels",
        "o levels": "O-Levels",
        "olevel": "O-Levels",
        "olevels": "O-Levels",
        "ordinary level": "O-Levels",
        "a-levels": "A-Levels",
        "a level": "A-Levels",
        "a levels": "A-Levels",
        "alevel": "A-Levels",
        "alevels": "A-Levels",
        "advanced level": "A-Levels",
        "matriculation": "Matriculation",
        "matric": "Matriculation",
        "cambridge oversea school certificate": "Cambridge Oversea School Certificate",
        "cambridge overseas": "Cambridge Oversea School Certificate",
        "certificate": "Certificate",
        "cert": "Certificate",
        "diploma": "Diploma",
        "dip": "Diploma",
        "degree": "Degree",
        "bachelor": "Degree",
        "bachelors": "Degree",
        "undergraduate": "Degree",
        "masters": "Masters",
        "master": "Masters",
        "postgraduate": "Masters",
        "msc": "Masters",
        "ma": "Masters",
        "mba": "Masters",
        "doctorate": "Doctorate",
        "phd": "Doctorate",
        "doctoral": "Doctorate",
        "others": "Others",
        "other": "Others",
        "n/a": "Others",
        "na": "Others",
    }

    normalized = level.strip().lower()
    return level_mapping.get(normalized, level.strip())


def normalize_next_of_kin_relationship(relationship: str | None) -> str | None:
    if not relationship:
        return None

    relationship_mapping = {
        "mother": "Mother",
        "mom": "Mother",
        "mum": "Mother",
        "mama": "Mother",
        "father": "Father",
        "dad": "Father",
        "papa": "Father",
        "brother": "Brother",
        "bro": "Brother",
        "sibling": "Brother",
        "sister": "Sister",
        "sis": "Sister",
        "child": "Child",
        "son": "Child",
        "daughter": "Child",
        "kid": "Child",
        "spouse": "Spouse",
        "husband": "Spouse",
        "wife": "Spouse",
        "partner": "Spouse",
        "other": "Other",
        "guardian": "Other",
        "relative": "Other",
        "friend": "Other",
        "uncle": "Other",
        "aunt": "Other",
        "grandparent": "Other",
        "grandfather": "Other",
        "grandmother": "Other",
        "cousin": "Other",
    }

    normalized = relationship.strip().lower()
    return relationship_mapping.get(normalized, "Other")


def normalize_text(text: str | None) -> str | None:
    if not text:
        return None

    normalized = text.strip()
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = re.sub(r"[^\w\s\-.,()&'/]", "", normalized)

    return normalized if normalized else None


def normalize_name(name: str | None) -> str | None:
    if not name:
        return None

    normalized = normalize_text(name)
    if not normalized:
        return None

    normalized = re.sub(r"\s+", " ", normalized.strip())

    return normalized


def normalize_phone(phone: str | None) -> str | None:
    if not phone:
        return None

    cleaned = re.sub(r"[^\d+\-() ]", "", phone.strip())
    cleaned = re.sub(r"\s+", " ", cleaned)

    return cleaned if cleaned else None


def normalize_email(email: str | None) -> str | None:
    if not email:
        return None

    normalized = email.strip().lower()

    if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", normalized):
        return None

    return normalized


def normalize_country(country: str | None) -> str | None:
    if not country:
        return None

    country_mapping = {
        "botswana": "Botswana",
        "bw": "Botswana",
        "bot": "Botswana",
        "south africa": "South Africa",
        "southafrica": "South Africa",
        "sa": "South Africa",
        "rsa": "South Africa",
        "zaf": "South Africa",
        "zimbabwe": "Zimbabwe",
        "zim": "Zimbabwe",
        "zw": "Zimbabwe",
        "zwe": "Zimbabwe",
        "zambia": "Zambia",
        "zm": "Zambia",
        "zmb": "Zambia",
        "namibia": "Namibia",
        "na": "Namibia",
        "nam": "Namibia",
        "lesotho": "Lesotho",
        "ls": "Lesotho",
        "lso": "Lesotho",
        "swaziland": "Eswatini",
        "eswatini": "Eswatini",
        "sz": "Eswatini",
        "swz": "Eswatini",
        "mozambique": "Mozambique",
        "moz": "Mozambique",
        "mz": "Mozambique",
        "angola": "Angola",
        "ao": "Angola",
        "ago": "Angola",
        "malawi": "Malawi",
        "mw": "Malawi",
        "mwi": "Malawi",
        "tanzania": "Tanzania",
        "tz": "Tanzania",
        "tza": "Tanzania",
        "kenya": "Kenya",
        "ke": "Kenya",
        "ken": "Kenya",
        "uganda": "Uganda",
        "ug": "Uganda",
        "uga": "Uganda",
        "nigeria": "Nigeria",
        "ng": "Nigeria",
        "nga": "Nigeria",
        "ghana": "Ghana",
        "gh": "Ghana",
        "gha": "Ghana",
    }

    normalized = country.strip().lower()
    return country_mapping.get(normalized, country.strip())


def normalize_nationality(nationality: str | None) -> str | None:
    if not nationality:
        return None

    nationality_mapping = {
        "motswana": "Motswana",
        "batswana": "Motswana",
        "botswana": "Motswana",
        "south african": "South African",
        "southafrican": "South African",
        "zimbabwean": "Zimbabwean",
        "zambian": "Zambian",
        "namibian": "Namibian",
        "mosotho": "Mosotho",
        "basotho": "Mosotho",
        "lesotho": "Mosotho",
        "swazi": "Swazi",
        "mozambican": "Mozambican",
        "angolan": "Angolan",
        "malawian": "Malawian",
        "tanzanian": "Tanzanian",
        "kenyan": "Kenyan",
        "ugandan": "Ugandan",
        "nigerian": "Nigerian",
        "ghanaian": "Ghanaian",
    }

    normalized = nationality.strip().lower()
    return nationality_mapping.get(normalized, nationality.strip())


def normalize_date(date_str: str | None) -> str | None:
    if not date_str or not date_str.strip():
        return None

    date_str = date_str.strip()

    date_formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%d-%m-%Y",
        "%m-%d-%Y",
        "%Y/%m/%d",
        "%d.%m.%Y",
        "%Y.%m.%d",
        "%d %b %Y",
        "%d %B %Y",
        "%b %d, %Y",
        "%B %d, %Y",
    ]

    for fmt in date_formats:
        try:
            parsed_date = datetime.strptime(date_str, fmt)
            return parsed_date.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return None


def normalize_marks(marks: str | None) -> float | None:
    if not marks:
        return None

    cleaned = marks.strip().replace("%", "").replace(",", ".")

    try:
        value = float(cleaned)
        return max(0.0, min(100.0, value))
    except ValueError:
        return None


def normalize_credits(credits: str | None) -> float | None:
    if not credits:
        return None

    cleaned = credits.strip().replace(",", ".")

    try:
        return float(cleaned)
    except ValueError:
        return None
