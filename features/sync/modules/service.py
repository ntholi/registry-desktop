from __future__ import annotations

from typing import Callable

from bs4 import BeautifulSoup

from base import get_logger
from base.browser import BASE_URL, Browser, get_form_payload
from features.common.cms_utils import post_cms_form

from .repository import ModuleRepository
from .scraper import scrape_all_modules, scrape_modules

logger = get_logger(__name__)


class ModuleSyncService:
    def __init__(self, repository: ModuleRepository):
        self.repository = repository
        self._browser = Browser()

    def fetch_and_save_modules(
        self, module_code: str, progress_callback: Callable[[str, int, int], None]
    ):
        progress_callback(f"Searching for modules matching '{module_code}'...", 1, 3)

        modules = scrape_modules(module_code)

        if not modules:
            raise ValueError(f"No modules found matching '{module_code}'")

        progress_callback(
            f"Found {len(modules)} module(s). Saving to database...",
            2,
            3,
        )

        saved_count = 0
        for module in modules:
            try:
                self.repository.save_module(
                    module_id=int(module["id"]),
                    code=module["code"],
                    name=module["name"],
                    status=module["status"],
                    timestamp=module["timestamp"],
                )
                saved_count += 1
            except Exception as e:
                logger.error(f"Error saving module {module['code']}: {e}")

        progress_callback(
            f"Successfully saved {saved_count} module(s) to database",
            3,
            3,
        )

        return saved_count

    def fetch_and_save_all_modules(
        self, progress_callback: Callable[[str, int, int], None]
    ):
        def scraping_progress(message, current, total):
            progress_callback(f"[Scraping] {message}", current, total)

        modules = scrape_all_modules(progress_callback=scraping_progress)

        if not modules:
            raise ValueError("No modules found")

        total_modules = len(modules)
        saved_count = 0

        for idx, module in enumerate(modules, start=1):
            progress_callback(
                f"Saving module {idx}/{total_modules}: {module['code']}",
                idx,
                total_modules,
            )

            try:
                self.repository.save_module(
                    module_id=int(module["id"]),
                    code=module["code"],
                    name=module["name"],
                    status=module["status"],
                    timestamp=module["timestamp"],
                )
                saved_count += 1
            except Exception as e:
                logger.error(f"Error saving module {module['code']}: {e}")

        progress_callback(
            f"Successfully saved {saved_count}/{total_modules} modules",
            total_modules,
            total_modules,
        )

        return saved_count

    def push_module(
        self,
        module_id: int,
        data: dict,
        progress_callback: Callable[[str], None],
    ) -> tuple[bool, str]:
        url = f"{BASE_URL}/f_moduleedit.php?ModuleID={module_id}"

        try:
            progress_callback(f"Fetching edit form for module {module_id}...")

            response = self._browser.fetch(url)
            page = BeautifulSoup(response.text, "lxml")
            form = page.select_one("form#ff_moduleedit")

            if not form:
                logger.error(
                    f"Could not find edit form - module_id={module_id}, "
                    f"url={url}, response_length={len(response.text) if response and response.text else 0}"
                )
                return False, "Could not find edit form"

            progress_callback(f"Preparing data for module {module_id}...")

            form_data = get_form_payload(form)

            form_data["a_edit"] = "U"

            if "code" in data and data["code"]:
                form_data["x_ModuleCode"] = data["code"]

            if "name" in data and data["name"]:
                form_data["x_ModuleName"] = data["name"]

            if "status" in data and data["status"]:
                form_data["x_ModuleStatCode"] = data["status"]

            if "date_stamp" in data and data["date_stamp"]:
                form_data["x_DateStamp"] = data["date_stamp"]

            progress_callback(f"Pushing module {module_id} to CMS...")

            cms_success, cms_message = post_cms_form(self._browser, url, form_data)

            if cms_success:
                progress_callback(f"Saving module {module_id} to database...")

                self.repository.save_module(
                    module_id=module_id,
                    code=data.get("code", ""),
                    name=data.get("name", ""),
                    status=data.get("status", ""),
                    timestamp=None,
                )
                return True, "Module updated successfully"
            else:
                return False, cms_message

        except Exception as e:
            logger.error(
                f"Error pushing module - module_id={module_id}, "
                f"url={url}, data={data}, error={str(e)}",
            )
            return False, f"Error: {str(e)}"

