import re
from collections.abc import Callable
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


class ModuleScrapeIntegrityError(RuntimeError):
    pass


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


def _module_signature(module: ModuleScrapeData) -> tuple[int, str, str, str, str]:
    return (
        int(module["cms_id"]),
        str(module["code"]),
        str(module["name"]),
        str(module["status"]),
        str(module["timestamp"]),
    )


def _all_modules_url(start: int) -> str:
    base_url = f"{BASE_URL}/f_modulelist.php?cmd=resetall"
    if start <= 1:
        return base_url
    return f"{base_url}&start={start}"


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


def _validate_scrape_page(
    requested_start: int,
    pager_bounds: tuple[int, int, int] | None,
    page_modules: list[ModuleScrapeData],
) -> None:
    if pager_bounds is None:
        if requested_start != 1:
            raise ModuleScrapeIntegrityError(
                "Module pager disappeared before the scrape completed"
            )
        return

    first_record, last_record, total_records = pager_bounds
    if first_record != requested_start:
        raise ModuleScrapeIntegrityError(
            f"Module pager expected start {requested_start} but got {first_record}"
        )
    if last_record < first_record:
        raise ModuleScrapeIntegrityError(
            f"Module pager range is invalid: {first_record} to {last_record}"
        )
    if total_records < last_record:
        raise ModuleScrapeIntegrityError(
            f"Module pager total {total_records} is smaller than page end {last_record}"
        )

    expected_rows = last_record - first_record + 1
    if len(page_modules) != expected_rows:
        raise ModuleScrapeIntegrityError(
            f"Module page {requested_start} expected {expected_rows} rows but extracted {len(page_modules)}"
        )


def _merge_modules(
    modules_by_id: dict[int, ModuleScrapeData],
    page_modules: list[ModuleScrapeData],
) -> None:
    for module in page_modules:
        module_id = int(module["cms_id"])
        existing = modules_by_id.get(module_id)
        if existing is not None and _module_signature(existing) != _module_signature(
            module
        ):
            raise ModuleScrapeIntegrityError(
                f"Module {module_id} changed while scraping"
            )
        modules_by_id[module_id] = module


def _scrape_all_modules_once(
    browser: Browser,
    progress_callback: Callable[[str, int, int], None] | None,
    phase: str,
) -> list[ModuleScrapeData]:
    modules_by_id: dict[int, ModuleScrapeData] = {}
    visited_starts: set[int] = set()
    current_start = 1
    current_page = 0
    expected_total: int | None = None
    total_pages = 1

    while True:
        if current_start in visited_starts:
            raise ModuleScrapeIntegrityError(
                f"Module pager loop detected at record {current_start}"
            )

        visited_starts.add(current_start)
        response = browser.fetch(_all_modules_url(current_start))
        page = BeautifulSoup(response.text, "lxml")
        pager_bounds = _extract_pager_bounds(page)
        page_modules = _dedupe_modules(_extract_modules_from_page(page))
        _validate_scrape_page(current_start, pager_bounds, page_modules)
        _merge_modules(modules_by_id, page_modules)

        current_page += 1

        if pager_bounds is None:
            if progress_callback:
                progress_callback(
                    f"{phase} page 1/1 ({len(page_modules)} modules)",
                    1,
                    1,
                )
            break

        first_record, last_record, total_records = pager_bounds
        if expected_total is None:
            expected_total = total_records
            records_per_page = max(last_record - first_record + 1, 1)
            total_pages = max(
                (expected_total + records_per_page - 1) // records_per_page,
                1,
            )
        elif total_records != expected_total:
            raise ModuleScrapeIntegrityError(
                f"Module total changed from {expected_total} to {total_records} while scraping"
            )

        if progress_callback:
            progress_callback(
                f"{phase} page {current_page}/{total_pages} ({len(page_modules)} modules)",
                current_page,
                total_pages,
            )

        if last_record >= expected_total:
            break

        next_start = last_record + 1
        if next_start <= current_start:
            raise ModuleScrapeIntegrityError(
                f"Module pager did not advance after record {current_start}"
            )

        current_start = next_start

    all_modules = list(modules_by_id.values())

    if expected_total is not None and len(all_modules) != expected_total:
        raise ModuleScrapeIntegrityError(
            f"Expected {expected_total} unique modules but scraped {len(all_modules)}"
        )

    logger.info(f"Scraped total of {len(all_modules)} modules")
    return all_modules


def _module_snapshot(
    modules: list[ModuleScrapeData],
) -> set[tuple[int, str, str, str, str]]:
    return {_module_signature(module) for module in modules}


def scrape_all_modules(
    progress_callback: Callable[[str, int, int], None] | None = None,
    *,
    verify: bool = True,
    max_attempts: int = 2,
) -> list[ModuleScrapeData]:
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    browser = Browser()
    last_error: ModuleScrapeIntegrityError | None = None

    for attempt in range(1, max_attempts + 1):
        if progress_callback:
            if attempt == 1:
                progress_callback(
                    "Fetching first page to determine total records...",
                    0,
                    1,
                )
            else:
                progress_callback(
                    f"Retrying module scrape ({attempt}/{max_attempts})...",
                    0,
                    1,
                )

        try:
            modules = _scrape_all_modules_once(browser, progress_callback, "Scraping")

            if not modules:
                logger.warning("No modules found on the page")
                return []

            if not verify:
                return modules

            if progress_callback:
                progress_callback("Verifying module snapshot...", 0, 1)

            verified_modules = _scrape_all_modules_once(
                browser,
                progress_callback,
                "Verifying",
            )

            if _module_snapshot(modules) != _module_snapshot(verified_modules):
                raise ModuleScrapeIntegrityError(
                    "Module snapshot changed between scrape and verification"
                )

            return modules
        except ModuleScrapeIntegrityError as error:
            last_error = error
            logger.warning(
                f"Module scrape integrity failure on attempt {attempt}/{max_attempts}: {error}"
            )

    if last_error is not None:
        raise last_error

    raise ModuleScrapeIntegrityError("Module scrape failed")


def _extract_modules_from_page(page: BeautifulSoup) -> list[ModuleScrapeData]:
    return _extract_module_rows(page)
