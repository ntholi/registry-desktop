from base import get_logger

from .repository import ModuleRepository
from .scraper import scrape_all_modules, scrape_modules

logger = get_logger(__name__)


class ModuleSyncService:
    def __init__(self, repository: ModuleRepository):
        self.repository = repository

    def fetch_and_save_modules(self, module_code: str, progress_callback=None):
        if progress_callback:
            progress_callback(
                f"Searching for modules matching '{module_code}'...", 1, 3
            )

        modules = scrape_modules(module_code)

        if not modules:
            raise ValueError(f"No modules found matching '{module_code}'")

        if progress_callback:
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

        if progress_callback:
            progress_callback(
                f"Successfully saved {saved_count} module(s) to database",
                3,
                3,
            )

        return saved_count

    def fetch_and_save_all_modules(self, progress_callback=None):
        def scraping_progress(message, current, total):
            if progress_callback:
                progress_callback(f"[Scraping] {message}", current, total)

        modules = scrape_all_modules(progress_callback=scraping_progress)

        if not modules:
            raise ValueError("No modules found")

        total_modules = len(modules)
        saved_count = 0

        for idx, module in enumerate(modules, start=1):
            if progress_callback:
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

        if progress_callback:
            progress_callback(
                f"Successfully saved {saved_count}/{total_modules} modules",
                total_modules,
                total_modules,
            )

        return saved_count
