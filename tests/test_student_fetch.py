import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from features.sync.students.service import StudentSyncService


def progress_callback(message: str, current: int, total: int):
    print(f"Progress ({current}/{total}): {message}")


def main():
    student_number = "901007412"
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


if __name__ == "__main__":
    main()
