from datetime import datetime
from typing import Optional

from bs4 import BeautifulSoup, Tag

from base import get_logger
from base.browser import BASE_URL, Browser

logger = get_logger(__name__)


def parse_date(date_str: Optional[str]) -> Optional[datetime]:
    if not date_str or not date_str.strip():
        return None
    try:
        return datetime.strptime(date_str.strip(), "%Y-%m-%d")
    except ValueError:
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


def scrape_student_data(std_no: str) -> dict:
    logger.info(f"Scraping data for student {std_no}")

    personal_data = scrape_student_personal_view(std_no)
    student_data = scrape_student_view(std_no)

    merged_data = {**personal_data, **student_data}

    logger.info(
        f"Completed scraping for student {std_no}. Found {len(merged_data)} fields"
    )
    return merged_data
