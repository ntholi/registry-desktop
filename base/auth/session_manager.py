import json
import logging
from pathlib import Path
from typing import Optional

from database.models import User

logger = logging.getLogger(__name__)


class SessionManager:
    SESSION_FILE = Path.home() / ".registry-desktop" / "session.json"

    @classmethod
    def save_session(cls, session_token: str, user: User):
        try:
            cls.SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)

            session_data = {
                "session_token": session_token,
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "name": user.name,
                    "image": user.image,
                    "role": user.role,
                    "position": user.position,
                }
            }

            with open(cls.SESSION_FILE, "w") as f:
                json.dump(session_data, f, indent=2)

            logger.info(f"Session saved for user: {user.email}")
        except Exception as e:
            logger.exception(f"Error saving session: {e}")

    @classmethod
    def load_session(cls) -> Optional[dict]:
        try:
            if not cls.SESSION_FILE.exists():
                return None

            with open(cls.SESSION_FILE, "r") as f:
                session_data = json.load(f)

            return session_data
        except Exception as e:
            logger.exception(f"Error loading session: {e}")
            return None

    @classmethod
    def clear_session(cls):
        try:
            if cls.SESSION_FILE.exists():
                cls.SESSION_FILE.unlink()
                logger.info("Session cleared")
        except Exception as e:
            logger.exception(f"Error clearing session: {e}")

    @classmethod
    def get_session_token(cls) -> Optional[str]:
        session_data = cls.load_session()
        if session_data:
            return session_data.get("session_token")
        return None

    @classmethod
    def get_user_data(cls) -> Optional[dict]:
        session_data = cls.load_session()
        if session_data:
            return session_data.get("user")
        return None
