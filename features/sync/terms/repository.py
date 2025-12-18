from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from base import get_logger
from database import Term, get_engine

logger = get_logger(__name__)


@dataclass(frozen=True)
class TermRow:
    id: int
    code: str
    name: Optional[str]
    year: Optional[int]
    start_date: Optional[str]
    end_date: Optional[str]
    is_active: bool


class TermRepository:
    def __init__(self) -> None:
        self._engine = get_engine()

    @contextmanager
    def _session(self):
        with Session(self._engine) as session:
            yield session

    def fetch_terms(
        self,
        *,
        search_query: Optional[str] = None,
        page: int = 1,
        page_size: int = 30,
    ):
        offset = (page - 1) * page_size
        with self._session() as session:
            query = session.query(Term)

            if search_query:
                search_pattern = f"%{search_query.lower()}%"
                query = query.filter(
                    (func.lower(Term.code).like(search_pattern))
                    | (func.lower(Term.name).like(search_pattern))
                )

            query = query.order_by(Term.code.desc())
            total = query.count()
            results = query.offset(offset).limit(page_size).all()

        rows = [
            TermRow(
                id=result.id,
                code=result.code,
                name=result.name,
                year=result.year,
                start_date=result.start_date,
                end_date=result.end_date,
                is_active=result.is_active,
            )
            for result in results
        ]
        return rows, total

    def get_term(self, term_id: int) -> Optional[Term]:
        with self._session() as session:
            return session.query(Term).filter(Term.id == term_id).first()

    def get_term_by_code(self, code: str) -> Optional[Term]:
        with self._session() as session:
            return session.query(Term).filter(Term.code == code).first()

    def save_term(
        self,
        code: str,
        name: Optional[str] = None,
        year: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        is_active: bool = False,
    ) -> Term:
        with self._session() as session:
            existing_term = session.query(Term).filter(Term.code == code).first()
            if existing_term:
                existing_term.name = name
                existing_term.year = year
                existing_term.start_date = start_date
                existing_term.end_date = end_date
                existing_term.is_active = is_active
                session.commit()
                session.refresh(existing_term)
                return existing_term
            else:
                new_term = Term(
                    code=code,
                    name=name,
                    year=year,
                    start_date=start_date,
                    end_date=end_date,
                    is_active=is_active,
                )
                session.add(new_term)
                session.commit()
                session.refresh(new_term)
                return new_term
