import re
from typing import TypedDict

from bs4 import BeautifulSoup

from base import get_logger
from base.browser import BASE_URL, Browser

logger = get_logger(__name__)


class ModuleScrapeData(TypedDict):
    cms_id: int
    code: str
    name: str
    status: str
    timestamp: str


def _extract_module_id(href: str) -> int | None:
    if "ModuleID=" not in href:
        return None

    try:
        return int(href.split("ModuleID=")[1].split("&")[0])
    except (ValueError, IndexError):
        return None


def _extract_module_rows(page: BeautifulSoup) -> list[ModuleScrapeData]:
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

        if not code:
            continue

        view_link = row.select_one("a[href*='f_moduleview.php']")
        if not view_link or "href" not in view_link.attrs:
            continue

        module_id = _extract_module_id(str(view_link["href"]))
        if module_id is None:
            continue

        modules.append(
            {
                "cms_id": module_id,
                "code": code,
                "name": name,
                "status": status,
                "timestamp": timestamp,
            }
        )

    return modules


def _dedupe_modules(modules: list[ModuleScrapeData]) -> list[ModuleScrapeData]:
    unique_modules: list[ModuleScrapeData] = []
    seen_ids: set[int] = set()

    for module in modules:
        module_id = int(module["cms_id"])
        if module_id in seen_ids:
            continue
        seen_ids.add(module_id)
        unique_modules.append(module)

    return unique_modules


def scrape_modules(module_code: str) -> list[ModuleScrapeData]:
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

    return _dedupe_modules(_extract_module_rows(page))


def _extract_pager_bounds(page: BeautifulSoup) -> tuple[int, int, int] | None:
    pager = page.select_one("form#ewpagerform")
    if not pager:
        return None

    text = pager.get_text(" ", strip=True)
    match = re.search(r"Records\s+(\d+)\s+to\s+(\d+)\s+of\s+(\d+)", text)
    if not match:
        return None

    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def scrape_all_modules(progress_callback=None) -> list[ModuleScrapeData]:
    browser = Browser()
    all_modules: list[ModuleScrapeData] = []
    current_page = 1

    base_url = f"{BASE_URL}/f_modulelist.php?cmd=resetall"

    if progress_callback:
        progress_callback("Fetching first page to determine total records...", 0, 1)

    response = browser.fetch(base_url)
    page = BeautifulSoup(response.text, "lxml")

    pager_bounds = _extract_pager_bounds(page)
    modules = _extract_modules_from_page(page)
    all_modules.extend(_dedupe_modules(modules))

    if not pager_bounds:
        if not all_modules:
            logger.warning("No modules found on the page")
        logger.info(f"Scraped total of {len(all_modules)} modules")
        return all_modules

    first_record, last_record, total_records = pager_bounds
    records_per_page = max(last_record - first_record + 1, 1)
    total_pages = (total_records + records_per_page - 1) // records_per_page

    logger.info(
        f"Total records: {total_records}, pages: {total_pages}, records per page: {records_per_page}"
    )

    if progress_callback:
        progress_callback(
            f"Scraped page 1/{total_pages} ({len(all_modules)} modules)",
            current_page,
            total_pages,
        )

    next_start = last_record + 1

    while next_start <= total_records:
        current_page += 1
        url = f"{base_url}&start={next_start}"
        response = browser.fetch(url)
        page = BeautifulSoup(response.text, "lxml")

        modules = _extract_modules_from_page(page)
        existing_ids = {module["cms_id"] for module in all_modules}
        new_modules = [
            module for module in modules if module["cms_id"] not in existing_ids
        ]
        all_modules.extend(new_modules)

        if progress_callback:
            progress_callback(
                f"Scraped page {current_page}/{total_pages} ({len(new_modules)} modules)",
                current_page,
                total_pages,
            )

        if len(modules) == 0:
            logger.warning(f"No modules found on page {current_page}, stopping")
            break

        pager_bounds = _extract_pager_bounds(page)
        if not pager_bounds:
            break

        _, current_last, total_records = pager_bounds
        if current_last < next_start:
            break

        next_start = current_last + 1

    logger.info(f"Scraped total of {len(all_modules)} modules")
    return all_modules


def _extract_modules_from_page(page: BeautifulSoup) -> list[ModuleScrapeData]:
    return _extract_module_rows(page)
