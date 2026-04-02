from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from base import get_logger
from database import Module, get_engine

logger = get_logger(__name__)


@dataclass(frozen=True)
class ModuleRow:
    module_db_id: int
    cms_id: Optional[int]
    code: str
    name: str
    status: str
    remark: Optional[str]
    timestamp: Optional[str]


class ModuleRepository:
    def __init__(self) -> None:
        self._engine = get_engine()

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
                search_pattern = f"%{search_query.lower()}%"
                query = query.filter(
                    (func.lower(Module.code).like(search_pattern))
                    | (func.lower(Module.name).like(search_pattern))
                )

            query = query.order_by(Module.code)
            total = query.count()
            results = query.offset(offset).limit(page_size).all()

        rows = [
            ModuleRow(
                module_db_id=result.id,  # type: ignore
                cms_id=result.cms_id,  # type: ignore
                code=result.code,  # type: ignore
                name=result.name,  # type: ignore
                status=result.status,  # type: ignore
                remark=result.remark,  # type: ignore
                timestamp=result.timestamp,  # type: ignore
            )
            for result in results
        ]
        return rows, total

    def get_module(self, cms_id: int) -> Optional[Module]:
        with self._session() as session:
            return session.query(Module).filter(Module.cms_id == cms_id).first()

    def save_module(
        self,
        cms_id: int,
        code: str,
        name: str,
        status: str,
        remark: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> Module:
        normalized_code = code.strip()
        normalized_name = name.strip()

        with self._session() as session:
            existing_module = (
                session.query(Module).filter(Module.cms_id == cms_id).first()
            )
            if not existing_module:
                existing_module = (
                    session.query(Module).filter(Module.code == normalized_code).first()
                )
            if existing_module:
                existing_module.code = normalized_code  # type: ignore
                if normalized_name or not existing_module.name:
                    existing_module.name = normalized_name  # type: ignore
                existing_module.status = status  # type: ignore
                existing_module.remark = remark  # type: ignore
                existing_module.timestamp = timestamp  # type: ignore
                existing_module.cms_id = cms_id  # type: ignore
                session.commit()
                session.refresh(existing_module)
                return existing_module
            else:
                new_module = Module(
                    cms_id=cms_id,
                    code=normalized_code,
                    name=normalized_name,
                    status=status,
                    remark=remark,
                    timestamp=timestamp,
                )
                session.add(new_module)
                session.commit()
                session.refresh(new_module)
                return new_module

    def find_missing_cms_ids(
        self,
        cms_ids: list[int],
        *,
        chunk_size: int = 500,
    ) -> list[int]:
        pending_ids = [int(cms_id) for cms_id in cms_ids]
        if not pending_ids:
            return []

        existing_ids: set[int] = set()
        with self._session() as session:
            for start in range(0, len(pending_ids), chunk_size):
                chunk = pending_ids[start : start + chunk_size]
                rows = (
                    session.query(Module.cms_id).filter(Module.cms_id.in_(chunk)).all()
                )
                existing_ids.update(
                    int(cms_id) for (cms_id,) in rows if cms_id is not None
                )

        return [cms_id for cms_id in pending_ids if cms_id not in existing_ids]

    def create_local_module(
        self,
        code: str,
        name: str,
        status: str,
        remark: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> tuple[bool, str, Optional[Module]]:
        normalized_code = code.strip()
        normalized_name = name.strip()

        with self._session() as session:
            existing = (
                session.query(Module).filter(Module.code == normalized_code).first()
            )
            if existing:
                return (
                    False,
                    f"Module with code '{normalized_code}' already exists",
                    existing,
                )

            new_module = Module(
                code=normalized_code,
                name=normalized_name,
                status=status,
                remark=remark,
                timestamp=timestamp,
            )
            session.add(new_module)
            session.commit()
            session.refresh(new_module)
            return True, "Module created", new_module
