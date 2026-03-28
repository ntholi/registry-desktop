import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from features.sync.students.repository import StudentRepository
from features.sync.students.service import StudentSyncService


def progress_callback(message: str, current: int, total: int):
    print(f"  [{current}/{total}] {message}")


def run_import(student_numbers: list[str]):
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
