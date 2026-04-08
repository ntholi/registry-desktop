import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.engine.url import make_url

from base.runtime_config import (
    get_current_cms_base_url,
    get_current_country_code,
    get_current_country_label,
    has_complete_runtime_configuration,
)
from database.connection import configure_database_urls_for_country, get_database_url
from features.sync.students.service import StudentSyncService


def progress_callback(message: str, current: int, total: int):
    print(f"Progress ({current}/{total}): {message}")


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


def main():
    student_number = "901007412"
    load_saved_runtime_configuration()
    service = StudentSyncService()

    try:
        service.fetch_student(
            student_number,
            progress_callback=progress_callback,
            import_options={
                "student_info": True,
                "personal_info": True,
                "education_history": True,
                "enrollment_data": True,
            },
        )

    except Exception as e:
        print(f"Error fetching student {student_number}: {str(e)}")
        raise


if __name__ == "__main__":
    main()
