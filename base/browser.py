import os
import pickle
import time

import requests
import urllib3
from bs4 import BeautifulSoup, Tag
from requests import Response
from requests.adapters import HTTPAdapter
from selenium.webdriver.chrome.webdriver import WebDriver as ChromeWebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait
from urllib3.exceptions import InsecureRequestWarning
from urllib3.util.retry import Retry

from . import get_logger
from .runtime_config import get_current_cms_base_url, get_current_session_file

logger = get_logger(__name__)


class _BaseUrlProxy:
    def __str__(self) -> str:
        return get_current_cms_base_url()

    def __repr__(self) -> str:
        return str(self)

    def __format__(self, format_spec: str) -> str:
        return format(str(self), format_spec)

    def __eq__(self, other: object) -> bool:
        return str(self) == str(other)

    def __hash__(self) -> int:
        return hash(str(self))


BASE_URL = _BaseUrlProxy()

urllib3.disable_warnings(InsecureRequestWarning)


def get_form_payload(form: Tag):
    data = {}
    inputs = form.select("input")
    for tag in inputs:
        if tag.attrs["type"] == "hidden":
            data[tag.attrs["name"]] = tag.attrs["value"]
    return data


def check_logged_in(html: str) -> bool:
    page = BeautifulSoup(html, "lxml")
    form = page.select_one("form")
    if form:
        if form.attrs.get("action") == "login.php":
            return False
    return True


class Browser:
    _instance = None
    logged_in = False
    max_retries = 60
    session: requests.Session | None = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Browser, cls).__new__(cls)
            cls._instance.load_session()
        return cls._instance

    def load_session(self):
        session_file = get_current_session_file()
        if os.path.exists(session_file):
            with open(session_file, "rb") as f:
                self.session = pickle.load(f)
            logger.info("Loaded existing session")
        else:
            self.session = requests.Session()
            self.session.verify = False
            logger.info("Created new session")

        self._configure_session_pool()

    def _configure_session_pool(self):
        if self.session is None:
            return

        adapter = HTTPAdapter(
            pool_connections=20,
            pool_maxsize=80,
            max_retries=Retry(
                total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504]
            ),
        )

        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def save_session(self):
        with open(get_current_session_file(), "wb") as f:
            pickle.dump(self.session, f)
        logger.info("Saved session")

    def login(self):
        logger.info("Logging in...")
        driver = ChromeWebDriver()
        url = f"{BASE_URL}/login.php"
        logger.info(f"Fetching {url}")
        driver.get(url)
        WebDriverWait(driver, 60 * 3).until(
            expected_conditions.presence_of_element_located(
                (By.LINK_TEXT, "[ Logout ]")
            )
        )
        logger.info("Logged in successfully")

        selenium_cookies = driver.get_cookies()
        driver.quit()

        if self.session is None:
            raise ValueError("Session is not initialized")

        self.session.cookies.clear()
        for cookie in selenium_cookies:
            self.session.cookies.set(
                cookie["name"], cookie["value"], domain=cookie["domain"]
            )

        self.save_session()

    def fetch(self, url: str) -> Response:
        if self.session is None:
            raise ValueError("Session is not initialized")

        retry_count = 0
        wait_time = 3

        while retry_count < self.max_retries:
            try:
                attempt_info = (
                    f"(Attempt {retry_count + 1}/{self.max_retries})"
                    if retry_count > 0
                    else ""
                )
                logger.info(f"Fetching {url} {attempt_info}")
                response = self.session.get(url, timeout=120)

                is_logged_in = check_logged_in(response.text)
                if not is_logged_in:
                    logger.info("Session expired, logging in again")
                    self.login()
                    logger.info(f"Logged in, re-fetching {url}")
                    response = self.session.get(url, timeout=120)

                if response.status_code != 200:
                    logger.error(
                        f"Unexpected status code on fetch - url={url}, "
                        f"status_code={response.status_code}, "
                        f"response_length={len(response.text) if response and response.text else 0}, "
                        f"headers={dict(response.headers)}, "
                        f"retry_attempt={retry_count + 1}/{self.max_retries}"
                    )
                    retry_count += 1
                    if retry_count < self.max_retries:
                        logger.info(
                            f"Waiting {wait_time} seconds before retry ({retry_count}/{self.max_retries})"
                        )
                        time.sleep(wait_time)
                        wait_time *= 2
                        continue

                return response

            except (requests.RequestException, TimeoutError) as e:
                retry_count += 1
                if retry_count < self.max_retries:
                    logger.error(
                        f"Request failed - url={url}, error={str(e)}, "
                        f"error_type={type(e).__name__}, "
                        f"retry_attempt={retry_count}/{self.max_retries}, "
                        f"waiting {wait_time} seconds before retry",
                    )
                    time.sleep(wait_time)
                    wait_time *= 2
                else:
                    logger.error(
                        f"Request failed after all retries - url={url}, "
                        f"error={str(e)}, error_type={type(e).__name__}, "
                        f"total_attempts={self.max_retries}",
                    )
                    raise

        raise requests.RequestException(
            f"Failed to fetch {url} after {self.max_retries} attempts"
        )

    def post(self, url: str, data: dict | str) -> Response:
        if self.session is None:
            raise ValueError("Session is not initialized")
        logger.info(f"Posting to {url}")
        logger.info(f"Payload: {str(data)}")
        response = self.session.post(url, data, timeout=120)
        is_logged_in = check_logged_in(response.text)
        if not is_logged_in:
            logger.info("Not logged in, attempting to re-login...")
            self.login()
            logger.info(f"Logged in, re-posting to {url}")
            response = self.session.post(url, data, timeout=120)
        if response.status_code != 200:
            logger.error(
                f"Unexpected status code on post - url={url}, "
                f"status_code={response.status_code}, "
                f"response_length={len(response.text) if response and response.text else 0}, "
                f"headers={dict(response.headers)}, "
                f"payload_preview={str(data)[:200]}"
            )
        return response
