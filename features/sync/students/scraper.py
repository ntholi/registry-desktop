from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Optional

from bs4 import BeautifulSoup, Tag

from base import get_logger
from base.browser import BASE_URL, Browser

logger = get_logger(__name__)


def extract_student_program_ids(std_no: str) -> list[str]:
    browser = Browser()
    url = f"{BASE_URL}/r_stdprogramlist.php?showmaster=1&StudentID={std_no}"
    response = browser.fetch(url)

    page = BeautifulSoup(response.text, "lxml")
    table = page.select_one("table#ewlistmain")

    if not table:
        logger.warning(f"No program table found for student {std_no}")
        return []

    program_ids = []
    rows = table.select("tr.ewTableRow, tr.ewTableAltRow")

    for row in rows:
        view_link = row.select_one("a[href*='r_stdprogramview.php?StdProgramID=']")
        if view_link:
            href = view_link.get("href")
            if href and isinstance(href, str) and "StdProgramID=" in href:
                program_id = href.split("StdProgramID=")[1].split("&")[0]
                program_ids.append(program_id)

    logger.info(f"Found {len(program_ids)} programs for student {std_no}")
    return program_ids


def scrape_student_program_data(std_program_id: str) -> dict:
    browser = Browser()
    url = f"{BASE_URL}/r_stdprogramview.php?StdProgramID={std_program_id}"
    response = browser.fetch(url)

    page = BeautifulSoup(response.text, "lxml")
    table = page.select_one("table.ewTable")

    if not table:
        logger.error(f"No data table found for student program {std_program_id}")
        return {}

    data = {}

    student_id_str = get_table_value(table, "StudentID")
    if student_id_str:
        student_id_parts = student_id_str.split()
        if student_id_parts:
            try:
                data["std_no"] = int(student_id_parts[0])
            except ValueError:
                logger.warning(f"Could not parse student ID from: {student_id_str}")

    program_str = get_table_value(table, "Program")
    if program_str:
        program_parts = program_str.split(maxsplit=1)
        if program_parts:
            data["program_code"] = program_parts[0]

    reg_date_str = get_table_value(table, "RegDate")
    if reg_date_str:
        parsed_date = parse_date(reg_date_str)
        if parsed_date:
            data["reg_date"] = parsed_date.strftime("%Y-%m-%d")

    intake_date_str = get_table_value(table, "Intake Date")
    if intake_date_str:
        parsed_date = parse_date(intake_date_str)
        if parsed_date:
            data["intake_date"] = parsed_date.strftime("%Y-%m-%d")

    start_term = get_table_value(table, "StartTerm")
    if start_term:
        data["start_term"] = start_term

    structure = get_table_value(table, "Version")
    if structure:
        data["structure_code"] = structure

    stream = get_table_value(table, "Stream")
    if stream:
        data["stream"] = stream

    status = get_table_value(table, "Status")
    if status:
        data["status"] = status

    assist_provider = get_table_value(table, "Asst-Provider")
    if assist_provider:
        data["assist_provider"] = assist_provider

    grad_date_str = get_table_value(table, "Graduation Date")
    if grad_date_str:
        parsed_date = parse_date(grad_date_str)
        if parsed_date:
            data["graduation_date"] = parsed_date.strftime("%Y-%m-%d")

    logger.info(f"Scraped program data for student program {std_program_id}")
    return data


def parse_date(date_str: Optional[str]) -> Optional[datetime]:
    if not date_str or not date_str.strip():
        return None
    try:
        return datetime.strptime(date_str.strip(), "%Y-%m-%d")
    except ValueError:
        return None


def parse_semester_number(semester_str: str) -> Optional[int]:
    if not semester_str or not semester_str.strip():
        return None

    semester_str = semester_str.strip()
    parts = semester_str.split()

    if parts:
        try:
            return int(parts[0])
        except ValueError:
            return None

    return None


def get_table_value(table: Tag, header_text: str) -> Optional[str]:
    rows = table.select("tr")
    for row in rows:
        header = row.select_one("td.ewTableHeader")
        if header:
            header_span = header.select_one("span")
            if header_span and header_text in header_span.get_text(strip=True):
                value_cell = row.select_one("td.ewTableAltRow")
                if value_cell:
                    value_span = value_cell.select_one("span")
                    if value_span:
                        return value_span.get_text(strip=True)
    return None


def scrape_student_personal_view(std_no: str) -> dict:
    browser = Browser()
    url = f"{BASE_URL}/r_stdpersonalview.php?StudentID={std_no}"
    response = browser.fetch(url)

    page = BeautifulSoup(response.text, "lxml")
    table = page.select_one("table.ewTable")

    if not table:
        logger.error(f"No data table found for student {std_no} on personal view page")
        return {}

    data = {}

    birthdate_str = get_table_value(table, "Birthdate")
    if birthdate_str:
        data["date_of_birth"] = parse_date(birthdate_str)

    sex = get_table_value(table, "Sex")
    if sex:
        data["gender"] = sex

    marital = get_table_value(table, "Marital")
    if marital:
        data["marital_status"] = marital

    religion = get_table_value(table, "Religion")
    if religion:
        data["religion"] = religion

    logger.info(f"Scraped personal data for student {std_no}")
    return data


def scrape_student_view(std_no: str) -> dict:
    browser = Browser()
    url = f"{BASE_URL}/r_studentview.php?StudentID={std_no}"
    response = browser.fetch(url)

    page = BeautifulSoup(response.text, "lxml")
    table = page.select_one("table.ewTable")

    if not table:
        logger.error(f"No data table found for student {std_no} on student view page")
        return {}

    data = {}

    name = get_table_value(table, "Name")
    if name:
        data["name"] = name

    ic_passport = get_table_value(table, "IC/Passport")
    if ic_passport:
        data["national_id"] = ic_passport

    sem = get_table_value(table, "Sem")
    if sem:
        try:
            data["sem"] = int(sem)
        except ValueError:
            pass

    house_phone = get_table_value(table, "House Phone No")
    if house_phone:
        data["phone1"] = house_phone

    current_mobile = get_table_value(table, "Current Mobile")
    if current_mobile:
        data["phone2"] = current_mobile

    logger.info(f"Scraped student data for {std_no}")
    return data


def extract_student_semester_ids(std_program_id: str) -> list[str]:
    browser = Browser()
    url = f"{BASE_URL}/r_stdsemesterlist.php?showmaster=1&StdProgramID={std_program_id}"
    response = browser.fetch(url)

    page = BeautifulSoup(response.text, "lxml")
    table = page.select_one("table#ewlistmain")

    if not table:
        logger.warning(f"No semester table found for student program {std_program_id}")
        return []

    semester_ids = []
    rows = table.select("tr.ewTableRow, tr.ewTableAltRow")

    for row in rows:
        view_link = row.select_one("a[href*='r_stdsemesterview.php?StdSemesterID=']")
        if view_link:
            href = view_link.get("href")
            if href and isinstance(href, str) and "StdSemesterID=" in href:
                semester_id = href.split("StdSemesterID=")[1].split("&")[0]
                semester_ids.append(semester_id)

    logger.info(
        f"Found {len(semester_ids)} semesters for student program {std_program_id}"
    )
    return semester_ids


def scrape_student_semester_data(std_semester_id: str) -> dict:
    browser = Browser()
    url = f"{BASE_URL}/r_stdsemesterview.php?StdSemesterID={std_semester_id}"
    response = browser.fetch(url)

    page = BeautifulSoup(response.text, "lxml")
    table = page.select_one("table.ewTable")

    if not table:
        logger.error(f"No data table found for student semester {std_semester_id}")
        return {}

    data: dict = {"id": std_semester_id}

    term = get_table_value(table, "Term")
    if term:
        data["term"] = term

    semester_str = get_table_value(table, "Semester")
    if semester_str:
        semester_number = parse_semester_number(semester_str)
        if semester_number is not None:
            data["semester_number"] = semester_number

    status = get_table_value(table, "SemStatus")
    if status:
        data["semester_status"] = status

    caf_date_str = get_table_value(table, "CAF Date")
    if caf_date_str:
        parsed_date = parse_date(caf_date_str)
        if parsed_date:
            data["caf_date"] = parsed_date.strftime("%Y-%m-%d")

    logger.info(f"Scraped semester data for student semester {std_semester_id}")
    return data


def scrape_student_data(std_no: str) -> dict:
    logger.info(f"Scraping data for student {std_no}")

    personal_data = scrape_student_personal_view(std_no)
    student_data = scrape_student_view(std_no)

    merged_data = {**personal_data, **student_data}

    logger.info(
        f"Completed scraping for student {std_no}. Found {len(merged_data)} fields"
    )
    return merged_data


def extract_student_module_ids(std_semester_id: str) -> list[str]:
    browser = Browser()
    url = f"{BASE_URL}/r_stdmodulelist.php?showmaster=1&StdSemesterID={std_semester_id}"
    response = browser.fetch(url)

    page = BeautifulSoup(response.text, "lxml")
    table = page.select_one("table#ewlistmain")

    if not table:
        logger.warning(f"No module table found for student semester {std_semester_id}")
        return []

    module_ids = []
    rows = table.select("tr.ewTableRow, tr.ewTableAltRow")

    for row in rows:
        view_link = row.select_one("a[href*='r_stdmoduleview.php?StdModuleID=']")
        if view_link:
            href = view_link.get("href")
            if href and isinstance(href, str) and "StdModuleID=" in href:
                module_id = href.split("StdModuleID=")[1].split("&")[0]
                module_ids.append(module_id)

    logger.info(
        f"Found {len(module_ids)} modules for student semester {std_semester_id}"
    )
    return module_ids


def scrape_student_module_data(std_module_id: str, student_semester_id: int) -> dict:
    browser = Browser()
    url = f"{BASE_URL}/r_stdmoduleview.php?StdModuleID={std_module_id}"
    response = browser.fetch(url)

    page = BeautifulSoup(response.text, "lxml")
    table = page.select_one("table.ewTable")

    if not table:
        logger.error(f"No data table found for student module {std_module_id}")
        return {}

    data = {"id": std_module_id, "student_semester_id": student_semester_id}

    module_str = get_table_value(table, "Module")
    if module_str:
        parts = module_str.split(maxsplit=1)
        if parts:
            data["module_code"] = parts[0]
            if len(parts) > 1:
                data["module_name"] = parts[1]

    module_status = get_table_value(table, "ModuleStatus")
    if module_status:
        data["status"] = module_status

    module_type = get_table_value(table, "Type")
    if module_type:
        data["type"] = module_type

    credits_str = get_table_value(table, "Credits")
    if credits_str:
        try:
            data["credits"] = float(credits_str)
        except ValueError:
            pass

    marks = get_table_value(table, "Marks")
    alter_mark = get_table_value(table, "[Reg] Alter Mark")
    if alter_mark:
        data["marks"] = alter_mark
    elif marks:
        data["marks"] = marks

    grade = get_table_value(table, "Grade")
    alter_grade = get_table_value(table, "[Reg] Alter Grade")
    if alter_grade:
        data["grade"] = alter_grade
    elif grade:
        data["grade"] = grade

    logger.info(f"Scraped module data for student module {std_module_id}")
    return data


def scrape_student_modules_concurrent(
    std_semester_id: str, db_semester_id: int, max_workers: int = 10
) -> list[dict]:
    logger.info(
        f"Starting concurrent module scraping for semester {std_semester_id} with {max_workers} workers"
    )

    module_ids = extract_student_module_ids(std_semester_id)

    if not module_ids:
        logger.info(f"No modules to scrape for semester {std_semester_id}")
        return []

    modules_data = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_module_id = {
            executor.submit(
                scrape_student_module_data, module_id, db_semester_id
            ): module_id
            for module_id in module_ids
        }

        for future in as_completed(future_to_module_id):
            module_id = future_to_module_id[future]
            try:
                data = future.result()
                if data:
                    modules_data.append(data)
                    logger.debug(f"Successfully scraped module {module_id}")
            except Exception as e:
                logger.error(f"Error scraping module {module_id}: {str(e)}")

    logger.info(
        f"Completed concurrent scraping for semester {std_semester_id}: "
        f"{len(modules_data)}/{len(module_ids)} modules scraped successfully"
    )
    return modules_data
