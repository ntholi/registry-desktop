from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from base import get_logger
from database import Module, get_engine

logger = get_logger(__name__)


@dataclass(frozen=True)
class ModuleRow:
    id: int
    code: str
    name: str
    status: str
    timestamp: Optional[str]


class ModuleRepository:
    def __init__(self) -> None:
        self._engine = get_engine(use_local=True)

    @contextmanager
    def _session(self):
        with Session(self._engine) as session:
            yield session

    def fetch_modules(
        self,
        *,
        search_query: Optional[str] = None,
        page: int = 1,
        page_size: int = 30,
    ):
        offset = (page - 1) * page_size
        with self._session() as session:
            query = session.query(Module)

            if search_query:
                search_pattern = f"%{search_query}%"
                query = query.filter(
                    (Module.code.like(search_pattern))
                    | (Module.name.like(search_pattern))
                )

            query = query.order_by(Module.code)
            total = query.count()
            results = query.offset(offset).limit(page_size).all()

        rows = [
            ModuleRow(
                id=result.id,  # type: ignore
                code=result.code,  # type: ignore
                name=result.name,  # type: ignore
                status=result.status,  # type: ignore
                timestamp=result.timestamp,  # type: ignore
            )
            for result in results
        ]
        return rows, total

    def save_module(
        self,
        module_id: int,
        code: str,
        name: str,
        status: str,
        timestamp: Optional[str] = None,
    ) -> Module:
        with self._session() as session:
            existing_module = (
                session.query(Module).filter(Module.id == module_id).first()
            )
            if existing_module:
                existing_module.code = code  # type: ignore
                existing_module.name = name  # type: ignore
                existing_module.status = status  # type: ignore
                existing_module.timestamp = timestamp  # type: ignore
                session.commit()
                session.refresh(existing_module)
                return existing_module
            else:
                new_module = Module(
                    id=module_id,
                    code=code,
                    name=name,
                    status=status,
                    timestamp=timestamp,
                )
                session.add(new_module)
                session.commit()
                session.refresh(new_module)
                return new_module
