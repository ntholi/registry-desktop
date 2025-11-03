from __future__ import annotations

from typing import Optional

from bs4 import BeautifulSoup

from base import get_logger
from base.browser import Browser, get_form_payload

logger = get_logger(__name__)


def format_module_enrollment_string(
    semester_module_id: int,
    module_status: str,
    credits: int,
    amount: int = 1200,
) -> str:
    return f"{semester_module_id}-{module_status}-{credits}-{amount}"


def fetch_cms_form(
    browser: Browser,
    url: str,
    form_selector: str,
) -> tuple[Optional[BeautifulSoup], Optional[dict]]:
    try:
        response = browser.fetch(url)
        page = BeautifulSoup(response.text, "lxml")
        form = page.select_one(form_selector)

        if not form:
            logger.error(
                f"Could not find form with selector '{form_selector}' at {url}"
            )
            return None, None

        return page, form
    except Exception as e:
        logger.error(f"Error fetching form from {url}: {str(e)}")
        return None, None


def post_cms_form(
    browser: Browser,
    url: str,
    form_data: dict,
) -> tuple[bool, str]:
    try:
        response = browser.post(url, form_data)

        if "Successful" in response.text:
            logger.info(f"CMS form post to {url} succeeded")
            return True, "Operation successful"
        else:
            logger.error(f"CMS form post to {url} failed - no 'Successful' in response")
            print(f"\n---------------- CMS Response from {url} ---------------")
            print("Payload sent:", form_data)
            print(f"\nFull HTML response:\n{response.text}")
            return False, "CMS update failed - response did not contain 'Successful'"
    except Exception as e:
        logger.error(f"Error posting form to {url}: {str(e)}")
        return False, f"Error: {str(e)}"


def verify_cms_success(response_text: str) -> bool:
    return "Successful" in response_text
