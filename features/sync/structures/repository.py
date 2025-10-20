from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import distinct
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
    semester_number: int
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
        self._engine = get_engine(use_local=True)

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
