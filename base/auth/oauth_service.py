import json
import logging
import os
import secrets
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread
from typing import Optional
from urllib.parse import parse_qs, urlencode, urlparse

import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

logger = logging.getLogger(__name__)


class OAuthService:
    SCOPES = ["openid", "https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/userinfo.profile"]
    REDIRECT_URI = "http://localhost:8080/callback"

    def __init__(self):
        self.client_id = os.getenv("AUTH_GOOGLE_ID")
        self.client_secret = os.getenv("AUTH_GOOGLE_SECRET")

        if not self.client_id or not self.client_secret:
            raise ValueError("AUTH_GOOGLE_ID and AUTH_GOOGLE_SECRET must be set in environment variables")

        self.credentials: Optional[Credentials] = None
        self.user_info: Optional[dict] = None
        self._server: Optional[HTTPServer] = None
        self._auth_code: Optional[str] = None
        self._state: Optional[str] = None

    def authenticate(self) -> tuple[Optional[Credentials], Optional[dict]]:
        try:
            self._state = secrets.token_urlsafe(32)

            auth_params = {
                'client_id': self.client_id,
                'redirect_uri': self.REDIRECT_URI,
                'response_type': 'code',
                'scope': ' '.join(self.SCOPES),
                'access_type': 'offline',
                'state': self._state,
                'prompt': 'consent'
            }

            auth_url = f"https://accounts.google.com/o/oauth2/auth?{urlencode(auth_params)}"

            logger.info("Opening browser for Google authentication...")
            webbrowser.open(auth_url)

            self._start_callback_server()

            if not self._auth_code:
                logger.error("Failed to receive authorization code")
                return None, None

            token_data = {
                'code': self._auth_code,
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'redirect_uri': self.REDIRECT_URI,
                'grant_type': 'authorization_code'
            }

            token_response = requests.post(
                'https://oauth2.googleapis.com/token',
                data=token_data
            )
            token_response.raise_for_status()
            token_json = token_response.json()

            self.credentials = Credentials(
                token=token_json['access_token'],
                refresh_token=token_json.get('refresh_token'),
                token_uri='https://oauth2.googleapis.com/token',
                client_id=self.client_id,
                client_secret=self.client_secret,
                scopes=token_json.get('scope', ' '.join(self.SCOPES)).split()
            )

            self.user_info = self._fetch_user_info(self.credentials.token)

            return self.credentials, self.user_info

        except Exception as e:
            logger.exception(f"Authentication failed: {e}")
            return None, None

    def _start_callback_server(self):
        oauth_service = self

        class CallbackHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                query_components = parse_qs(urlparse(self.path).query)

                if 'code' in query_components and 'state' in query_components:
                    received_state = query_components['state'][0]

                    if received_state != oauth_service._state:
                        self.send_response(400)
                        self.send_header('Content-type', 'text/html')
                        self.end_headers()
                        self.wfile.write(b'<html><body><h1>Authentication Failed</h1><p>Invalid state parameter.</p></body></html>')
                        return

                    oauth_service._auth_code = query_components['code'][0]

                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    success_html = '''
                    <html>
                    <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                        <h1 style="color: #4CAF50;">Authentication Successful!</h1>
                        <p>You can close this window and return to the application.</p>
                        <script>window.close();</script>
                    </body>
                    </html>
                    '''
                    self.wfile.write(success_html.encode())
                else:
                    self.send_response(400)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(b'<html><body><h1>Authentication Failed</h1></body></html>')

            def log_message(self, format, *args):
                pass

        self._server = HTTPServer(('localhost', 8080), CallbackHandler)

        logger.info("Starting callback server on http://localhost:8080")
        self._server.handle_request()
        self._server.server_close()

    def _fetch_user_info(self, access_token: str) -> Optional[dict]:
        try:
            response = requests.get(
                'https://www.googleapis.com/oauth2/v2/userinfo',
                headers={'Authorization': f'Bearer {access_token}'}
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.exception(f"Failed to fetch user info: {e}")
            return None

    def refresh_credentials(self, credentials: Credentials) -> Optional[Credentials]:
        try:
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
                return credentials
            return credentials
        except Exception as e:
            logger.exception(f"Failed to refresh credentials: {e}")
            return None
