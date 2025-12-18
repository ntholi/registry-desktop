import re

from bs4 import BeautifulSoup

from base import get_logger
from base.browser import BASE_URL, Browser

logger = get_logger(__name__)


def scrape_all_terms(progress_callback=None) -> list[dict]:
    browser = Browser()
    all_terms = []
    current_page = 1
    start = 1

    base_url = f"{BASE_URL}/f_termlist.php"

    if progress_callback:
        progress_callback("Fetching first page to determine total records...", 0, 1)

    response = browser.fetch(base_url)
    page = BeautifulSoup(response.text, "lxml")

    total_records = _extract_total_records(page)

    if total_records == 0:
        logger.warning("No terms found on the page")
        return []

    records_per_page = 10
    total_pages = (total_records + records_per_page - 1) // records_per_page

    logger.info(
        f"Total records: {total_records}, pages: {total_pages}, records per page: {records_per_page}"
    )

    terms = _extract_terms_from_page(page)
    all_terms.extend(terms)

    if progress_callback:
        progress_callback(
            f"Scraped page 1/{total_pages} ({len(terms)} terms)",
            current_page,
            total_pages,
        )

    while current_page < total_pages:
        current_page += 1
        start += records_per_page

        url = f"{base_url}?start={start}"
        response = browser.fetch(url)
        page = BeautifulSoup(response.text, "lxml")

        terms = _extract_terms_from_page(page)
        all_terms.extend(terms)

        if progress_callback:
            progress_callback(
                f"Scraped page {current_page}/{total_pages} ({len(terms)} terms)",
                current_page,
                total_pages,
            )

        if len(terms) == 0:
            logger.warning(f"No terms found on page {current_page}, stopping")
            break

    logger.info(f"Scraped total of {len(all_terms)} terms")
    return all_terms


def _extract_total_records(page: BeautifulSoup) -> int:
    pager_text = page.select_one("form#ewpagerform")
    if not pager_text:
        return 0

    text = pager_text.get_text(strip=True)
    match = re.search(r"Records\s+\d+\s+to\s+\d+\s+of\s+(\d+)", text)
    if match:
        return int(match.group(1))

    return 0


def _extract_terms_from_page(page: BeautifulSoup) -> list[dict]:
    terms = []
    rows = page.select("table#ewlistmain tr")

    for row in rows:
        cells = row.select("td")
        if len(cells) < 7:
            continue

        code = cells[0].get_text(strip=True)
        name = cells[1].get_text(strip=True)
        start_date = cells[2].get_text(strip=True)
        end_date = cells[3].get_text(strip=True)

        is_current_checkbox = cells[4].select_one("input[type='checkbox']")
        is_current = is_current_checkbox is not None and is_current_checkbox.has_attr(
            "checked"
        )

        year_text = cells[6].get_text(strip=True)
        year = int(year_text) if year_text.isdigit() else None

        if not code:
            continue

        terms.append(
            {
                "code": code,
                "name": name if name else None,
                "start_date": start_date if start_date else None,
                "end_date": end_date if end_date else None,
                "is_active": is_current,
                "year": year,
            }
        )

    return terms
