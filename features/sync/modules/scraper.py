import re

from bs4 import BeautifulSoup

from base import get_logger
from base.browser import BASE_URL, Browser

logger = get_logger(__name__)


def scrape_modules(module_code: str) -> list[dict[str, str]]:
    browser = Browser()

    url = (
        f"{BASE_URL}/f_modulelist.php?"
        f"a_search=E&"
        f"z_ModuleCode=LIKE%2C%27%25%2C%25%27&"
        f"x_ModuleCode={module_code}&"
        f"sv_x_ModuleCode=&"
        f"s_x_ModuleCode=&"
        f"z_ModuleName=LIKE%2C%27%25%2C%25%27&"
        f"x_ModuleName=&"
        f"sv_x_ModuleName=&"
        f"s_x_ModuleName=&"
        f"Submit=Search"
    )

    response = browser.fetch(url)
    page = BeautifulSoup(response.text, "lxml")

    modules = []
    rows = page.select("table#ewlistmain tr")

    for row in rows:
        cells = row.select("td")
        if len(cells) < 5:
            continue

        code = cells[0].get_text(strip=True)
        name = cells[1].get_text(strip=True)
        status = cells[2].get_text(strip=True)
        timestamp = cells[4].get_text(strip=True)

        if not code or not name:
            continue

        view_link = row.select_one("a[href*='f_moduleview.php']")
        if view_link and "href" in view_link.attrs:
            href = str(view_link["href"])
            if "ModuleID=" in href:
                module_id = href.split("ModuleID=")[1].split("&")[0]
                modules.append(
                    {
                        "id": int(module_id),
                        "code": code,
                        "name": name,
                        "status": status,
                        "timestamp": timestamp,
                    }
                )

    return modules


def scrape_all_modules(progress_callback=None) -> list[dict[str, str]]:
    browser = Browser()
    all_modules = []
    current_page = 1
    start = 1

    base_url = f"{BASE_URL}/f_modulelist.php"

    if progress_callback:
        progress_callback("Fetching first page to determine total records...", 0, 1)

    response = browser.fetch(base_url)
    page = BeautifulSoup(response.text, "lxml")

    total_records = _extract_total_records(page)

    if total_records == 0:
        logger.warning("No modules found on the page")
        return []

    records_per_page = 10
    total_pages = (total_records + records_per_page - 1) // records_per_page

    logger.info(
        f"Total records: {total_records}, pages: {total_pages}, records per page: {records_per_page}"
    )

    modules = _extract_modules_from_page(page)
    all_modules.extend(modules)

    if progress_callback:
        progress_callback(
            f"Scraped page 1/{total_pages} ({len(modules)} modules)",
            current_page,
            total_pages,
        )

    while current_page < total_pages:
        current_page += 1
        start += records_per_page

        url = f"{base_url}?start={start}"
        response = browser.fetch(url)
        page = BeautifulSoup(response.text, "lxml")

        modules = _extract_modules_from_page(page)
        all_modules.extend(modules)

        if progress_callback:
            progress_callback(
                f"Scraped page {current_page}/{total_pages} ({len(modules)} modules)",
                current_page,
                total_pages,
            )

        if len(modules) == 0:
            logger.warning(f"No modules found on page {current_page}, stopping")
            break

    logger.info(f"Scraped total of {len(all_modules)} modules")
    return all_modules


def _extract_total_records(page: BeautifulSoup) -> int:
    pager_text = page.select_one("form#ewpagerform")
    if not pager_text:
        return 0

    text = pager_text.get_text(strip=True)
    match = re.search(r"Records\s+\d+\s+to\s+\d+\s+of\s+(\d+)", text)
    if match:
        return int(match.group(1))

    return 0


def _extract_modules_from_page(page: BeautifulSoup) -> list[dict[str, str]]:
    modules = []
    rows = page.select("table#ewlistmain tr")

    for row in rows:
        cells = row.select("td")
        if len(cells) < 5:
            continue

        code = cells[0].get_text(strip=True)
        name = cells[1].get_text(strip=True)
        status = cells[2].get_text(strip=True)
        timestamp = cells[4].get_text(strip=True)

        if not code or not name:
            continue

        view_link = row.select_one("a[href*='f_moduleview.php']")
        if view_link and "href" in view_link.attrs:
            href = str(view_link["href"])
            if "ModuleID=" in href:
                module_id = href.split("ModuleID=")[1].split("&")[0]
                modules.append(
                    {
                        "id": int(module_id),
                        "code": code,
                        "name": name,
                        "status": status,
                        "timestamp": timestamp,
                    }
                )

    return modules
