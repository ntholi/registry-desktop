from bs4 import BeautifulSoup

from base import get_logger
from base.browser import BASE_URL, Browser

logger = get_logger(__name__)


def scrape_structures(program_id: int) -> list[dict[str, str | int]]:
    browser = Browser()
    url = f"{BASE_URL}/f_structurelist.php?showmaster=1&ProgramID={program_id}"
    response = browser.fetch(url)
    page = BeautifulSoup(response.text, "lxml")

    structures = []
    rows = page.select("table#ewlistmain tr")

    for row in rows:
        cells = row.select("td")
        if len(cells) < 2:
            continue

        structure_code = cells[0].get_text(strip=True)
        structure_desc = cells[1].get_text(strip=True)

        if not structure_code:
            continue

        view_link = row.select_one("a[href*='f_structureview.php']")
        if view_link and "href" in view_link.attrs:
            href = str(view_link["href"])
            if "StructureID=" in href:
                structure_id = href.split("StructureID=")[1].split("&")[0]
                structures.append(
                    {
                        "id": int(structure_id),
                        "code": structure_code,
                        "desc": structure_desc,
                    }
                )

    return structures


def scrape_semesters(structure_id: int) -> list[dict[str, str | int | float]]:
    browser = Browser()
    url = f"{BASE_URL}/f_semesterlist.php?showmaster=1&StructureID={structure_id}"
    response = browser.fetch(url)
    page = BeautifulSoup(response.text, "lxml")

    semesters = []
    rows = page.select("table#ewlistmain tr")

    for row in rows:
        cells = row.select("td")
        if len(cells) < 2:
            continue

        semester_name = cells[0].get_text(strip=True)
        credits_text = cells[1].get_text(strip=True)

        if not semester_name or not credits_text:
            continue

        try:
            credits = float(credits_text)
        except (ValueError, TypeError):
            continue

        view_link = row.select_one("a[href*='f_semesterview.php']")
        if view_link and "href" in view_link.attrs:
            href = str(view_link["href"])
            if "SemesterID=" in href:
                semester_id = href.split("SemesterID=")[1].split("&")[0]
                semester_number = int(semester_name.split()[0])
                name_parts = semester_name.split(maxsplit=1)
                clean_name = name_parts[1] if len(name_parts) > 1 else semester_name
                semesters.append(
                    {
                        "id": int(semester_id),
                        "semester_number": semester_number,
                        "name": clean_name,
                        "total_credits": credits,
                    }
                )

    return semesters


def scrape_semester_modules(
    semester_id: int,
) -> list[dict[str, str | int | float | bool]]:
    browser = Browser()
    url = f"{BASE_URL}/f_semmodulelist.php?showmaster=1&SemesterID={semester_id}"
    response = browser.fetch(url)
    page = BeautifulSoup(response.text, "lxml")

    semester_modules = []
    rows = page.select("table#ewlistmain tr")

    for row in rows:
        cells = row.select("td")
        if len(cells) < 4:
            continue

        module_text = cells[0].get_text(strip=True)
        module_type = cells[1].get_text(strip=True)
        credits_text = cells[3].get_text(strip=True)

        if not module_text or not module_type:
            continue

        parts = module_text.split(maxsplit=1)
        if len(parts) < 2:
            continue

        module_code = parts[0]
        module_name = parts[1]

        try:
            credits = float(credits_text)
        except (ValueError, TypeError):
            continue

        view_link = row.select_one("a[href*='f_semmoduleview.php']")
        if view_link and "href" in view_link.attrs:
            href = str(view_link["href"])
            if "SemModuleID=" in href:
                sem_module_id = href.split("SemModuleID=")[1].split("&")[0]
                semester_modules.append(
                    {
                        "id": int(sem_module_id),
                        "module_code": module_code,
                        "module_name": module_name,
                        "type": module_type,
                        "credits": credits,
                        "hidden": False,
                    }
                )

    return semester_modules


def scrape_school_details(school_code: str) -> dict[str, str | int] | None:
    browser = Browser()
    url = f"{BASE_URL}/f_schoollist.php"
    response = browser.fetch(url)
    page = BeautifulSoup(response.text, "lxml")

    rows = page.select("table#ewlistmain tr")
    for row in rows:
        cells = row.select("td")
        if len(cells) > 1:
            code_cell = cells[0].get_text(strip=True)
            if code_cell.upper() == school_code.upper():
                name_cell = cells[1].get_text(strip=True)
                view_link = row.select_one("a[href*='f_schoolview.php']")
                if view_link and "href" in view_link.attrs:
                    href = str(view_link["href"])
                    if "SchoolID=" in href:
                        school_id = href.split("SchoolID=")[1]
                        return {
                            "id": int(school_id),
                            "code": code_cell,
                            "name": name_cell,
                        }
    return None


def scrape_school_id(school_code: str) -> int | None:
    browser = Browser()
    url = f"{BASE_URL}/f_schoollist.php"
    response = browser.fetch(url)
    page = BeautifulSoup(response.text, "lxml")

    rows = page.select("table#ewlistmain tr")
    for row in rows:
        cells = row.select("td")
        if len(cells) > 0:
            code_cell = cells[0].get_text(strip=True)
            if code_cell.upper() == school_code.upper():
                view_link = row.select_one("a[href*='f_schoolview.php']")
                if view_link and "href" in view_link.attrs:
                    href = str(view_link["href"])
                    if "SchoolID=" in href:
                        school_id = href.split("SchoolID=")[1]
                        return int(school_id)
    return None


def scrape_programs(school_id: int) -> list[dict[str, str]]:
    browser = Browser()
    url = f"{BASE_URL}/f_programlist.php?showmaster=1&SchoolID={school_id}"
    response = browser.fetch(url)
    page = BeautifulSoup(response.text, "lxml")

    programs = []
    rows = page.select("table#ewlistmain tr")

    for row in rows:
        cells = row.select("td")
        if len(cells) < 3:
            continue

        program_code = cells[0].get_text(strip=True)
        program_name = cells[1].get_text(strip=True)

        if not program_code or not program_name:
            continue

        view_link = row.select_one("a[href*='f_programview.php']")
        if view_link and "href" in view_link.attrs:
            href = str(view_link["href"])
            if "ProgramID=" in href:
                program_id = href.split("ProgramID=")[1]
                programs.append(
                    {
                        "id": program_id,
                        "code": program_code,
                        "name": program_name,
                    }
                )

    return programs
