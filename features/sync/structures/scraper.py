from bs4 import BeautifulSoup

from base import get_logger
from base.browser import BASE_URL, Browser

logger = get_logger(__name__)


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
