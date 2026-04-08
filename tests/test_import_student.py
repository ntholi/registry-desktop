import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.engine.url import make_url

from base.runtime_config import (
    get_current_cms_base_url,
    get_current_country_code,
    get_current_country_label,
    has_complete_runtime_configuration,
)
from database.connection import configure_database_urls_for_country, get_database_url
from features.sync.students.repository import StudentRepository
from features.sync.students.service import StudentSyncService


def progress_callback(message: str, current: int, total: int):
    print(f"  [{current}/{total}] {message}")


def load_saved_runtime_configuration() -> None:
    if not has_complete_runtime_configuration():
        raise RuntimeError(
            "Saved runtime configuration is missing. Run main.py and save the country and database connection first."
        )

    country_code = get_current_country_code()
    if not country_code:
        raise RuntimeError(
            "Saved runtime configuration does not include a country. Run main.py and save it again."
        )

    configure_database_urls_for_country(country_code)

    masked_database_url = make_url(get_database_url()).render_as_string(
        hide_password=True
    )
    print(f"Using saved country: {get_current_country_label()} ({country_code})")
    print(f"Using saved CMS: {get_current_cms_base_url()}")
    print(f"Using saved database: {masked_database_url}")


def run_import(student_numbers: list[str]):
    load_saved_runtime_configuration()
    repository = StudentRepository()
    service = StudentSyncService(repository)

    import_options = {
        "student_info": True,
        "personal_info": True,
        "education_history": True,
        "enrollment_data": True,
        "addresses": True,
        "skip_active_term": False,
        "delete_programs_before_import": False,
    }

    for std_no in student_numbers:
        print(f"\n{'='*60}")
        print(f"Importing student: {std_no}")
        print(f"{'='*60}")
        try:
            was_updated = service.fetch_student(
                std_no,
                progress_callback,
                import_options,
                None,
            )
            if was_updated:
                print(f"SUCCESS: Student {std_no} imported")
            else:
                print(f"FAILED: Student {std_no} was not updated")
        except Exception as e:
            print(f"ERROR: Student {std_no} - {e}")

    print(f"\n{'='*60}")
    print("Import complete")
    print(f"{'='*60}")


if __name__ == "__main__":
    students = sys.argv[1:] if len(sys.argv) > 1 else ["901000002"]
    run_import(students)
