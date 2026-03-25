import logging
from datetime import datetime, timedelta
from typing import Optional

import nanoid
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import Account
from database.models import Session as SessionModel
from database.models import User

logger = logging.getLogger(__name__)


class AuthRepository:
    def __init__(self, db_session: Session):
        self.db = db_session

    def get_user_by_email(self, email: str) -> Optional[User]:
        try:
            stmt = select(User).where(User.email == email)
            result = self.db.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            self.db.rollback()
            logger.exception(f"Error fetching user by email: {e}")
            return None

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        try:
            stmt = select(User).where(User.id == user_id)
            result = self.db.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            self.db.rollback()
            logger.exception(f"Error fetching user by id: {e}")
            return None

    def create_user(
        self, email: str, name: str, image: Optional[str] = None
    ) -> Optional[User]:
        try:
            user = User(
                id=nanoid.generate(),
                email=email,
                name=name,
                image=image,
                email_verified=True,
                role="user",
            )
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)
            return user
        except Exception as e:
            self.db.rollback()
            logger.exception(f"Error creating user: {e}")
            return None

    def update_user(
        self, user_id: str, name: Optional[str] = None, image: Optional[str] = None
    ) -> Optional[User]:
        try:
            user = self.get_user_by_id(user_id)
            if not user:
                return None

            if name:
                user.name = name
            if image:
                user.image = image

            self.db.commit()
            self.db.refresh(user)
            return user
        except Exception as e:
            self.db.rollback()
            logger.exception(f"Error updating user: {e}")
            return None

    def create_account(
        self,
        user_id: str,
        provider_id: str,
        account_id: str,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        access_token_expires_at: Optional[datetime] = None,
        scope: Optional[str] = None,
        id_token: Optional[str] = None,
    ) -> Optional[Account]:
        try:
            account = Account(
                id=nanoid.generate(),
                user_id=user_id,
                provider_id=provider_id,
                account_id=account_id,
                access_token=access_token,
                refresh_token=refresh_token,
                access_token_expires_at=access_token_expires_at,
                scope=scope,
                id_token=id_token,
            )
            self.db.add(account)
            self.db.commit()
            self.db.refresh(account)
            return account
        except Exception as e:
            self.db.rollback()
            logger.exception(f"Error creating account: {e}")
            return None

    def get_account(self, provider_id: str, account_id: str) -> Optional[Account]:
        try:
            stmt = select(Account).where(
                Account.provider_id == provider_id, Account.account_id == account_id
            )
            result = self.db.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            self.db.rollback()
            logger.exception(f"Error fetching account: {e}")
            return None

    def update_account_tokens(
        self,
        provider_id: str,
        account_id: str,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        access_token_expires_at: Optional[datetime] = None,
    ) -> Optional[Account]:
        try:
            account = self.get_account(provider_id, account_id)
            if not account:
                return None

            if access_token:
                account.access_token = access_token
            if refresh_token:
                account.refresh_token = refresh_token
            if access_token_expires_at:
                account.access_token_expires_at = access_token_expires_at

            self.db.commit()
            self.db.refresh(account)
            return account
        except Exception as e:
            self.db.rollback()
            logger.exception(f"Error updating account tokens: {e}")
            return None

    def create_session(
        self, user_id: str, expires_days: int = 30
    ) -> Optional[SessionModel]:
        try:
            token = nanoid.generate(size=32)
            expires_at = datetime.utcnow() + timedelta(days=expires_days)

            session = SessionModel(
                id=nanoid.generate(),
                token=token,
                user_id=user_id,
                expires_at=expires_at,
            )
            self.db.add(session)
            self.db.commit()
            self.db.refresh(session)
            return session
        except Exception as e:
            self.db.rollback()
            logger.exception(f"Error creating session: {e}")
            return None

    def get_session(self, token: str) -> Optional[SessionModel]:
        try:
            stmt = select(SessionModel).where(SessionModel.token == token)
            result = self.db.execute(stmt)
            session = result.scalar_one_or_none()

            if session and session.expires_at < datetime.utcnow():
                self.delete_session(token)
                return None

            return session
        except Exception as e:
            self.db.rollback()
            logger.exception(f"Error fetching session: {e}")
            return None

    def delete_session(self, token: str) -> bool:
        try:
            stmt = select(SessionModel).where(SessionModel.token == token)
            result = self.db.execute(stmt)
            session = result.scalar_one_or_none()

            if session:
                self.db.delete(session)
                self.db.commit()
                return True
            return False
        except Exception as e:
            self.db.rollback()
            logger.exception(f"Error deleting session: {e}")
            return False

    def get_user_by_token(self, token: str) -> Optional[User]:
        try:
            session = self.get_session(token)
            if not session:
                return None

            return self.get_user_by_id(session.user_id)
        except Exception as e:
            self.db.rollback()
            logger.exception(f"Error fetching user by session token: {e}")
            return None
