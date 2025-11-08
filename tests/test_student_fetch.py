from base import get_logger
from features.sync.students.service import StudentSyncService

logger = get_logger(__name__)


def progress_callback(message: str, current: int, total: int):
    logger.info(f"Progress ({current}/{total}): {message}")


def main():
    student_number = "901000022"
    service = StudentSyncService()

    logger.info(f"Starting fetch for student {student_number}")

    try:
        success = service.fetch_student(
            student_number,
            progress_callback=progress_callback,
            import_options={
                "student_info": True,
                "personal_info": True,
                "education_history": True,
                "enrollment_data": True,
            },
        )

        if success:
            logger.info(f"Successfully fetched student {student_number}")
        else:
            logger.warning(f"Fetch completed with issues for student {student_number}")

    except Exception as e:
        logger.error(f"Error fetching student {student_number}: {str(e)}")


if __name__ == "__main__":
    main()
