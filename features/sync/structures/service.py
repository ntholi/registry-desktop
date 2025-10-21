from base import get_logger

from .repository import StructureRepository
from .scraper import scrape_programs, scrape_school_details

logger = get_logger(__name__)


class SchoolSyncService:
    def __init__(self, repository: StructureRepository):
        self.repository = repository

    def import_school(self, school_code: str, progress_callback=None):
        if progress_callback:
            progress_callback(f"Searching for school '{school_code}'...", 1, 4)

        school_data = scrape_school_details(school_code)
        if not school_data:
            raise ValueError(f"School with code '{school_code}' not found")

        school_id = int(school_data["id"])
        school_name = str(school_data["name"])
        school_code = str(school_data["code"])

        if progress_callback:
            progress_callback(
                f"Found school {school_code} (ID: {school_id}). Fetching programs...",
                2,
                4,
            )

        programs = scrape_programs(school_id)

        if progress_callback:
            progress_callback(
                f"Retrieved {len(programs)} program(s). Saving to database...", 3, 4
            )

        self.repository.save_school(school_id, school_code, school_name)

        for program in programs:
            self.repository.save_program(
                int(program["id"]),
                program["code"],
                program["name"],
                school_id,
            )

        if progress_callback:
            progress_callback(
                f"Successfully saved {school_code} and {len(programs)} program(s)", 4, 4
            )

        return school_id, programs
