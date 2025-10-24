from __future__ import annotations

from bs4 import BeautifulSoup

from base import get_logger
from base.browser import BASE_URL, Browser

logger = get_logger(__name__)


def get_cms_semesters(student_program_id: int) -> list[dict]:
    browser = Browser()
    url = f"{BASE_URL}/r_stdsemesterlist.php?showmaster=1&StdProgramID={student_program_id}"
    response = browser.fetch(url)
    page = BeautifulSoup(response.text, "lxml")
    table = page.select_one("table#ewlistmain")

    if not table:
        logger.warning(
            f"No semester table found for student program {student_program_id}"
        )
        return []

    semesters = []
    rows = table.select("tr.ewTableRow, tr.ewTableAltRow")

    for row in rows:
        view_link = row.select_one("a[href*='r_stdsemesterview.php?StdSemesterID=']")
        if view_link:
            href = view_link.get("href")
            if href and isinstance(href, str) and "StdSemesterID=" in href:
                semester_id = href.split("StdSemesterID=")[1].split("&")[0]

                cols = row.select("td")
                term = None
                if len(cols) > 0:
                    term_span = cols[0].select_one("span")
                    if term_span:
                        term = term_span.get_text(strip=True)
                    else:
                        term_text = cols[0].get_text(strip=True)
                        if term_text:
                            term = term_text

                semesters.append({"id": int(semester_id), "term": term})

    logger.info(
        f"Found {len(semesters)} semesters for student program {student_program_id}"
    )
    return semesters


def get_cms_semester_modules(student_semester_id: int) -> list[dict]:
    browser = Browser()
    url = f"{BASE_URL}/r_stdmodulelist.php?showmaster=1&StdSemesterID={student_semester_id}"
    response = browser.fetch(url)
    page = BeautifulSoup(response.text, "lxml")
    table = page.select_one("table#ewlistmain")

    if not table:
        logger.warning(
            f"No module table found for student semester {student_semester_id}"
        )
        return []

    modules = []
    rows = table.select("tr.ewTableRow, tr.ewTableAltRow")

    for row in rows:
        view_link = row.select_one("a[href*='r_stdmoduleview.php?StdModuleID=']")
        if view_link:
            href = view_link.get("href")
            if href and isinstance(href, str) and "StdModuleID=" in href:
                module_id = href.split("StdModuleID=")[1].split("&")[0]

                cols = row.select("td")
                module_code = None
                if len(cols) > 1:
                    module_span = cols[1].select_one("span")
                    if module_span:
                        module_text = module_span.get_text(strip=True)
                        parts = module_text.split(maxsplit=1)
                        if parts:
                            module_code = parts[0]

                if module_code:
                    modules.append({"id": int(module_id), "module_code": module_code})

    logger.info(
        f"Found {len(modules)} modules for student semester {student_semester_id}"
    )
    return modules
