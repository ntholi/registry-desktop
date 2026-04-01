from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import distinct, or_
from sqlalchemy.orm import Session

from base import get_logger
from database import (
    Module,
    Program,
    School,
    SemesterModule,
    Structure,
    StructureSemester,
    get_engine,
)
from database.models import ProgramLevel

logger = get_logger(__name__)


@dataclass(frozen=True)
class StructureRow:
    cms_id: int
    code: str
    desc: Optional[str]
    school_code: Optional[str]
    program_name: Optional[str]


@dataclass(frozen=True)
class SemesterRow:
    cms_id: int
    semester_number: str
    name: str
    total_credits: float


@dataclass(frozen=True)
class SemesterModuleRow:
    cms_id: int
    module_code: str
    module_name: str
    type: str
    credits: float
    hidden: bool


class StructureRepository:
    def __init__(self) -> None:
        self._engine = get_engine()

    @contextmanager
    def _session(self):
        with Session(self._engine) as session:
            yield session

    def _resolve_program_db_id(
        self, session: Session, program_id: int
    ) -> Optional[int]:
        result = session.query(Program.id).filter(Program.id == program_id).first()
        if result:
            return int(result[0])

        result = session.query(Program.id).filter(Program.cms_id == program_id).first()
        if result:
            return int(result[0])

        return None

    def _resolve_structure_db_id(
        self, session: Session, structure_id: int
    ) -> Optional[int]:
        result = (
            session.query(Structure.id).filter(Structure.id == structure_id).first()
        )
        if result:
            return int(result[0])

        result = (
            session.query(Structure.id).filter(Structure.cms_id == structure_id).first()
        )
        if result:
            return int(result[0])

        return None

    def _resolve_structure_semester_db_id(
        self, session: Session, structure_semester_id: int
    ) -> Optional[int]:
        result = (
            session.query(StructureSemester.id)
            .filter(StructureSemester.id == structure_semester_id)
            .first()
        )
        if result:
            return int(result[0])

        result = (
            session.query(StructureSemester.id)
            .filter(StructureSemester.cms_id == structure_semester_id)
            .first()
        )
        if result:
            return int(result[0])

        return None

    def list_active_schools(self):
        with self._session() as session:
            return (
                session.query(School.cms_id.label("cms_id"), School.name)
                .filter(School.is_active == True)
                .filter(School.cms_id.isnot(None))
                .order_by(School.name)
                .all()
            )

    def list_programs(self, school_id: Optional[int] = None):
        with self._session() as session:
            query = session.query(Program.cms_id.label("cms_id"), Program.name).filter(
                Program.cms_id.isnot(None)
            )
            if school_id:
                query = query.join(School, Program.school_id == School.id).filter(
                    School.cms_id == school_id
                )
            return query.order_by(Program.name).all()

    def get_program_for_structure(self, structure_id: int) -> tuple[int, str] | None:
        with self._session() as session:
            result = (
                session.query(Program.cms_id.label("cms_id"), Program.name)
                .join(Structure, Structure.program_id == Program.id)
                .filter(
                    or_(Structure.id == structure_id, Structure.cms_id == structure_id)
                )
                .filter(Program.cms_id.isnot(None))
                .first()
            )
            if not result:
                return None
            return int(result.cms_id), str(result.name)

    def fetch_structures(
        self,
        *,
        school_id: Optional[int] = None,
        program_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 30,
    ):
        offset = (page - 1) * page_size
        with self._session() as session:
            query = (
                session.query(
                    Structure.cms_id.label("cms_id"),
                    Structure.code,
                    Structure.desc,
                    School.code.label("school_code"),
                    Program.name.label("program_name"),
                )
                .join(Program, Structure.program_id == Program.id)
                .join(School, Program.school_id == School.id)
                .filter(Structure.cms_id.isnot(None))
            )

            if school_id:
                query = query.filter(School.cms_id == school_id)

            if program_id:
                query = query.filter(Program.cms_id == program_id)

            query = query.order_by(Structure.code)
            total = query.count()
            results = query.offset(offset).limit(page_size).all()

        rows = [
            StructureRow(
                cms_id=result.cms_id,
                code=result.code,
                desc=result.desc,
                school_code=result.school_code,
                program_name=result.program_name,
            )
            for result in results
        ]
        return rows, total

    def get_structure_semesters(self, structure_id: int):
        with self._session() as session:
            results = (
                session.query(
                    StructureSemester.cms_id.label("cms_id"),
                    StructureSemester.semester_number,
                    StructureSemester.name,
                    StructureSemester.total_credits,
                )
                .join(Structure, StructureSemester.structure_id == Structure.id)
                .filter(
                    or_(Structure.id == structure_id, Structure.cms_id == structure_id)
                )
                .filter(StructureSemester.cms_id.isnot(None))
                .order_by(StructureSemester.semester_number)
                .all()
            )

        return [
            SemesterRow(
                cms_id=result.cms_id,
                semester_number=result.semester_number,
                name=result.name,
                total_credits=result.total_credits,
            )
            for result in results
        ]

    def get_semester_modules(self, semester_id: int):
        with self._session() as session:
            results = (
                session.query(
                    SemesterModule.cms_id.label("cms_id"),
                    Module.code,
                    Module.name,
                    SemesterModule.type,
                    SemesterModule.credits,
                    SemesterModule.hidden,
                )
                .join(Module, SemesterModule.module_id == Module.id)
                .join(
                    StructureSemester,
                    SemesterModule.semester_id == StructureSemester.id,
                )
                .filter(
                    or_(
                        StructureSemester.id == semester_id,
                        StructureSemester.cms_id == semester_id,
                    )
                )
                .filter(SemesterModule.cms_id.isnot(None))
                .order_by(Module.code)
                .all()
            )

        return [
            SemesterModuleRow(
                cms_id=result.cms_id,
                module_code=result.code,
                module_name=result.name,
                type=result.type,
                credits=result.credits,
                hidden=result.hidden,
            )
            for result in results
        ]

    def save_school(self, cms_id: int, code: str, name: str) -> School:
        with self._session() as session:
            existing_school = (
                session.query(School).filter(School.cms_id == cms_id).first()
            )
            if not existing_school:
                existing_school = (
                    session.query(School).filter(School.code == code).first()
                )
            if existing_school:
                existing_school.code = code  # type: ignore
                existing_school.name = name  # type: ignore
                existing_school.is_active = True  # type: ignore
                existing_school.cms_id = cms_id  # type: ignore
                session.commit()
                session.refresh(existing_school)
                return existing_school
            else:
                new_school = School(
                    cms_id=cms_id,
                    code=code,
                    name=name,
                    is_active=True,
                )
                session.add(new_school)
                session.commit()
                session.refresh(new_school)
                return new_school

    def save_program(
        self,
        cms_id: int,
        code: str,
        name: str,
        school_id: int,
        level: ProgramLevel = "degree",
    ) -> Program:
        with self._session() as session:
            existing_program = (
                session.query(Program).filter(Program.cms_id == cms_id).first()
            )
            if not existing_program:
                existing_program = (
                    session.query(Program).filter(Program.code == code).first()
                )
            if existing_program:
                existing_program.code = code  # type: ignore
                existing_program.name = name  # type: ignore
                existing_program.school_id = school_id  # type: ignore
                existing_program.level = level  # type: ignore
                existing_program.cms_id = cms_id  # type: ignore
                session.commit()
                session.refresh(existing_program)
                return existing_program
            else:
                new_program = Program(
                    cms_id=cms_id,
                    code=code,
                    name=name,
                    school_id=school_id,
                    level=level,
                )
                session.add(new_program)
                session.commit()
                session.refresh(new_program)
                return new_program

    def save_structure(
        self,
        cms_id: int,
        code: str,
        desc: str,
        program_id: int,
    ) -> Structure:
        with self._session() as session:
            resolved_program_id = self._resolve_program_db_id(session, program_id)
            if resolved_program_id is None:
                raise ValueError(f"Program not found for ID {program_id}")

            existing_structure = (
                session.query(Structure).filter(Structure.cms_id == cms_id).first()
            )
            if not existing_structure:
                existing_structure = (
                    session.query(Structure).filter(Structure.code == code).first()
                )
            if existing_structure:
                existing_structure.code = code  # type: ignore
                existing_structure.desc = desc  # type: ignore
                existing_structure.program_id = resolved_program_id  # type: ignore
                existing_structure.cms_id = cms_id  # type: ignore
                session.commit()
                session.refresh(existing_structure)
                return existing_structure
            else:
                new_structure = Structure(
                    cms_id=cms_id,
                    code=code,
                    desc=desc,
                    program_id=resolved_program_id,
                )
                session.add(new_structure)
                session.commit()
                session.refresh(new_structure)
                return new_structure

    def save_semester(
        self,
        cms_id: int,
        semester_number: str,
        name: str,
        total_credits: float,
        structure_id: int,
    ) -> StructureSemester:
        with self._session() as session:
            resolved_structure_id = self._resolve_structure_db_id(session, structure_id)
            if resolved_structure_id is None:
                raise ValueError(f"Structure not found for ID {structure_id}")

            existing_semester = (
                session.query(StructureSemester)
                .filter(StructureSemester.cms_id == cms_id)
                .first()
            )
            if not existing_semester:
                existing_semester = (
                    session.query(StructureSemester)
                    .filter(StructureSemester.structure_id == resolved_structure_id)
                    .filter(StructureSemester.semester_number == semester_number)
                    .first()
                )
            if existing_semester:
                existing_semester.semester_number = semester_number  # type: ignore
                existing_semester.name = name  # type: ignore
                existing_semester.total_credits = total_credits  # type: ignore
                existing_semester.structure_id = resolved_structure_id  # type: ignore
                existing_semester.cms_id = cms_id  # type: ignore
                session.commit()
                session.refresh(existing_semester)
                return existing_semester
            else:
                new_semester = StructureSemester(
                    cms_id=cms_id,
                    semester_number=semester_number,
                    name=name,
                    total_credits=total_credits,
                    structure_id=resolved_structure_id,
                )
                session.add(new_semester)
                session.commit()
                session.refresh(new_semester)
                return new_semester

    def save_semester_module(
        self,
        cms_id: int,
        module_code: str,
        module_name: str,
        module_type: str,
        credits: float,
        semester_id: int,
        hidden: bool = False,
    ) -> SemesterModule:
        normalized_module_code = module_code.strip()
        normalized_module_name = module_name.strip()

        with self._session() as session:
            resolved_semester_id = self._resolve_structure_semester_db_id(
                session, semester_id
            )
            if resolved_semester_id is None:
                raise ValueError(f"Semester not found for ID {semester_id}")

            module = (
                session.query(Module)
                .filter(Module.code == normalized_module_code)
                .first()
            )
            if not module:
                module = Module(
                    code=normalized_module_code,
                    name=normalized_module_name,
                    status="Active",
                )
                session.add(module)
                session.commit()
                session.refresh(module)
            elif normalized_module_name and module.name != normalized_module_name:
                module.name = normalized_module_name  # type: ignore
                session.commit()
                session.refresh(module)

            existing_sem_module = (
                session.query(SemesterModule)
                .filter(SemesterModule.cms_id == cms_id)
                .first()
            )
            if not existing_sem_module:
                existing_sem_module = (
                    session.query(SemesterModule)
                    .filter(SemesterModule.module_id == module.id)
                    .filter(SemesterModule.semester_id == resolved_semester_id)
                    .first()
                )
            if existing_sem_module:
                existing_sem_module.module_id = module.id  # type: ignore
                existing_sem_module.type = module_type  # type: ignore
                existing_sem_module.credits = credits  # type: ignore
                existing_sem_module.semester_id = resolved_semester_id  # type: ignore
                existing_sem_module.hidden = hidden  # type: ignore
                existing_sem_module.cms_id = cms_id  # type: ignore
                session.commit()
                session.refresh(existing_sem_module)
                return existing_sem_module
            else:
                new_sem_module = SemesterModule(
                    cms_id=cms_id,
                    module_id=module.id,
                    type=module_type,
                    credits=credits,
                    semester_id=resolved_semester_id,
                    hidden=hidden,
                )
                session.add(new_sem_module)
                session.commit()
                session.refresh(new_sem_module)
                return new_sem_module
