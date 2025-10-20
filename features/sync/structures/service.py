from base import get_logger

from .repository import StructureRepository
from .scraper import scrape_programs, scrape_school_id

logger = get_logger(__name__)


class SchoolSyncService:
    def __init__(self, repository: StructureRepository):
        self.repository = repository

    def import_school(self, school_code: str, progress_callback=None):
        if progress_callback:
            progress_callback(f"Searching for school '{school_code}'...", 1, 3)

        school_id = scrape_school_id(school_code)
        if not school_id:
            raise ValueError(f"School with code '{school_code}' not found")

        if progress_callback:
            progress_callback(
                f"Found school {school_code} (ID: {school_id}). Fetching programs...",
                2,
                3,
            )

        programs = scrape_programs(school_id)

        if progress_callback:
            progress_callback(
                f"Retrieved {len(programs)} program(s) for {school_code}", 3, 3
            )

        return school_id, programs
