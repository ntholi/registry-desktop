import logging
import os
import platform
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import requests

from base.__version__ import __version__

logger = logging.getLogger(__name__)


class AutoUpdater:
    REPO_OWNER = "ntholi"
    REPO_NAME = "registry-desktop"
    GITHUB_API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"

    def __init__(self):
        self.current_version = __version__
        self.latest_version: Optional[str] = None
        self.download_url: Optional[str] = None
        self.release_notes: Optional[str] = None

    def check_for_updates(self) -> bool:
        try:
            logger.info(f"Checking for updates (current version: {self.current_version})...")

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
                    if asset["name"].endswith(".dmg") or asset["name"].endswith(".app.zip"):
                        self.download_url = asset["browser_download_url"]
                        break
            elif platform.system() == "Linux":
                for asset in assets:
                    if asset["name"].endswith(".AppImage") or asset["name"].endswith(".tar.gz"):
                        self.download_url = asset["browser_download_url"]
                        break

            if not self.download_url:
                logger.warning(f"No suitable download found for {platform.system()}")
                return False

            has_update = self._compare_versions(self.current_version, self.latest_version)

            if has_update:
                logger.info(f"New version available: {self.latest_version}")
            else:
                logger.info("Application is up to date")

            return has_update

        except requests.RequestException as e:
            logger.error(f"Failed to check for updates: {e}")
            return False
        except Exception as e:
            logger.exception(f"Unexpected error checking for updates: {e}")
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
        if not self.download_url:
            logger.error("No download URL available")
            return False

        try:
            logger.info(f"Downloading update from {self.download_url}...")

            response = requests.get(self.download_url, stream=True, timeout=30)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0

            file_extension = Path(self.download_url).suffix
            temp_file = tempfile.NamedTemporaryFile(
                delete=False,
                suffix=file_extension,
                prefix="registry_update_"
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
            logger.error(f"Failed to download update: {e}")
            return False
        except Exception as e:
            logger.exception(f"Unexpected error during update: {e}")
            return False

    def _install_windows_update(self, installer_path: str):
        logger.info("Starting Windows installer...")
        subprocess.Popen([installer_path], shell=True)
        os._exit(0)

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
