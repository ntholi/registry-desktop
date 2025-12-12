from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import distinct
from sqlalchemy.orm import Session

from base import get_logger
from database import (Module, Program, School, SemesterModule, Structure,
                      StructureSemester, get_engine)

logger = get_logger(__name__)


@dataclass(frozen=True)
class StructureRow:
    id: int
    code: str
    desc: Optional[str]
    school_code: Optional[str]
    program_name: Optional[str]


@dataclass(frozen=True)
class SemesterRow:
    id: int
    semester_number: str
    name: str
    total_credits: float


@dataclass(frozen=True)
class SemesterModuleRow:
    id: int
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

    def list_active_schools(self):
        with self._session() as session:
            return (
                session.query(School.id, School.name)
                .filter(School.is_active == True)
                .order_by(School.name)
                .all()
            )

    def list_programs(self, school_id: Optional[int] = None):
        with self._session() as session:
            query = session.query(Program.id, Program.name)
            if school_id:
                query = query.filter(Program.school_id == school_id)
            return query.order_by(Program.name).all()

    def get_program_for_structure(self, structure_id: int) -> tuple[int, str] | None:
        with self._session() as session:
            result = (
                session.query(Program.id, Program.name)
                .join(Structure, Structure.program_id == Program.id)
                .filter(Structure.id == structure_id)
                .first()
            )
            if not result:
                return None
            return int(result.id), str(result.name)

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
                    Structure.id,
                    Structure.code,
                    Structure.desc,
                    School.code.label("school_code"),
                    Program.name.label("program_name"),
                )
                .join(Program, Structure.program_id == Program.id)
                .join(School, Program.school_id == School.id)
            )

            if school_id:
                query = query.filter(Program.school_id == school_id)

            if program_id:
                query = query.filter(Program.id == program_id)

            query = query.order_by(Structure.code)
            total = query.count()
            results = query.offset(offset).limit(page_size).all()

        rows = [
            StructureRow(
                id=result.id,
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
                    StructureSemester.id,
                    StructureSemester.semester_number,
                    StructureSemester.name,
                    StructureSemester.total_credits,
                )
                .filter(StructureSemester.structure_id == structure_id)
                .order_by(StructureSemester.semester_number)
                .all()
            )

        return [
            SemesterRow(
                id=result.id,
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
                    SemesterModule.id,
                    Module.code,
                    Module.name,
                    SemesterModule.type,
                    SemesterModule.credits,
                    SemesterModule.hidden,
                )
                .join(Module, SemesterModule.module_id == Module.id)
                .filter(SemesterModule.semester_id == semester_id)
                .order_by(Module.code)
                .all()
            )

        return [
            SemesterModuleRow(
                id=result.id,
                module_code=result.code,
                module_name=result.name,
                type=result.type,
                credits=result.credits,
                hidden=result.hidden,
            )
            for result in results
        ]

    def save_school(self, school_id: int, code: str, name: str) -> School:
        with self._session() as session:
            existing_school = (
                session.query(School).filter(School.id == school_id).first()
            )
            if existing_school:
                existing_school.code = code  # type: ignore
                existing_school.name = name  # type: ignore
                existing_school.is_active = True  # type: ignore
                session.commit()
                session.refresh(existing_school)
                return existing_school
            else:
                new_school = School(
                    id=school_id,
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
        program_id: int,
        code: str,
        name: str,
        school_id: int,
        level: str = "Unknown",
    ) -> Program:
        with self._session() as session:
            existing_program = (
                session.query(Program).filter(Program.id == program_id).first()
            )
            if existing_program:
                existing_program.code = code  # type: ignore
                existing_program.name = name  # type: ignore
                existing_program.school_id = school_id  # type: ignore
                existing_program.level = level  # type: ignore
                session.commit()
                session.refresh(existing_program)
                return existing_program
            else:
                new_program = Program(
                    id=program_id,
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
        structure_id: int,
        code: str,
        desc: str,
        program_id: int,
    ) -> Structure:
        with self._session() as session:
            existing_structure = (
                session.query(Structure).filter(Structure.id == structure_id).first()
            )
            if existing_structure:
                existing_structure.code = code  # type: ignore
                existing_structure.desc = desc  # type: ignore
                existing_structure.program_id = program_id  # type: ignore
                session.commit()
                session.refresh(existing_structure)
                return existing_structure
            else:
                new_structure = Structure(
                    id=structure_id,
                    code=code,
                    desc=desc,
                    program_id=program_id,
                )
                session.add(new_structure)
                session.commit()
                session.refresh(new_structure)
                return new_structure

    def save_semester(
        self,
        semester_id: int,
        semester_number: str,
        name: str,
        total_credits: float,
        structure_id: int,
    ) -> StructureSemester:
        with self._session() as session:
            existing_semester = (
                session.query(StructureSemester)
                .filter(StructureSemester.id == semester_id)
                .first()
            )
            if existing_semester:
                existing_semester.semester_number = semester_number  # type: ignore
                existing_semester.name = name  # type: ignore
                existing_semester.total_credits = total_credits  # type: ignore
                existing_semester.structure_id = structure_id  # type: ignore
                session.commit()
                session.refresh(existing_semester)
                return existing_semester
            else:
                new_semester = StructureSemester(
                    id=semester_id,
                    semester_number=semester_number,
                    name=name,
                    total_credits=total_credits,
                    structure_id=structure_id,
                )
                session.add(new_semester)
                session.commit()
                session.refresh(new_semester)
                return new_semester

    def save_semester_module(
        self,
        sem_module_id: int,
        module_code: str,
        module_name: str,
        module_type: str,
        credits: float,
        semester_id: int,
        hidden: bool = False,
    ) -> SemesterModule:
        with self._session() as session:
            module = session.query(Module).filter(Module.code == module_code).first()
            if not module:
                module = Module(
                    code=module_code,
                    name=module_name,
                    status="Active",
                )
                session.add(module)
                session.commit()
                session.refresh(module)

            existing_sem_module = (
                session.query(SemesterModule)
                .filter(SemesterModule.id == sem_module_id)
                .first()
            )
            if existing_sem_module:
                existing_sem_module.module_id = module.id  # type: ignore
                existing_sem_module.type = module_type  # type: ignore
                existing_sem_module.credits = credits  # type: ignore
                existing_sem_module.semester_id = semester_id  # type: ignore
                existing_sem_module.hidden = hidden  # type: ignore
                session.commit()
                session.refresh(existing_sem_module)
                return existing_sem_module
            else:
                new_sem_module = SemesterModule(
                    id=sem_module_id,
                    module_id=module.id,
                    type=module_type,
                    credits=credits,
                    semester_id=semester_id,
                    hidden=hidden,
                )
                session.add(new_sem_module)
                session.commit()
                session.refresh(new_sem_module)
                return new_sem_module
