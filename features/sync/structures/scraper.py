import re
from collections.abc import Callable
from typing import Any, TypedDict, cast

from bs4 import BeautifulSoup

from base import get_logger
from base.browser import BASE_URL, Browser
from database.models import ProgramLevel
from utils.modules import extract_module_code_and_name

logger = get_logger(__name__)


class SchoolScrapeData(TypedDict):
    cms_id: int
    code: str
    name: str


class ProgramScrapeData(TypedDict):
    cms_id: int
    code: str
    name: str
    level: ProgramLevel


class StructureScrapeData(TypedDict):
    cms_id: int
    code: str
    desc: str


class SemesterScrapeData(TypedDict):
    cms_id: int
    semester_number: str
    name: str
    total_credits: float


class SemesterModuleScrapeData(TypedDict):
    cms_id: int
    module_code: str
    module_name: str
    type: str
    credits: float
    hidden: bool


class StructureScrapeIntegrityError(RuntimeError):
    pass


ScrapeProgressCallback = Callable[[str, int, int], None]
ScrapeRow = dict[str, Any]
ScrapeSignature = tuple[Any, ...]


def _extract_query_id(href: str, parameter: str) -> int | None:
    marker = f"{parameter}="
    if marker not in href:
        return None

    try:
        return int(href.split(marker)[1].split("&")[0])
    except (ValueError, IndexError):
        return None


def _normalize_program_level(category: str) -> ProgramLevel:
    normalized = category.strip().lower()
    if "short" in normalized and "course" in normalized:
        return "short_course"
    if normalized in {"certificate", "cert"}:
        return "certificate"
    if "cert" in normalized:
        return "certificate"
    if normalized in {"diploma", "dip"}:
        return "diploma"
    if "dip" in normalized:
        return "diploma"
    if normalized in {"degree", "deg"}:
        return "degree"
    if (
        "degree" in normalized
        or "bachelor" in normalized
        or "undergraduate" in normalized
    ):
        return "degree"

    logger.warning(
        f"Unknown program category '{category}', defaulting to 'short_course'"
    )
    return "short_course"


def _extract_pager_bounds(page: BeautifulSoup) -> tuple[int, int, int] | None:
    pager = page.select_one("form#ewpagerform")
    if not pager:
        return None

    text = pager.get_text(" ", strip=True)
    match = re.search(r"Records\s+(\d+)\s+to\s+(\d+)\s+of\s+(\d+)", text)
    if not match:
        return None

    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def _get_detail_value(page: BeautifulSoup, field_name: str) -> str | None:
    expected = field_name.strip().lower()

    for row in page.select("table.ewTable tr"):
        cells = row.select("td")
        if len(cells) < 2:
            continue

        label = cells[0].get_text(strip=True).rstrip(":").lower()
        if label != expected:
            continue

        value = cells[1].get_text(" ", strip=True)
        return value or None

    return None


def _dedupe_rows(rows: list[ScrapeRow]) -> list[ScrapeRow]:
    unique_rows: list[ScrapeRow] = []
    seen_ids: set[int] = set()

    for row in rows:
        row_id = int(row["cms_id"])
        if row_id in seen_ids:
            continue
        seen_ids.add(row_id)
        unique_rows.append(row)

    return unique_rows


def _snapshot_rows(
    rows: list[ScrapeRow],
    signature: Callable[[ScrapeRow], ScrapeSignature],
) -> set[ScrapeSignature]:
    return {signature(row) for row in rows}


def _validate_scrape_page(
    entity_name: str,
    requested_start: int,
    pager_bounds: tuple[int, int, int] | None,
    page_rows: list[ScrapeRow],
) -> None:
    if pager_bounds is None:
        if requested_start != 1:
            raise StructureScrapeIntegrityError(
                f"{entity_name.title()} pager disappeared before the scrape completed"
            )
        return

    first_record, last_record, total_records = pager_bounds
    if first_record != requested_start:
        raise StructureScrapeIntegrityError(
            f"{entity_name.title()} pager expected start {requested_start} but got {first_record}"
        )
    if last_record < first_record:
        raise StructureScrapeIntegrityError(
            f"{entity_name.title()} pager range is invalid: {first_record} to {last_record}"
        )
    if total_records < last_record:
        raise StructureScrapeIntegrityError(
            f"{entity_name.title()} pager total {total_records} is smaller than page end {last_record}"
        )

    expected_rows = last_record - first_record + 1
    if len(page_rows) != expected_rows:
        raise StructureScrapeIntegrityError(
            f"{entity_name.title()} page {requested_start} expected {expected_rows} rows but extracted {len(page_rows)}"
        )


def _merge_rows(
    entity_name: str,
    rows_by_id: dict[int, ScrapeRow],
    page_rows: list[ScrapeRow],
    signature: Callable[[ScrapeRow], ScrapeSignature],
) -> None:
    for row in page_rows:
        row_id = int(row["cms_id"])
        existing = rows_by_id.get(row_id)
        if existing is not None and signature(existing) != signature(row):
            raise StructureScrapeIntegrityError(
                f"{entity_name.title()} {row_id} changed while scraping"
            )
        rows_by_id[row_id] = row


def _paged_url(base_url: str, start: int) -> str:
    if start <= 1:
        return base_url
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}start={start}"


def _scrape_paginated_rows(
    browser: Browser,
    *,
    base_url: str,
    entity_name: str,
    extract_rows: Callable[[BeautifulSoup], list[ScrapeRow]],
    signature: Callable[[ScrapeRow], ScrapeSignature],
    phase: str,
    progress_callback: ScrapeProgressCallback | None = None,
) -> list[ScrapeRow]:
    rows_by_id: dict[int, ScrapeRow] = {}
    visited_starts: set[int] = set()
    current_start = 1
    current_page = 0
    expected_total: int | None = None
    total_pages = 1

    while True:
        if current_start in visited_starts:
            raise StructureScrapeIntegrityError(
                f"{entity_name.title()} pager loop detected at record {current_start}"
            )

        visited_starts.add(current_start)
        response = browser.fetch(_paged_url(base_url, current_start))
        page = BeautifulSoup(response.text, "lxml")
        pager_bounds = _extract_pager_bounds(page)
        page_rows = _dedupe_rows(extract_rows(page))

        _validate_scrape_page(entity_name, current_start, pager_bounds, page_rows)
        _merge_rows(entity_name, rows_by_id, page_rows, signature)

        current_page += 1

        if pager_bounds is None:
            if progress_callback:
                progress_callback(
                    f"{phase} {entity_name} page 1/1 ({len(page_rows)} rows)",
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
            raise StructureScrapeIntegrityError(
                f"{entity_name.title()} total changed from {expected_total} to {total_records} while scraping"
            )

        if progress_callback:
            progress_callback(
                f"{phase} {entity_name} page {current_page}/{total_pages} ({len(page_rows)} rows)",
                current_page,
                total_pages,
            )

        if last_record >= expected_total:
            break

        next_start = last_record + 1
        if next_start <= current_start:
            raise StructureScrapeIntegrityError(
                f"{entity_name.title()} pager did not advance after record {current_start}"
            )

        current_start = next_start

    rows = list(rows_by_id.values())
    if expected_total is not None and len(rows) != expected_total:
        raise StructureScrapeIntegrityError(
            f"Expected {expected_total} unique {entity_name} rows but scraped {len(rows)}"
        )

    logger.info(f"Scraped total of {len(rows)} {entity_name} row(s)")
    return rows


def _scrape_verified_rows(
    *,
    entity_name: str,
    runner: Callable[[str], list[ScrapeRow]],
    signature: Callable[[ScrapeRow], ScrapeSignature],
    progress_callback: ScrapeProgressCallback | None,
    verify: bool,
    max_attempts: int,
) -> list[ScrapeRow]:
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    last_error: StructureScrapeIntegrityError | None = None

    for attempt in range(1, max_attempts + 1):
        if progress_callback:
            if attempt == 1:
                progress_callback(
                    f"Fetching first {entity_name} page to determine total records...",
                    0,
                    1,
                )
            else:
                progress_callback(
                    f"Retrying {entity_name} scrape ({attempt}/{max_attempts})...",
                    0,
                    1,
                )

        try:
            rows = runner("Scraping")

            if not rows:
                logger.warning(f"No {entity_name} rows found on the page")
                return []

            if not verify:
                return rows

            if progress_callback:
                progress_callback(f"Verifying {entity_name} snapshot...", 0, 1)

            verified_rows = runner("Verifying")
            if _snapshot_rows(rows, signature) != _snapshot_rows(
                verified_rows,
                signature,
            ):
                raise StructureScrapeIntegrityError(
                    f"{entity_name.title()} snapshot changed between scrape and verification"
                )

            return rows
        except StructureScrapeIntegrityError as error:
            last_error = error
            logger.warning(
                f"{entity_name.title()} scrape integrity failure on attempt {attempt}/{max_attempts}: {error}"
            )

    if last_error is not None:
        raise last_error

    raise StructureScrapeIntegrityError(f"{entity_name.title()} scrape failed")


def _get_program_level(
    browser: Browser,
    program_id: int,
    level_cache: dict[int, ProgramLevel],
) -> ProgramLevel:
    cached_level = level_cache.get(program_id)
    if cached_level is not None:
        return cached_level

    url = f"{BASE_URL}/f_programview.php?ProgramID={program_id}"
    response = browser.fetch(url)
    page = BeautifulSoup(response.text, "lxml")

    for row in page.select("table.ewTable tr"):
        cells = row.select("td")
        if len(cells) < 2:
            continue

        label = cells[0].get_text(strip=True)
        if label.strip().lower() != "category":
            continue

        category = cells[1].get_text(strip=True)
        if not category:
            break

        level = _normalize_program_level(category)
        level_cache[program_id] = level
        return level

    logger.warning(
        f"Could not find Category on program view page, defaulting to 'degree' - program_id={program_id}"
    )
    level_cache[program_id] = "degree"
    return level_cache[program_id]


def _scrape_semester_module_identity(
    browser: Browser,
    sem_module_id: int,
    cache: dict[int, tuple[str | None, str | None]],
) -> tuple[str | None, str | None]:
    cached = cache.get(sem_module_id)
    if cached is not None:
        return cached

    url = f"{BASE_URL}/f_semmoduleview.php?SemModuleID={sem_module_id}"
    response = browser.fetch(url)
    page = BeautifulSoup(response.text, "lxml")
    module_text = _get_detail_value(page, "Module") or ""
    module_code, module_name = extract_module_code_and_name(module_text)

    if module_code and module_name is None:
        module_name = ""

    cache[sem_module_id] = (module_code, module_name)
    return cache[sem_module_id]


def _extract_schools_from_page(page: BeautifulSoup) -> list[ScrapeRow]:
    schools: list[ScrapeRow] = []
    rows = page.select("table#ewlistmain tr")

    for row in rows:
        cells = row.select("td")
        if len(cells) < 2:
            continue

        code = cells[0].get_text(strip=True)
        name = cells[1].get_text(strip=True)
        if not code or not name:
            continue

        view_link = row.select_one("a[href*='f_schoolview.php']")
        if not view_link or "href" not in view_link.attrs:
            continue

        school_id = _extract_query_id(str(view_link["href"]), "SchoolID")
        if school_id is None:
            continue

        schools.append({"cms_id": school_id, "code": code, "name": name})

    return schools


def _extract_programs_from_page(
    page: BeautifulSoup,
    browser: Browser,
    level_cache: dict[int, ProgramLevel],
) -> list[ScrapeRow]:
    programs: list[ScrapeRow] = []
    rows = page.select("table#ewlistmain tr")

    for row in rows:
        cells = row.select("td")
        if len(cells) < 3:
            continue

        code = cells[0].get_text(strip=True)
        name = cells[1].get_text(strip=True)
        if not code or not name:
            continue

        view_link = row.select_one("a[href*='f_programview.php']")
        if not view_link or "href" not in view_link.attrs:
            continue

        program_id = _extract_query_id(str(view_link["href"]), "ProgramID")
        if program_id is None:
            continue

        programs.append(
            {
                "cms_id": program_id,
                "code": code,
                "name": name,
                "level": _get_program_level(browser, program_id, level_cache),
            }
        )

    return programs


def _extract_structures_from_page(page: BeautifulSoup) -> list[ScrapeRow]:
    structures: list[ScrapeRow] = []
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
        if not view_link or "href" not in view_link.attrs:
            continue

        structure_id = _extract_query_id(str(view_link["href"]), "StructureID")
        if structure_id is None:
            continue

        structures.append(
            {
                "cms_id": structure_id,
                "code": structure_code,
                "desc": structure_desc,
            }
        )

    return structures


def _extract_semesters_from_page(page: BeautifulSoup) -> list[ScrapeRow]:
    semesters: list[ScrapeRow] = []
    rows = page.select("table#ewlistmain tr")

    for row in rows:
        cells = row.select("td")
        if not cells:
            continue

        semester_name = cells[0].get_text(strip=True)
        if not semester_name:
            continue

        credits = 0.0
        if len(cells) > 1:
            credits_text = cells[1].get_text(strip=True).replace(",", "")
            if credits_text and credits_text.replace(".", "", 1).isdigit():
                credits = float(credits_text)

        view_link = row.select_one("a[href*='f_semesterview.php']")
        if not view_link or "href" not in view_link.attrs:
            continue

        semester_id = _extract_query_id(str(view_link["href"]), "SemesterID")
        if semester_id is None:
            continue

        semester_number = semester_name.split()[0]
        name_parts = semester_name.split(maxsplit=1)
        clean_name = name_parts[1] if len(name_parts) > 1 else semester_name
        semesters.append(
            {
                "cms_id": semester_id,
                "semester_number": semester_number,
                "name": clean_name,
                "total_credits": credits,
            }
        )

    return semesters


def _extract_semester_modules_from_page(
    page: BeautifulSoup,
    browser: Browser,
    detail_cache: dict[int, tuple[str | None, str | None]],
) -> list[ScrapeRow]:
    semester_modules: list[ScrapeRow] = []
    rows = page.select("table#ewlistmain tr")

    for row in rows:
        cells = row.select("td")
        if len(cells) < 4:
            continue

        module_text = cells[0].get_text(strip=True)
        module_type = cells[1].get_text(strip=True)
        credits_text = cells[3].get_text(strip=True).replace(",", "")

        if not module_text or not module_type:
            continue

        view_link = row.select_one("a[href*='f_semmoduleview.php']")
        if not view_link or "href" not in view_link.attrs:
            continue

        sem_module_id = _extract_query_id(str(view_link["href"]), "SemModuleID")
        if sem_module_id is None:
            continue

        module_code, module_name = extract_module_code_and_name(module_text)
        if not module_code or module_name is None:
            detail_code, detail_name = _scrape_semester_module_identity(
                browser,
                sem_module_id,
                detail_cache,
            )
            if detail_code:
                module_code = detail_code
            if detail_name is not None:
                module_name = detail_name

        if not module_code:
            continue

        if module_name is None:
            module_name = ""

        try:
            credits = float(credits_text)
        except (TypeError, ValueError):
            continue

        semester_modules.append(
            {
                "cms_id": sem_module_id,
                "module_code": module_code,
                "module_name": module_name,
                "type": module_type,
                "credits": credits,
                "hidden": False,
            }
        )

    return semester_modules


def _school_signature(row: ScrapeRow) -> ScrapeSignature:
    return (int(row["cms_id"]), str(row["code"]), str(row["name"]))


def _program_signature(row: ScrapeRow) -> ScrapeSignature:
    return (
        int(row["cms_id"]),
        str(row["code"]),
        str(row["name"]),
        str(row["level"]),
    )


def _structure_signature(row: ScrapeRow) -> ScrapeSignature:
    return (int(row["cms_id"]), str(row["code"]), str(row["desc"]))


def _semester_signature(row: ScrapeRow) -> ScrapeSignature:
    return (
        int(row["cms_id"]),
        str(row["semester_number"]),
        str(row["name"]),
        float(row["total_credits"]),
    )


def _semester_module_signature(row: ScrapeRow) -> ScrapeSignature:
    return (
        int(row["cms_id"]),
        str(row["module_code"]),
        str(row["module_name"]),
        str(row["type"]),
        float(row["credits"]),
        bool(row["hidden"]),
    )


def scrape_structures(
    program_id: int,
    progress_callback: ScrapeProgressCallback | None = None,
    *,
    verify: bool = True,
    max_attempts: int = 2,
) -> list[StructureScrapeData]:
    browser = Browser()
    base_url = f"{BASE_URL}/f_structurelist.php?showmaster=1&ProgramID={program_id}"

    rows = _scrape_verified_rows(
        entity_name="structure",
        runner=lambda phase: _scrape_paginated_rows(
            browser,
            base_url=base_url,
            entity_name="structure",
            extract_rows=_extract_structures_from_page,
            signature=_structure_signature,
            phase=phase,
            progress_callback=progress_callback,
        ),
        signature=_structure_signature,
        progress_callback=progress_callback,
        verify=verify,
        max_attempts=max_attempts,
    )

    return cast(list[StructureScrapeData], rows)


def scrape_semesters(
    structure_id: int,
    progress_callback: ScrapeProgressCallback | None = None,
    *,
    verify: bool = True,
    max_attempts: int = 2,
) -> list[SemesterScrapeData]:
    browser = Browser()
    base_url = f"{BASE_URL}/f_semesterlist.php?showmaster=1&StructureID={structure_id}"

    rows = _scrape_verified_rows(
        entity_name="semester",
        runner=lambda phase: _scrape_paginated_rows(
            browser,
            base_url=base_url,
            entity_name="semester",
            extract_rows=_extract_semesters_from_page,
            signature=_semester_signature,
            phase=phase,
            progress_callback=progress_callback,
        ),
        signature=_semester_signature,
        progress_callback=progress_callback,
        verify=verify,
        max_attempts=max_attempts,
    )

    return cast(list[SemesterScrapeData], rows)


def scrape_semester_modules(
    semester_id: int,
    progress_callback: ScrapeProgressCallback | None = None,
    *,
    verify: bool = True,
    max_attempts: int = 2,
) -> list[SemesterModuleScrapeData]:
    browser = Browser()
    base_url = f"{BASE_URL}/f_semmodulelist.php?showmaster=1&SemesterID={semester_id}"

    def runner(phase: str) -> list[ScrapeRow]:
        detail_cache: dict[int, tuple[str | None, str | None]] = {}
        return _scrape_paginated_rows(
            browser,
            base_url=base_url,
            entity_name="semester module",
            extract_rows=lambda page: _extract_semester_modules_from_page(
                page,
                browser,
                detail_cache,
            ),
            signature=_semester_module_signature,
            phase=phase,
            progress_callback=progress_callback,
        )

    rows = _scrape_verified_rows(
        entity_name="semester module",
        runner=runner,
        signature=_semester_module_signature,
        progress_callback=progress_callback,
        verify=verify,
        max_attempts=max_attempts,
    )

    return cast(list[SemesterModuleScrapeData], rows)


def scrape_all_schools(
    progress_callback: ScrapeProgressCallback | None = None,
    *,
    verify: bool = True,
    max_attempts: int = 2,
) -> list[SchoolScrapeData]:
    browser = Browser()
    base_url = f"{BASE_URL}/f_schoollist.php?cmd=resetall"

    rows = _scrape_verified_rows(
        entity_name="school",
        runner=lambda phase: _scrape_paginated_rows(
            browser,
            base_url=base_url,
            entity_name="school",
            extract_rows=_extract_schools_from_page,
            signature=_school_signature,
            phase=phase,
            progress_callback=progress_callback,
        ),
        signature=_school_signature,
        progress_callback=progress_callback,
        verify=verify,
        max_attempts=max_attempts,
    )

    return cast(list[SchoolScrapeData], rows)


def scrape_school_details(school_code: str) -> SchoolScrapeData | None:
    schools = scrape_all_schools()
    for school in schools:
        if str(school["code"]).upper() == school_code.upper():
            return school
    return None


def scrape_school_id(school_code: str) -> int | None:
    schools = scrape_all_schools()
    for school in schools:
        if str(school["code"]).upper() == school_code.upper():
            return int(school["cms_id"])
    return None


def scrape_programs(
    school_id: int,
    progress_callback: ScrapeProgressCallback | None = None,
    *,
    verify: bool = True,
    max_attempts: int = 2,
) -> list[ProgramScrapeData]:
    browser = Browser()
    base_url = f"{BASE_URL}/f_programlist.php?showmaster=1&SchoolID={school_id}"

    def runner(phase: str) -> list[ScrapeRow]:
        level_cache: dict[int, ProgramLevel] = {}
        return _scrape_paginated_rows(
            browser,
            base_url=base_url,
            entity_name="program",
            extract_rows=lambda page: _extract_programs_from_page(
                page,
                browser,
                level_cache,
            ),
            signature=_program_signature,
            phase=phase,
            progress_callback=progress_callback,
        )

    rows = _scrape_verified_rows(
        entity_name="program",
        runner=runner,
        signature=_program_signature,
        progress_callback=progress_callback,
        verify=verify,
        max_attempts=max_attempts,
    )

    return cast(list[ProgramScrapeData], rows)
