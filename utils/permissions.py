from typing import Optional

from base.auth.session_manager import SessionManager


def can_edit_grades() -> bool:
    user_data = SessionManager.get_user_data()
    if not user_data:
        return False

    role = user_data.get("role")
    return role == "admin"


def get_current_user_role() -> Optional[str]:
    user_data = SessionManager.get_user_data()
    if not user_data:
        return None
    return user_data.get("role")
