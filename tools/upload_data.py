import argparse
import sys
from collections.abc import Callable
from dataclasses import dataclass, field

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

sys.path.insert(0, ".")

from base import get_logger
from database.models import NextOfKin, Student, StudentEducation

logger = get_logger(__name__)

STUDENT_FILLABLE_FIELDS = [
    "national_id",
    "date_of_birth",
    "phone1",
    "phone2",
    "gender",
    "marital_status",
    "country",
    "race",
    "nationality",
    "birth_place",
    "religion",
]


@dataclass
class MergeStats:
    students_added: int = 0
    students_updated: int = 0
    students_skipped: int = 0
    students_fields_filled: dict[str, int] = field(default_factory=dict)
    education_added: int = 0
    education_skipped: int = 0
    kins_added: int = 0
    kins_skipped: int = 0

    def summary(self) -> str:
        lines = [
            "=== Merge Summary ===",
            f"Students: {self.students_added} added, {self.students_updated} updated, {self.students_skipped} skipped",
        ]
        if self.students_fields_filled:
            lines.append("  Fields filled:")
            for fname, count in sorted(
                self.students_fields_filled.items(), key=lambda x: -x[1]
            ):
                lines.append(f"    {fname}: {count}")
        lines.append(
            f"Education: {self.education_added} added, {self.education_skipped} skipped"
        )
        lines.append(
            f"Next of Kin: {self.kins_added} added, {self.kins_skipped} skipped"
        )
        return "\n".join(lines)


@dataclass
class Conflict:
    std_no: int
    student_name: str
    field_name: str
    target_value: str
    source_value: str


@dataclass
class AnalysisResult:
    students_to_add: int = 0
    students_to_update: int = 0
    fields_to_fill: dict[str, int] = field(default_factory=dict)
    education_to_add: int = 0
    kins_to_add: int = 0
    conflicts: list[Conflict] = field(default_factory=list)


def analyze_differences(
    source_engine: Engine,
    target_engine: Engine,
) -> AnalysisResult:
    result = AnalysisResult()

    with Session(source_engine) as src, Session(target_engine) as tgt:
        src_students = {s.std_no: s for s in src.query(Student).all()}
        tgt_students = {s.std_no: s for s in tgt.query(Student).all()}

        for std_no, src_s in src_students.items():
            tgt_s = tgt_students.get(std_no)
            if tgt_s is None:
                result.students_to_add += 1
                continue

            has_fill = False
            for fname in STUDENT_FILLABLE_FIELDS:
                src_val = _effective_value(getattr(src_s, fname))
                tgt_val = getattr(tgt_s, fname)
                if tgt_val is None and src_val is not None:
                    result.fields_to_fill[fname] = (
                        result.fields_to_fill.get(fname, 0) + 1
                    )
                    has_fill = True
                elif (
                    tgt_val is not None
                    and src_val is not None
                    and str(tgt_val).strip() != str(src_val).strip()
                ):
                    result.conflicts.append(
                        Conflict(
                            std_no=std_no,
                            student_name=tgt_s.name,
                            field_name=fname,
                            target_value=str(tgt_val),
                            source_value=str(src_val),
                        )
                    )

            if has_fill:
                result.students_to_update += 1

        tgt_student_ids = set(tgt_students.keys()) | {
            s for s in src_students if s not in tgt_students
        }
        tgt_edu_cms_ids = {
            row[0]
            for row in tgt.query(StudentEducation.cms_id)
            .filter(StudentEducation.cms_id.isnot(None))
            .all()
        }
        for edu in src.query(StudentEducation).all():
            if edu.std_no in tgt_student_ids:
                if edu.cms_id is None or edu.cms_id not in tgt_edu_cms_ids:
                    result.education_to_add += 1

        tgt_kin_keys: set[tuple[int, str]] = set()
        for kin in tgt.query(NextOfKin).all():
            tgt_kin_keys.add((kin.std_no, kin.name.strip().lower()))
        for kin in src.query(NextOfKin).all():
            if kin.std_no in tgt_student_ids:
                key = (kin.std_no, kin.name.strip().lower())
                if key not in tgt_kin_keys:
                    result.kins_to_add += 1
                    tgt_kin_keys.add(key)

    return result


def _effective_value(val: object) -> object:
    if isinstance(val, str) and val.strip() == "":
        return None
    return val


def merge_students(
    source: Session,
    target: Session,
    stats: MergeStats,
    progress_callback: Callable[[str, int, int], None] | None = None,
    resolutions: dict[tuple[int, str], str] | None = None,
) -> None:
    resolved = resolutions or {}
    source_students = source.query(Student).all()
    target_students = {s.std_no: s for s in target.query(Student).all()}

    used_national_ids: set[str] = set()
    for s in target_students.values():
        if s.national_id:
            used_national_ids.add(s.national_id)

    total = len(source_students)
    for i, src in enumerate(source_students):
        if progress_callback:
            progress_callback(f"Merging student {src.std_no}...", i + 1, total)

        tgt = target_students.get(src.std_no)
        if tgt is None:
            nat_id = _effective_value(src.national_id)
            if isinstance(nat_id, str) and nat_id in used_national_ids:
                nat_id = None
            new_student = Student(
                std_no=src.std_no,
                name=src.name,
                national_id=nat_id,
                status=src.status,
                date_of_birth=src.date_of_birth,
                phone1=_effective_value(src.phone1),
                phone2=_effective_value(src.phone2),
                gender=_effective_value(src.gender),
                marital_status=_effective_value(src.marital_status),
                country=_effective_value(src.country),
                race=_effective_value(src.race),
                nationality=_effective_value(src.nationality),
                birth_place=_effective_value(src.birth_place),
                religion=_effective_value(src.religion),
            )
            if isinstance(nat_id, str):
                used_national_ids.add(nat_id)
            target.add(new_student)
            stats.students_added += 1
        else:
            changed = False
            for fname in STUDENT_FILLABLE_FIELDS:
                tgt_val = getattr(tgt, fname)
                src_val = _effective_value(getattr(src, fname))
                if tgt_val is None and src_val is not None:
                    if fname == "national_id" and isinstance(src_val, str):
                        if src_val in used_national_ids:
                            continue
                        used_national_ids.add(src_val)
                    setattr(tgt, fname, src_val)
                    stats.students_fields_filled[fname] = (
                        stats.students_fields_filled.get(fname, 0) + 1
                    )
                    changed = True
                elif (
                    tgt_val is not None
                    and src_val is not None
                    and str(tgt_val).strip() != str(src_val).strip()
                ):
                    key = (src.std_no, fname)
                    if key in resolved:
                        chosen = resolved[key]
                        if str(chosen).strip() != str(tgt_val).strip():
                            if fname == "national_id" and isinstance(chosen, str):
                                if chosen in used_national_ids:
                                    continue
                                if isinstance(tgt_val, str):
                                    used_national_ids.discard(tgt_val)
                                used_national_ids.add(chosen)
                            setattr(tgt, fname, chosen)
                            changed = True
            if changed:
                stats.students_updated += 1
            else:
                stats.students_skipped += 1

    target.flush()
    logger.info(
        "Students: %d added, %d updated, %d skipped",
        stats.students_added,
        stats.students_updated,
        stats.students_skipped,
    )


def merge_student_education(
    source: Session,
    target: Session,
    stats: MergeStats,
    progress_callback: Callable[[str, int, int], None] | None = None,
) -> None:
    target_student_ids = {row[0] for row in target.query(Student.std_no).all()}
    target_cms_ids = {
        row[0]
        for row in target.query(StudentEducation.cms_id)
        .filter(StudentEducation.cms_id.isnot(None))
        .all()
    }

    source_educations = source.query(StudentEducation).all()
    total = len(source_educations)

    for i, src_edu in enumerate(source_educations):
        if progress_callback:
            progress_callback(f"Merging education record {i + 1}...", i + 1, total)

        if src_edu.std_no not in target_student_ids:
            stats.education_skipped += 1
            continue

        if src_edu.cms_id is not None and src_edu.cms_id in target_cms_ids:
            stats.education_skipped += 1
            continue

        is_pg = target.bind.dialect.name == "postgresql" if target.bind else False

        new_edu = StudentEducation(
            std_no=src_edu.std_no,
            school_name=src_edu.school_name or "",
            type=None if is_pg else src_edu.type,
            level=None if is_pg else src_edu.level,
            start_date=src_edu.start_date,
            end_date=src_edu.end_date,
            cms_id=src_edu.cms_id,
        )
        target.add(new_edu)
        target.flush()

        if is_pg and (src_edu.type or src_edu.level):
            set_clauses = []
            params: dict[str, object] = {"edu_id": new_edu.id}
            if src_edu.type:
                set_clauses.append("type = CAST(:edu_type AS education_type)")
                params["edu_type"] = src_edu.type
            if src_edu.level:
                set_clauses.append("level = CAST(:edu_level AS education_level)")
                params["edu_level"] = src_edu.level
            if set_clauses:
                target.execute(
                    text(
                        f"UPDATE student_education SET {', '.join(set_clauses)} WHERE id = :edu_id"
                    ),
                    params,
                )
        if src_edu.cms_id is not None:
            target_cms_ids.add(src_edu.cms_id)
        stats.education_added += 1

    target.flush()
    logger.info(
        "Education: %d added, %d skipped",
        stats.education_added,
        stats.education_skipped,
    )


def merge_next_of_kins(
    source: Session,
    target: Session,
    stats: MergeStats,
    progress_callback: Callable[[str, int, int], None] | None = None,
) -> None:
    target_student_ids = {row[0] for row in target.query(Student.std_no).all()}

    existing_kins: set[tuple[int, str]] = set()
    for kin in target.query(NextOfKin).all():
        existing_kins.add((kin.std_no, kin.name.strip().lower()))

    source_kins = source.query(NextOfKin).all()
    total = len(source_kins)

    for i, src_kin in enumerate(source_kins):
        if progress_callback:
            progress_callback(f"Merging next of kin {i + 1}...", i + 1, total)

        if src_kin.std_no not in target_student_ids:
            stats.kins_skipped += 1
            continue

        key = (src_kin.std_no, src_kin.name.strip().lower())
        if key in existing_kins:
            stats.kins_skipped += 1
            continue

        new_kin = NextOfKin(
            std_no=src_kin.std_no,
            name=src_kin.name,
            relationship=src_kin.relationship,
            phone=src_kin.phone,
            email=src_kin.email,
            occupation=src_kin.occupation,
            address=src_kin.address,
            country=src_kin.country,
        )
        target.add(new_kin)
        existing_kins.add(key)
        stats.kins_added += 1

    target.flush()
    logger.info(
        "Next of Kin: %d added, %d skipped",
        stats.kins_added,
        stats.kins_skipped,
    )


def run_merge(
    source_engine: Engine,
    target_engine: Engine,
    progress_callback: Callable[[str, int, int], None] | None = None,
    resolutions: dict[tuple[int, str], str] | None = None,
) -> MergeStats:
    stats = MergeStats()

    with Session(source_engine) as source_session:
        with Session(target_engine) as target_session:
            try:
                merge_students(
                    source_session,
                    target_session,
                    stats,
                    progress_callback,
                    resolutions,
                )
                merge_student_education(
                    source_session, target_session, stats, progress_callback
                )
                merge_next_of_kins(
                    source_session, target_session, stats, progress_callback
                )
                target_session.commit()
                logger.info("Merge completed successfully")
            except Exception:
                target_session.rollback()
                logger.exception("Merge failed, rolling back")
                raise

    return stats


def create_source_engine(url: str) -> Engine:
    return create_engine(url, echo=False, pool_pre_ping=True, poolclass=NullPool)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Upload missing data from source database to target database"
    )
    parser.add_argument("--source", required=True, help="Source database URL")
    parser.add_argument("--target", required=True, help="Target database URL")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    args = parser.parse_args()

    source_engine = create_source_engine(args.source)
    target_engine = create_source_engine(args.target)

    if args.dry_run:
        logger.info("DRY RUN mode - analyzing differences...")
        with Session(source_engine) as src, Session(target_engine) as tgt:
            src_count = src.query(Student).count()
            tgt_count = tgt.query(Student).count()
            src_ids = {row[0] for row in src.query(Student.std_no).all()}
            tgt_ids = {row[0] for row in tgt.query(Student.std_no).all()}
            only_src = len(src_ids - tgt_ids)
            both = len(src_ids & tgt_ids)

            null_counts: dict[str, int] = {}
            for s in tgt.query(Student).filter(Student.std_no.in_(src_ids)).all():
                for fname in STUDENT_FILLABLE_FIELDS:
                    if getattr(s, fname) is None:
                        null_counts[fname] = null_counts.get(fname, 0) + 1

            print(f"\nStudents: source={src_count}, target={tgt_count}")
            print(f"  New (only in source): {only_src}")
            print(f"  Shared: {both}")
            print("  NULL fields in target (fillable from source):")
            for fname, count in sorted(null_counts.items(), key=lambda x: -x[1]):
                print(f"    {fname}: {count}")

            src_edu = src.query(StudentEducation).count()
            tgt_edu = tgt.query(StudentEducation).count()
            print(f"\nEducation: source={src_edu}, target={tgt_edu}")

            src_kins = src.query(NextOfKin).count()
            tgt_kins = tgt.query(NextOfKin).count()
            print(f"Next of Kin: source={src_kins}, target={tgt_kins}")
        return

    def progress(msg: str, current: int, total: int) -> None:
        if current % 500 == 0 or current == total:
            logger.info("[%d/%d] %s", current, total, msg)

    stats = run_merge(source_engine, target_engine, progress)
    print(stats.summary())


if __name__ == "__main__":
    main()
