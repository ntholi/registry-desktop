from __future__ import annotations

from typing import Callable

from base import get_logger

from .repository import TermRepository
from .scraper import scrape_all_terms

logger = get_logger(__name__)


class TermSyncService:
    def __init__(self, repository: TermRepository):
        self.repository = repository

    def fetch_and_save_all_terms(
        self, progress_callback: Callable[[str, int, int], None]
    ):
        def scraping_progress(message, current, total):
            progress_callback(f"[Scraping] {message}", current, total)

        terms = scrape_all_terms(progress_callback=scraping_progress)

        if not terms:
            raise ValueError("No terms found")

        total_terms = len(terms)
        saved_count = 0

        for idx, term in enumerate(terms, start=1):
            progress_callback(
                f"Saving term {idx}/{total_terms}: {term['code']}",
                idx,
                total_terms,
            )

            try:
                self.repository.save_term(
                    code=term["code"],
                    name=term.get("name"),
                    year=term.get("year"),
                    start_date=term.get("start_date"),
                    end_date=term.get("end_date"),
                    is_active=term.get("is_active", False),
                )
                saved_count += 1
            except Exception as e:
                logger.error(f"Error saving term {term['code']}: {e}")

        progress_callback(
            f"Successfully saved {saved_count}/{total_terms} terms",
            total_terms,
            total_terms,
        )

        return saved_count
