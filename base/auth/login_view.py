import logging
import threading
from typing import Callable, Optional

import wx
from sqlalchemy.orm import Session

from base.auth.oauth_service import OAuthService
from base.auth.repository import AuthRepository
from base.auth.session_manager import SessionManager
from database.connection import get_engine
from database.models import User

logger = logging.getLogger(__name__)


class LoginWindow(wx.Frame):
    def __init__(self, on_login_success: Callable[[User], None]):
        super().__init__(
            None, title="Limkokwing Registry - Login", size=wx.Size(500, 300)
        )

        self.on_login_success = on_login_success
        self.oauth_service: Optional[OAuthService] = None

        panel = wx.Panel(self)
        panel.SetBackgroundColour(wx.WHITE)

        main_sizer = wx.BoxSizer(wx.VERTICAL)

        main_sizer.AddStretchSpacer(1)

        title_label = wx.StaticText(panel, label="Limkokwing Registry")
        title_font = title_label.GetFont()
        title_font.PointSize += 8
        title_font = title_font.Bold()
        title_label.SetFont(title_font)
        main_sizer.Add(title_label, 0, wx.ALIGN_CENTER | wx.BOTTOM, 10)

        subtitle_label = wx.StaticText(panel, label="Desktop Application")
        subtitle_font = subtitle_label.GetFont()
        subtitle_font.PointSize += 2
        subtitle_label.SetFont(subtitle_font)
        subtitle_label.SetForegroundColour(wx.Colour(100, 100, 100))
        main_sizer.Add(subtitle_label, 0, wx.ALIGN_CENTER | wx.BOTTOM, 30)

        self.google_button = wx.Button(panel, label="Sign in with Google")
        self.google_button.SetMinSize(wx.Size(250, 40))
        button_font = self.google_button.GetFont()
        button_font.PointSize += 1
        self.google_button.SetFont(button_font)
        self.google_button.Bind(wx.EVT_BUTTON, self.on_google_signin)
        main_sizer.Add(self.google_button, 0, wx.ALIGN_CENTER | wx.BOTTOM, 10)

        self.status_text = wx.StaticText(panel, label="")
        self.status_text.SetForegroundColour(wx.Colour(100, 100, 100))

        main_sizer.AddStretchSpacer(1)

        main_sizer.Add(
            wx.StaticLine(panel, style=wx.LI_HORIZONTAL), 0, wx.EXPAND | wx.ALL, 10
        )

        footer_font = self.status_text.GetFont()
        footer_font.PointSize -= 1
        self.status_text.SetFont(footer_font)
        self.status_text.SetLabel("Authentication with Google")
        main_sizer.Add(self.status_text, 0, wx.ALIGN_CENTER | wx.BOTTOM, 10)

        panel.SetSizer(main_sizer)

        self.Centre()

    def on_google_signin(self, event):
        self.google_button.Enable(False)
        self.status_text.SetLabel("Opening browser for authentication...")

        thread = threading.Thread(target=self._authenticate_google, daemon=True)
        thread.start()

    def _authenticate_google(self):
        try:
            self.oauth_service = OAuthService()
            credentials, user_info = self.oauth_service.authenticate()

            if not credentials or not user_info:
                wx.CallAfter(
                    self._show_error, "Authentication failed. Please try again."
                )
                return

            wx.CallAfter(self.status_text.SetLabel, "Verifying user credentials...")

            engine = get_engine()
            with Session(engine) as db_session:
                auth_repo = AuthRepository(db_session)

                email = user_info.get("email")
                name = user_info.get("name")
                picture = user_info.get("picture")
                google_id = user_info.get("id")

                if not email or not google_id:
                    wx.CallAfter(
                        self._show_error,
                        "Failed to retrieve user information from Google.",
                    )
                    return

                user = auth_repo.get_user_by_email(email)

                if not user:
                    wx.CallAfter(
                        self._show_error,
                        f"No account found for {email}.\n\nPlease contact your administrator to create an account.",
                    )
                    return

                user = auth_repo.update_user(user.id, name=name, image=picture)
                if not user:
                    wx.CallAfter(self._show_error, "Failed to update user information.")
                    return

                account = auth_repo.get_account("google", google_id)

                if not account:
                    expires_at = None
                    if credentials.expiry:
                        expires_at = int(credentials.expiry.timestamp())

                    actual_scopes = (
                        " ".join(credentials.scopes)
                        if credentials.scopes
                        else " ".join(self.oauth_service.SCOPES)
                    )

                    account = auth_repo.create_account(
                        user_id=user.id,
                        provider="google",
                        provider_account_id=google_id,
                        access_token=credentials.token,
                        refresh_token=credentials.refresh_token,
                        expires_at=expires_at,
                        token_type="Bearer",
                        scope=actual_scopes,
                        id_token=(
                            credentials.id_token
                            if hasattr(credentials, "id_token")
                            else None
                        ),
                    )
                    if not account:
                        wx.CallAfter(self._show_error, "Failed to link Google account.")
                        return
                else:
                    expires_at = None
                    if credentials.expiry:
                        expires_at = int(credentials.expiry.timestamp())

                    account = auth_repo.update_account_tokens(
                        provider="google",
                        provider_account_id=google_id,
                        access_token=credentials.token,
                        refresh_token=credentials.refresh_token,
                        expires_at=expires_at,
                    )
                    if not account:
                        wx.CallAfter(
                            self._show_error, "Failed to update Google account tokens."
                        )
                        return

                session = auth_repo.create_session(user.id)
                if not session:
                    wx.CallAfter(self._show_error, "Failed to create session.")
                    return

                SessionManager.save_session(session.session_token, user)

                wx.CallAfter(self._on_success, user)

        except ValueError as ve:
            wx.CallAfter(self._show_error, str(ve))
        except Exception as e:
            logger.exception(f"Authentication error: {e}")
            wx.CallAfter(self._show_error, f"Authentication failed: {str(e)}")

    def _show_error(self, message: str):
        self.status_text.SetLabel(message)
        self.status_text.SetForegroundColour(wx.RED)
        self.google_button.Enable(True)

        wx.MessageBox(message, "Authentication Error", wx.OK | wx.ICON_ERROR)

    def _on_success(self, user: User):
        self.status_text.SetLabel("Login successful! Opening application...")
        self.status_text.SetForegroundColour(wx.Colour(0, 150, 0))

        self.Hide()
        self.on_login_success(user)
        self.Close()
