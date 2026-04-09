import logging
import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

import requests

from base.__version__ import __version__

logger = logging.getLogger(__name__)


class AutoUpdater:
    REPO_OWNER = "ntholi"
    REPO_NAME = "registry-desktop"
    GITHUB_API_URL = (
        f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"
    )

    def __init__(self):
        self.current_version = __version__
        self.latest_version: Optional[str] = None
        self.download_url: Optional[str] = None
        self.release_notes: Optional[str] = None
        self.last_error: Optional[str] = None

    def check_for_updates(self) -> bool:
        self.latest_version = None
        self.download_url = None
        self.release_notes = None
        self.last_error = None

        try:
            logger.info(
                f"Checking for updates (current version: {self.current_version})..."
            )

            response = requests.get(self.GITHUB_API_URL, timeout=10)
            response.raise_for_status()

            release_data = response.json()
            self.latest_version = release_data.get("tag_name", "").lstrip("v")
            self.release_notes = release_data.get("body", "")

            assets = release_data.get("assets", [])

            if platform.system() == "Windows":
                for asset in assets:
                    if asset["name"].endswith(".exe"):
                        self.download_url = asset["browser_download_url"]
                        break
            elif platform.system() == "Darwin":
                for asset in assets:
                    if asset["name"].endswith(".dmg") or asset["name"].endswith(
                        ".app.zip"
                    ):
                        self.download_url = asset["browser_download_url"]
                        break
            elif platform.system() == "Linux":
                for asset in assets:
                    if asset["name"].endswith(".AppImage") or asset["name"].endswith(
                        ".tar.gz"
                    ):
                        self.download_url = asset["browser_download_url"]
                        break

            if not self.download_url:
                self.last_error = f"No suitable download found for {platform.system()}"
                logger.warning(self.last_error)
                return False

            has_update = self._compare_versions(
                self.current_version, self.latest_version
            )

            if has_update:
                logger.info(f"New version available: {self.latest_version}")
            else:
                logger.info("Application is up to date")

            return has_update

        except requests.RequestException as e:
            self.last_error = f"Failed to check for updates: {e}"
            logger.error(self.last_error)
            return False
        except Exception as e:
            self.last_error = f"Unexpected error checking for updates: {e}"
            logger.exception(self.last_error)
            return False

    def _compare_versions(self, current: str, latest: str | None) -> bool:
        if latest is None:
            return False
        try:
            current_parts = [int(x) for x in current.split(".")]
            latest_parts = [int(x) for x in latest.split(".")]

            for i in range(max(len(current_parts), len(latest_parts))):
                current_part = current_parts[i] if i < len(current_parts) else 0
                latest_part = latest_parts[i] if i < len(latest_parts) else 0

                if latest_part > current_part:
                    return True
                elif latest_part < current_part:
                    return False

            return False
        except (ValueError, AttributeError):
            logger.error(f"Failed to compare versions: {current} vs {latest}")
            return False

    def download_and_install_update(self, progress_callback=None) -> bool:
        self.last_error = None

        if not self.download_url:
            self.last_error = "No download URL available"
            logger.error(self.last_error)
            return False

        try:
            logger.info(f"Downloading update from {self.download_url}...")

            response = requests.get(self.download_url, stream=True, timeout=30)
            response.raise_for_status()

            total_size = int(response.headers.get("content-length", 0))
            downloaded = 0

            file_extension = Path(self.download_url).suffix
            temp_file = tempfile.NamedTemporaryFile(
                delete=False, suffix=file_extension, prefix="registry_update_"
            )

            with temp_file as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

                        if progress_callback and total_size > 0:
                            progress = int((downloaded / total_size) * 100)
                            progress_callback(progress, downloaded, total_size)

            temp_file_path = temp_file.name
            logger.info(f"Update downloaded to {temp_file_path}")

            if platform.system() == "Windows":
                self._install_windows_update(temp_file_path)
            elif platform.system() == "Darwin":
                self._install_macos_update(temp_file_path)
            elif platform.system() == "Linux":
                self._install_linux_update(temp_file_path)

            return True

        except requests.RequestException as e:
            self.last_error = f"Failed to download update: {e}"
            logger.error(self.last_error)
            return False
        except Exception as e:
            self.last_error = f"Unexpected error during update: {e}"
            logger.exception(self.last_error)
            return False

    def _install_windows_update(self, installer_path: str):
        logger.info("Starting Windows installer...")

        current_executable = Path(sys.executable).resolve()

        if (
            getattr(sys, "frozen", False)
            and current_executable.suffix.lower() == ".exe"
        ):
            script_content = self._build_windows_update_script(
                installer_path,
                str(current_executable),
                os.getpid(),
            )

            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=".cmd",
                prefix="registry_update_",
                mode="w",
                encoding="utf-8",
                newline="\r\n",
            ) as script_file:
                script_file.write(script_content)
                script_path = script_file.name

            creationflags = 0
            if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
                creationflags |= subprocess.CREATE_NEW_PROCESS_GROUP
            if hasattr(subprocess, "DETACHED_PROCESS"):
                creationflags |= subprocess.DETACHED_PROCESS
            if hasattr(subprocess, "CREATE_NO_WINDOW"):
                creationflags |= subprocess.CREATE_NO_WINDOW

            subprocess.Popen(
                ["cmd.exe", "/c", script_path], creationflags=creationflags
            )
            os._exit(0)
            return

        subprocess.Popen([installer_path])
        os._exit(0)
        return

    def _build_windows_update_script(
        self,
        source_path: str,
        target_path: str,
        process_id: int,
    ) -> str:
        lines = [
            "@echo off",
            "setlocal",
            f'set "SOURCE={source_path}"',
            f'set "TARGET={target_path}"',
            f'set "PID={process_id}"',
            ":wait_for_exit",
            'tasklist /FI "PID eq %PID%" 2>NUL | find /I "%PID%" >NUL',
            "if not errorlevel 1 (",
            "    timeout /t 1 /nobreak >NUL",
            "    goto wait_for_exit",
            ")",
            'move /Y "%SOURCE%" "%TARGET%" >NUL',
            "if errorlevel 1 (",
            '    start "" "%SOURCE%"',
            "    exit /b 1",
            ")",
            'start "" "%TARGET%"',
        ]
        return "\r\n".join(lines) + "\r\n"

    def _install_macos_update(self, installer_path: str):
        logger.info("Opening macOS installer...")
        subprocess.Popen(["open", installer_path])
        os._exit(0)

    def _install_linux_update(self, installer_path: str):
        logger.info("Starting Linux installer...")

        os.chmod(installer_path, 0o755)
        subprocess.Popen([installer_path])
        os._exit(0)

    def get_latest_version(self) -> Optional[str]:
        return self.latest_version

    def get_release_notes(self) -> Optional[str]:
        return self.release_notes

    def get_last_error(self) -> Optional[str]:
        return self.last_error
