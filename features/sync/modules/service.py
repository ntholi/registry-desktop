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

            if "remark" in data and data["remark"]:
                form_data["x_ModuleRemark"] = data["remark"]

            progress_callback(f"Pushing module {module_id} to CMS...")

            cms_success, cms_message = post_cms_form(self._browser, url, form_data)

            if cms_success:
                progress_callback(f"Saving module {module_id} to database...")

                self.repository.save_module(
                    module_id=module_id,
                    code=data.get("code", ""),
                    name=data.get("name", ""),
                    status=data.get("status", ""),
                    remark=data.get("remark"),
                    timestamp=data.get("date_stamp"),
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

    def create_module(
        self,
        data: dict,
        progress_callback: Callable[[str], None],
    ) -> tuple[bool, str]:
        url = f"{BASE_URL}/f_moduleadd.php"

        try:
            progress_callback("Fetching module add form...")

            response = self._browser.fetch(url)
            page = BeautifulSoup(response.text, "lxml")
            form = page.select_one("form#ff_moduleadd")

            if not form:
                logger.error(
                    f"Could not find add form - url={url}, response_length={len(response.text) if response and response.text else 0}"
                )
                return False, "Could not find add form"

            progress_callback("Preparing module data...")

            form_data = get_form_payload(form)
            form_data["a_add"] = "A"

            code = (data.get("code") or "").strip()
            name = (data.get("name") or "").strip()
            remark = data.get("remark")
            date_stamp = data.get("date_stamp")
            status = (data.get("status") or "Active").strip() or "Active"

            if code:
                form_data["x_ModuleCode"] = code
            if name:
                form_data["x_ModuleName"] = name
            if status:
                form_data["x_ModuleStatCode"] = status
            if remark:
                form_data["x_ModuleRemark"] = remark
            if date_stamp:
                form_data["x_DateStamp"] = date_stamp

            progress_callback("Creating module in CMS...")
            cms_success, cms_message = post_cms_form(self._browser, url, form_data)

            if not cms_success:
                return False, cms_message

            progress_callback("Fetching created module to get ModuleID...")

            created = scrape_modules(code)
            if not created:
                return False, "Module created in CMS but could not be found by search"

            created_module = None
            for candidate in created:
                candidate_code = str(candidate.get("code", "")).strip().lower()
                if candidate_code == code.lower():
                    created_module = candidate
                    break

            if created_module is None:
                created_module = created[0]

            progress_callback("Saving module to database...")
            self.repository.save_module(
                module_id=int(created_module["id"]),
                code=created_module.get("code", code),
                name=created_module.get("name", name),
                status=created_module.get("status", "Active"),
                remark=remark,
                timestamp=created_module.get("timestamp") or date_stamp,
            )

            return True, "Module created successfully"

        except Exception as e:
            logger.error(f"Error creating module - data={data}, error={str(e)}")
            return False, f"Error: {str(e)}"

