# Fluxeon Bootstrapper
# Version: 1.0.3
# https://raw.githubusercontent.com/Vexoyz/Fluxeon/main/Fluxeon.pyw

FLUXEON_VERSION = "1.0.3" # Updated version

import sys
import os
from pathlib import Path
import requests
import subprocess
import shutil
import zipfile
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QProgressBar, QPushButton, QMessageBox
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QIcon, QPixmap, QColor, QPalette
from PyQt6.QtWidgets import QHBoxLayout, QSizePolicy, QSpacerItem
from PyQt6.QtCore import QSize
import threading
import re
import platform
import hashlib
import time # For sleep

# --- WebView2 detection and install helpers ---
def is_webview2_installed():
    """Check if WebView2 runtime is installed by checking registry keys."""
    try:
        import winreg
        keys = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"),
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}")
        ]
        for root, path in keys:
            try:
                with winreg.OpenKey(root, path):
                    return True
            except FileNotFoundError:
                continue
    except Exception as e:
        print(f"[WARN] Could not check WebView2 registry: {e}")
    return False

def install_webview2_runtime(client_dir: Path):
    """Extract and run WebView2 installer if not installed."""
    installer_zip = DOWNLOADS_DIR / "WebView2RuntimeInstaller.zip"
    installer_dir = client_dir / "WebView2Runtime"
    installer_exe = installer_dir / "MicrosoftEdgeWebview2Setup.exe"
    if not installer_zip.exists():
        print("[WARN] WebView2RuntimeInstaller.zip not found, skipping WebView2 install.")
        return
    try:
        if not installer_dir.exists():
            installer_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(installer_zip, 'r') as zip_ref:
            zip_ref.extractall(installer_dir)
        if installer_exe.exists():
            print("[INFO] Running WebView2 installer...")
            subprocess.run([str(installer_exe), "/silent", "/install"], cwd=installer_dir, timeout=120)
            print("[INFO] WebView2 installer finished.")
        else:
            print("[WARN] WebView2 installer exe not found after extraction.")
    except Exception as e:
        print(f"[ERROR] Failed to install WebView2: {e}")
    try:
        if installer_dir.exists():
            shutil.rmtree(installer_dir)
    except Exception as e:
        print(f"[WARN] Could not clean up WebView2 installer dir: {e}")

LOCALAPPDATA = os.getenv("LOCALAPPDATA")
FLUXEON_DIR = Path(LOCALAPPDATA) / "Fluxeon"
CLIENT_DIR = FLUXEON_DIR / "Client"
DOWNLOADS_DIR = FLUXEON_DIR / "Downloads"

VERSION_API_URL = "https://clientsettingscdn.roblox.com/v2/client-version/WindowsPlayer"
BASE_URLS = [
    "https://setup.rbxcdn.com",
    "https://setup-aws.rbxcdn.com",
    "https://setup-ak.rbxcdn.com",
    "https://roblox-setup.cachefly.net",
    "https://s3.amazonaws.com/setup.roblox.com"
]
VERSION_STUDIO_HASH = "version-012732894899482c"
FLUXEON_MAIN_SCRIPT_URL = "https://raw.githubusercontent.com/Vexoyz/Fluxeon/main/Fluxeon.pyw"

FLUXEON_USER_AGENT = f"Fluxeon/{FLUXEON_VERSION} ({platform.system()} {platform.release()})"

TARGETED_DOWNLOAD_HEADERS = {
    'User-Agent': FLUXEON_USER_AGENT,
    'Connection': 'keep-alive',
}
http_session = requests.Session()
http_session.headers.clear()
http_session.headers.update(TARGETED_DOWNLOAD_HEADERS)

PACKAGE_DIRECTORY_MAP = {
    "RobloxApp.zip": "",
    "RobloxStudioApp.zip": "",
    "content-avatar.zip": "content/avatar",
    "content-configs.zip": "content/configs",
    "content-fonts.zip": "content/fonts",
    "content-models.zip": "content/models",
    "content-particles.zip": "content/particles",
    "content-sky.zip": "content/sky",
    "content-sounds.zip": "content/sounds",
    "content-music.zip": "content/music",
    "content-textures.zip": "content/textures",
    "content-textures2.zip": "content/textures",
    "content-textures3.zip": "content/textures",
    "content-terrain.zip": "content/terrain",
    "content-translations.zip": "content/translations",
    "content-materials.zip": "PlatformContent/pc/materials",
    "platform-content-pc-fonts.zip": "PlatformContent/pc/fonts",
    "content-platform-fonts.zip": "PlatformContent/pc/fonts",
    "content-platform-dictionaries.zip": "PlatformContent/pc/dictionaries",
    "content-scripts.zip": "PlatformContent/pc/scripts",
    "content-shaders.zip": "PlatformContent/pc/shaders",
    "luapackages.zip": "ExtraContent/LuaPackages",
    "extracontent-avatar.zip": "ExtraContent/avatar",
    "extracontent-configs.zip": "ExtraContent/configs",
    "extracontent-debugging.zip": "ExtraContent/debugging",
    "extracontent-models.zip": "ExtraContent/models",
    "extracontent-scripts.zip": "ExtraContent/scripts",
    "extracontent-sounds.zip": "ExtraContent/sounds",
    "extracontent-textures.zip": "ExtraContent/textures",
    "extracontent-translations.zip": "ExtraContent/translations",
    "extracontent-luapackages.zip": "ExtraContent/LuaPackages",
    "extracontent-qtwebengine.zip": "ExtraContent/qtwebengine",
    "extracontent-qml.zip": "ExtraContent/qml",
    "extracontent-places.zip": "ExtraContent/places",
    "shaders.zip": "shaders",
    "ssl.zip": "ssl",
    "WebView2RuntimeInstaller.zip": "WebView2Runtime",
    "WebView2.zip": "WebView2Runtime",
    "ApplicationStyle.zip": "ApplicationStyle",
    "RobloxCrashHandler.zip": "",
    "redist.zip": "",
    "RobloxPlayerLauncher.exe": ""
}


class LaunchModes:
    PLAYER_URI = "player_uri"
    MENU = "menu"
    CHOICE = "choice"
    ERROR = "error"
    LAUNCH_APP = "launch_app"

def kill_roblox_processes():
    """Attempts to terminate running Roblox player and launcher processes."""
    processes_to_kill = ["RobloxPlayerBeta.exe", "RobloxPlayerLauncher.exe", "RobloxCrashHandler.exe"]
    killed_any = False
    for process_name in processes_to_kill:
        try:
            if platform.system() == "Windows":
                # Using check=False so we don't raise an exception if process not found
                # timeout parameter added in Python 3.5 for subprocess.run
                try:
                    result = subprocess.run(
                        ["taskkill", "/F", "/IM", process_name], 
                        capture_output=True, text=True, check=False, timeout=5
                    )
                    if result.returncode == 0:
                        print(f"[INFO] Terminated running process: {process_name}")
                        killed_any = True
                    elif result.returncode == 128: # Process not found
                        print(f"[INFO] Process not found (already closed?): {process_name}")
                    else: # Other error codes (e.g., access denied to kill)
                        print(f"[WARN] `taskkill` for {process_name} exited with code {result.returncode}: {result.stderr.strip() or result.stdout.strip()}")
                except subprocess.TimeoutExpired:
                    print(f"[WARN] `taskkill` for {process_name} timed out.")
                except FileNotFoundError: # taskkill not found
                    print(f"[WARN] `taskkill` command not found. Cannot terminate {process_name}.")
                    break # No point trying other processes if taskkill isn't there
            # Add elif for other OS if needed
        except Exception as e:
            print(f"[WARN] Error trying to terminate {process_name}: {e}")
    
    if killed_any:
        print("[INFO] Waiting 2 seconds for processes to fully terminate and release file locks...")
        time.sleep(2) # Blocking sleep, assumes this is acceptable before lengthy file ops

def find_working_base_url():
    for url in BASE_URLS:
        try:
            resp = http_session.get(f"{url}/versionStudio", timeout=10)
            if resp.status_code == 200 and resp.text.strip() == VERSION_STUDIO_HASH:
                print(f"[DEBUG] Using base URL: {url}")
                return url
        except requests.exceptions.RequestException as e:
            print(f"Network error checking base URL {url}: {e}")
        except Exception as e:
            print(f"Unexpected error checking base URL {url}: {e}")
    print("[ERROR] No working base URL found.")
    return None

def calculate_md5(file_path: Path):
    hash_md5 = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except FileNotFoundError:
        print(f"[ERROR] File not found for MD5 calculation: {file_path}")
    except Exception as e:
        print(f"[ERROR] Could not calculate MD5 for {file_path}: {e}")
    return None


class DownloaderThread(QThread):
    progress_changed = pyqtSignal(int)
    status_changed = pyqtSignal(str)
    finished = pyqtSignal(bool, Path)

    def __init__(self, url: str, save_path: Path, package_name: str = "File"):
        super().__init__()
        self.url = url
        self.save_path = save_path
        self.package_name = package_name

    def run(self):
        try:
            self.status_changed.emit(f"Downloading: {self.package_name}...")
            DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
            with http_session.get(self.url, stream=True, timeout=300) as r:
                r.raise_for_status()
                total_length = r.headers.get('content-length')
                if total_length is None:
                    self.save_path.write_bytes(r.content)
                    self.progress_changed.emit(100)
                else:
                    total_length = int(total_length)
                    chunk_size = 8192 * 4
                    downloaded = 0
                    with open(self.save_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=chunk_size):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                percent = int(downloaded * 100 / total_length) if total_length > 0 else 0
                                self.progress_changed.emit(percent)
            self.finished.emit(True, self.save_path)
        except requests.exceptions.HTTPError as http_err:
            error_message = f"HTTP error ({http_err.response.status_code}) downloading {self.package_name}"
            print(f"[ERROR] {error_message}: {http_err.request.url}")
            print(f"[ERROR] Response: {http_err.response.text[:200]}")
            if http_err.response.status_code == 403:
                self.status_changed.emit(f"Download failed (403 Forbidden): {self.package_name}. Try VPN or wait.")
            else:
                self.status_changed.emit(f"Download failed ({http_err.response.status_code}): {self.package_name}")
            self.finished.emit(False, self.save_path)
        except requests.exceptions.RequestException as req_err:
            print(f"[ERROR] Request error downloading {self.package_name}: {req_err}")
            self.status_changed.emit(f"Download failed (Network error): {self.package_name}")
            self.finished.emit(False, self.save_path)
        except Exception as e:
            print(f"[ERROR] General error downloading {self.package_name}: {e}")
            import traceback
            traceback.print_exc()
            self.status_changed.emit(f"Download failed ({type(e).__name__}): {self.package_name}")
            self.finished.emit(False, self.save_path)


class FluxeonUpdater(QWidget):
    def __init__(self, launch_uri: str = None, launch_target_is_launcher: bool = True):
        super().__init__()
        self.launch_uri = launch_uri
        self.launch_target_is_launcher = launch_target_is_launcher

        # --- Modern UI Styling ---
        self.setWindowTitle(f"Fluxeon Bootstrapper v{FLUXEON_VERSION}")
        self.setFixedSize(480, 260)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.setStyleSheet("""
            QWidget {
                background: #23272e;
                color: #f5f6fa;
                font-family: 'Segoe UI', 'Arial', sans-serif;
                font-size: 15px;
            }
            QLabel#HeaderLabel {
                font-size: 22px;
                font-weight: bold;
                color: #00b894;
                margin-bottom: 8px;
            }
            QLabel#StatusLabel {
                font-size: 15px;
                font-weight: 500;
                color: #f5f6fa;
            }
            QLabel#ProgressLabel {
                font-size: 13px;
                color: #b2bec3;
            }
            QProgressBar {
                border: 1px solid #636e72;
                border-radius: 8px;
                background: #2d3436;
                height: 22px;
                text-align: center;
                font-size: 13px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00b894, stop:1 #0984e3);
                border-radius: 8px;
            }
            QPushButton {
                background: #00b894;
                color: #fff;
                border: none;
                border-radius: 7px;
                padding: 7px 18px;
                font-size: 15px;
                font-weight: 500;
                margin-top: 10px;
            }
            QPushButton:hover {
                background: #0984e3;
            }
        """)

        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(28, 22, 28, 22)

        # Header area with icon and title
        header_layout = QHBoxLayout()
        # Placeholder for logo/icon (replace with your own QPixmap if available)
        icon_label = QLabel()
        icon_pix = QPixmap(48, 48)
        icon_pix.fill(QColor("#00b894"))
        icon_label.setPixmap(icon_pix)
        icon_label.setFixedSize(48, 48)
        header_layout.addWidget(icon_label)
        header_title = QLabel("Fluxeon Bootstrapper")
        header_title.setObjectName("HeaderLabel")
        header_layout.addWidget(header_title)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Status label
        self.status_label = QLabel("Checking for updates...")
        self.status_label.setObjectName("StatusLabel")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        # Progress label
        self.package_progress_label = QLabel("")
        self.package_progress_label.setObjectName("ProgressLabel")
        self.package_progress_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.package_progress_label.setWordWrap(True)
        layout.addWidget(self.package_progress_label)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)

        # Retry button
        self.retry_button = QPushButton("Retry")
        self.retry_button.clicked.connect(self.start_update_process)
        self.retry_button.setVisible(False)
        layout.addWidget(self.retry_button)

        # Spacer to push content up
        layout.addItem(QSpacerItem(20, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        self.setLayout(layout)

        self.latest_version_id = None
        self.local_version_file = CLIENT_DIR / "version.txt"
        self.base_url = None
        self.package_manifest = []
        self.current_package_index = 0
        self.downloaded_package_paths = []

        FLUXEON_DIR.mkdir(parents=True, exist_ok=True)
        DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

        # Always show window immediately, then start update process
        QTimer.singleShot(0, self.start_update_process)

    def start_update_process(self):
        self.retry_button.setVisible(False)
        self.status_label.setText("Checking for updates...")
        self.status_label.setStyleSheet("color: #00b894;")
        self.package_progress_label.setText("")
        self.progress_bar.setValue(0)
        self.latest_version_id = None
        self.package_manifest = []
        self.current_package_index = 0
        self.downloaded_package_paths = []

        FLUXEON_DIR.mkdir(parents=True, exist_ok=True)
        DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

        def find_url_and_continue():
            self.base_url = find_working_base_url()
            if not self.base_url:
                QTimer.singleShot(0, lambda: self.status_label.setText("Error: No working Roblox CDN found."))
                QTimer.singleShot(0, lambda: self.status_label.setStyleSheet("color: #d63031;"))
                QTimer.singleShot(0, lambda: self.package_progress_label.setText("Check internet or firewall. Then Retry."))
                QTimer.singleShot(0, lambda: self.retry_button.setVisible(True))
                return
            QTimer.singleShot(0, self.fetch_latest_version)
        threading.Thread(target=find_url_and_continue, daemon=True).start()

    def fetch_latest_version(self):
        self.status_label.setText("Checking for latest Roblox version...")
        self.status_label.setStyleSheet("color: #00b894;")
        self.package_progress_label.setText("")
        self.progress_bar.setValue(0)
        try:
            r = http_session.get(VERSION_API_URL, timeout=10)
            r.raise_for_status()
            data = r.json()
            version_upload = data.get("clientVersionUpload", "")
            if not version_upload:
                raise ValueError("Client version (clientVersionUpload) not found or empty in API response.")
            self.latest_version_id = version_upload

            self.status_label.setText(f"Roblox Version: {self.latest_version_id}")
            self.status_label.setStyleSheet("color: #00b894;")
            self.check_local_version()
        except Exception as e:
            self.status_label.setText(f"Failed to get latest Roblox version.")
            self.status_label.setStyleSheet("color: #d63031;")
            self.package_progress_label.setText(str(e))
            self.retry_button.setVisible(True)

    def check_local_version(self):
        CLIENT_DIR.mkdir(parents=True, exist_ok=True)
        local_version = None
        if self.local_version_file.exists():
            try:
                local_version = self.local_version_file.read_text().strip()
            except Exception as e:
                print(f"[WARN] Error reading local version file '{self.local_version_file}': {e}")

        core_app_exe_path = CLIENT_DIR / "RobloxPlayerBeta.exe"
        expected_subdir_path = CLIENT_DIR / "content"

        if local_version == self.latest_version_id and core_app_exe_path.exists() and expected_subdir_path.exists() and expected_subdir_path.is_dir():
            self.status_label.setText("Roblox is already up to date.")
            self.status_label.setStyleSheet("color: #00b894;")
            self.package_progress_label.setText("Starting Roblox...")
            self.progress_bar.setValue(100)
            QTimer.singleShot(1000, self.launch_roblox)
        else:
            if local_version != self.latest_version_id:
                self.status_label.setText(f"New Roblox version available.")
                self.status_label.setStyleSheet("color: #0984e3;")
                self.package_progress_label.setText(f"Updating from {local_version or 'None'} to {self.latest_version_id}...")
            elif not core_app_exe_path.exists() or not expected_subdir_path.exists():
                self.status_label.setText("Roblox client files seem incomplete.")
                self.status_label.setStyleSheet("color: #fdcb6e;")
                self.package_progress_label.setText(f"Re-installing version {self.latest_version_id}...")
            QTimer.singleShot(0, self.fetch_package_manifest)


    def fetch_package_manifest(self):
        # ... (This method is the same as in the previous corrected response, starting with the manifest_url definition) ...
        if not self.base_url or not self.latest_version_id:
            self.status_label.setText("Error: Cannot fetch manifest.")
            self.package_progress_label.setText("Missing base URL or version ID. Please retry.")
            self.retry_button.setVisible(True)
            return

        self.status_label.setText(f"Roblox Version: {self.latest_version_id}")
        self.package_progress_label.setText("Fetching package manifest...")
        self.progress_bar.setValue(0)
        manifest_url = f"{self.base_url}/{self.latest_version_id}-rbxPkgManifest.txt"
        
        try:
            print(f"[DEBUG] Fetching manifest: {manifest_url}")
            resp = http_session.get(manifest_url, timeout=20)
            resp.raise_for_status()
            manifest_content = resp.text.strip()
            
            print(f"[DEBUG] Raw Manifest Content (first 500 chars):\n{manifest_content[:500]}...")

            lines = manifest_content.splitlines()
            self.package_manifest = []

            if not lines:
                raise ValueError("Manifest is empty after splitting lines.")

            manifest_format_version_str = lines.pop(0).strip()
            print(f"[DEBUG] Manifest format version string: '{manifest_format_version_str}'")
            
            manifest_format_code = -1 
            if manifest_format_version_str.lower().startswith("v"):
                try:
                    manifest_format_code = int(manifest_format_version_str[1:])
                except ValueError:
                    print(f"[WARN] Could not parse int from manifest version '{manifest_format_version_str}'. Assuming v1-style.")
                    manifest_format_code = 1
            else:
                print(f"[WARN] First line '{manifest_format_version_str}' is not 'vX'. Prepending and assuming v1-style.")
                lines.insert(0, manifest_format_version_str)
                manifest_format_code = 1

            file_count_from_manifest = 0
            if lines and lines[0].strip().isdigit():
                file_count_str = lines.pop(0).strip()
                try:
                    file_count_from_manifest = int(file_count_str)
                    print(f"[DEBUG] Manifest reported file count: {file_count_from_manifest}")
                except ValueError:
                    print(f"[WARN] Could not parse file count from '{file_count_str}'. Adding back as data.")
                    lines.insert(0, file_count_str)
            
            current_line_idx = 0
            if manifest_format_code == 0:
                print("[DEBUG] Parsing manifest as v0 format.")
                while current_line_idx + 3 < len(lines): # Need 4 lines for a v0 package
                    pkg_name = lines[current_line_idx].strip()
                    pkg_hash = lines[current_line_idx + 1].strip()
                    pkg_packed_size_str = lines[current_line_idx + 2].strip()
                    # pkg_uncompressed_size_str = lines[current_line_idx + 3].strip() # We don't use this field

                    if not pkg_name or not pkg_hash or not pkg_packed_size_str.isdigit():
                        print(f"[WARN] Invalid v0 entry at data line {current_line_idx}. Name='{pkg_name}', Hash='{pkg_hash}', SizeStr='{pkg_packed_size_str}'. Skipping.")
                        current_line_idx += 4 # Skip the 4 lines for this presumed bad entry
                        continue
                    
                    pkg_packed_size = int(pkg_packed_size_str)
                    pkg_url = f"{self.base_url}/{self.latest_version_id}-{pkg_name}"
                    self.package_manifest.append({'name': pkg_name, 'hash': pkg_hash, 'packed_size': pkg_packed_size, 'url': pkg_url})
                    current_line_idx += 4
                if current_line_idx < len(lines): # Check for leftover lines not forming a full package
                     print(f"[WARN] Trailing lines in v0 manifest data ({len(lines) - current_line_idx} lines remaining): {lines[current_line_idx:]}")

            elif manifest_format_code >= 1: # Handles v1 and any future vX as comma-separated
                if manifest_format_code > 1: print(f"[WARN] Manifest v{manifest_format_code}, parsing as v1-style (comma-separated).")
                else: print("[DEBUG] Parsing manifest as v1-style (comma-separated).")

                for line_content in lines[current_line_idx:]: # Process all remaining lines (if any)
                    line_content = line_content.strip()
                    if not line_content: continue # Skip empty lines

                    parts = line_content.split(',')
                    # Expect at least: Name, Hash, PackedSize. UncompressedSize is optional 4th.
                    if len(parts) >= 3: 
                        pkg_name = parts[0].strip()
                        pkg_hash = parts[1].strip()
                        pkg_packed_size_str = parts[2].strip()

                        if not pkg_name or not pkg_hash or not pkg_packed_size_str.isdigit():
                            print(f"[WARN] Invalid v1-style package line: '{line_content}'. Malformed data (name, hash, or size). Skipping.")
                            continue
                        
                        pkg_packed_size = int(pkg_packed_size_str)
                        pkg_url = f"{self.base_url}/{self.latest_version_id}-{pkg_name}"
                        self.package_manifest.append({'name': pkg_name, 'hash': pkg_hash, 'packed_size': pkg_packed_size, 'url': pkg_url})
                    else:
                        print(f"[WARN] Malformed v1-style package line (not enough comma-separated parts): '{line_content}'. Skipping.")
            else:
                # This case should ideally not be reached if the logic above correctly defaults.
                print(f"[ERROR] Unknown manifest_format_code '{manifest_format_code}' derived from version string '{manifest_format_version_str}'. No parsing strategy applied after version/count lines.")


            if not self.package_manifest: # After attempting parsing, check if we got anything
                raise ValueError("Package manifest parsing yielded no packages. Manifest might be malformed or unexpectedly empty after header lines.")

            print(f"[DEBUG] Manifest parsed. {len(self.package_manifest)} packages will be processed.")
            self.package_progress_label.setText(f"Found {len(self.package_manifest)} packages for version {self.latest_version_id}.")
            self.current_package_index = 0
            self.downloaded_package_paths = []
            self.download_next_package()

        except requests.exceptions.HTTPError as http_err:
            self.status_label.setText(f"Manifest fetch failed (HTTP {http_err.response.status_code}).")
            self.package_progress_label.setText("Roblox version might not be available on CDN yet.")
            print(f"Error fetching manifest from {manifest_url}: {http_err}")
            self.retry_button.setVisible(True)
        except Exception as e:
            self.status_label.setText(f"Failed to process package manifest: {type(e).__name__}")
            self.package_progress_label.setText(str(e)) # Show the error message
            print(f"Error during manifest processing: {e}")
            import traceback
            traceback.print_exc()
            self.retry_button.setVisible(True)

    def download_next_package(self):
        if self.current_package_index >= len(self.package_manifest):
            self.on_all_packages_downloaded()
            return

        package_info = self.package_manifest[self.current_package_index]
        package_name = package_info['name']
        package_url = package_info['url']
        package_expected_hash = package_info['hash']
        
        save_path = DOWNLOADS_DIR / package_name

        self.package_progress_label.setText(f"Downloading ({self.current_package_index + 1}/{len(self.package_manifest)}): {package_name}")
        self.progress_bar.setValue(0)

        if save_path.exists() and package_expected_hash:
            local_hash = calculate_md5(save_path)
            if local_hash and local_hash.lower() == package_expected_hash.lower():
                print(f"[DEBUG] Package {package_name} found with matching hash. Skipping download.")
                self.on_single_package_download_finished(True, save_path)
                return
            else:
                print(f"[DEBUG] {package_name} exists but hash mismatch (local:{local_hash}, expected:{package_expected_hash}) or error. Re-downloading.")
                try: save_path.unlink()
                except OSError as e: print(f"[WARN] Could not delete existing {save_path}: {e}")
        
        if package_name.lower().endswith(".exe"):
            print(f"[INFO] Package '{package_name}' is an executable. Will be moved to client root after download.")

        self.downloader = DownloaderThread(package_url, save_path, package_name)
        self.downloader.progress_changed.connect(self.progress_bar.setValue)
        self.downloader.finished.connect(self.on_single_package_download_finished)
        self.downloader.start()

    def on_single_package_download_finished(self, success: bool, downloaded_file_path: Path):
        if success:
            package_info = self.package_manifest[self.current_package_index]
            package_expected_hash = package_info['hash']
            package_name = package_info['name']

            if package_expected_hash:
                actual_hash = calculate_md5(downloaded_file_path)
                if not actual_hash or actual_hash.lower() != package_expected_hash.lower():
                    msg = f"MD5 mismatch for {package_name}.\nExpected: {package_expected_hash}, Got: {actual_hash or 'Error'}.\nFile corrupt. Please retry."
                    self.status_label.setText("Download Verification Failed")
                    self.package_progress_label.setText(msg)
                    print(f"[ERROR] {msg}")
                    self.retry_button.setVisible(True)
                    if downloaded_file_path.exists(): downloaded_file_path.unlink(missing_ok=True)
                    return
                print(f"[DEBUG] MD5 verified for {package_name}")
            
            self.downloaded_package_paths.append(downloaded_file_path)
            self.current_package_index += 1
            self.download_next_package()
        else:
            self.retry_button.setVisible(True)

    def on_all_packages_downloaded(self):
        self.status_label.setText("All packages downloaded.")
        self.package_progress_label.setText("Starting extraction process...")
        self.progress_bar.setValue(0)
        QTimer.singleShot(100, self.extract_all_packages)

    def extract_all_packages(self):
        self.package_progress_label.setText("Preparing for extraction...")
        self.progress_bar.setValue(0)
        QApplication.processEvents()

        try:
            print("[INFO] Attempting to terminate any existing Roblox processes...")
            kill_roblox_processes() # KILL ROBLOX PROCESSES BEFORE SHUTIL.RMTREE

            if CLIENT_DIR.exists():
                print(f"[DEBUG] Cleaning up old client directory: {CLIENT_DIR}")
                shutil.rmtree(CLIENT_DIR)
            CLIENT_DIR.mkdir(parents=True, exist_ok=True)
            print(f"[DEBUG] Created client directory: {CLIENT_DIR}")

            total_packages = len(self.downloaded_package_paths)
            for i, package_path in enumerate(self.downloaded_package_paths):
                package_name = package_path.name
                self.package_progress_label.setText(f"Processing ({i+1}/{total_packages}): {package_name}")
                self.progress_bar.setValue(int(((i+1) / total_packages) * 100) if total_packages > 0 else 0)
                QApplication.processEvents()

                if package_name.lower().endswith(".exe"):
                    target_exe_path = CLIENT_DIR / package_name
                    print(f"[DEBUG] Moving executable {package_name} to {target_exe_path}")
                    try:
                        shutil.move(str(package_path), str(target_exe_path))
                    except Exception as e_move:
                        self.status_label.setText(f"Error moving {package_name}: {type(e_move).__name__}")
                        self.package_progress_label.setText(str(e_move))
                        self.retry_button.setVisible(True)
                        return
                    continue

                if package_name.lower().endswith(".zip"):
                    target_relative_dir_str = PACKAGE_DIRECTORY_MAP.get(package_name)
                    if target_relative_dir_str is None:
                        print(f"[WARN] No mapping for package '{package_name}'. Extracting to CLIENT_DIR root.")
                        target_extract_path = CLIENT_DIR
                    elif target_relative_dir_str == "":
                        target_extract_path = CLIENT_DIR
                    else:
                        target_extract_path = CLIENT_DIR / target_relative_dir_str
                    
                    print(f"[DEBUG] Extracting ZIP {package_name} to {target_extract_path}")
                    target_extract_path.mkdir(parents=True, exist_ok=True)

                    try:
                        with zipfile.ZipFile(package_path, 'r') as zip_ref:
                            zip_ref.extractall(target_extract_path)
                    except zipfile.BadZipFile as bzf_error:
                        self.status_label.setText(f"Extraction failed for {package_name}: Corrupt ZIP.")
                        self.package_progress_label.setText(f"Error: {bzf_error}")
                        if package_path.exists(): package_path.unlink(missing_ok=True)
                        self.retry_button.setVisible(True)
                        return
                    except Exception as e_zip:
                        self.status_label.setText(f"Extraction error for {package_name}.")
                        self.package_progress_label.setText(f"Error: {type(e_zip).__name__} - {e_zip}")
                        import traceback; traceback.print_exc()
                        self.retry_button.setVisible(True)
                        return
                else:
                    print(f"[WARN] Don't know how to process non-ZIP/non-EXE package: {package_name}. It will remain in downloads.")

            if not self.latest_version_id:
                 raise ValueError("latest_version_id is not set before writing version file.")
            self.local_version_file.write_text(self.latest_version_id)
            
            try:
                if DOWNLOADS_DIR.exists():
                    print(f"[DEBUG] Cleaning up downloads directory: {DOWNLOADS_DIR}")
                    for item in DOWNLOADS_DIR.iterdir():
                        try:
                            if item.is_file(): item.unlink()
                            elif item.is_dir(): shutil.rmtree(item)
                        except Exception as e_del_item:
                             print(f"[WARN] Could not delete item {item} from downloads: {e_del_item}")
            except Exception as e_clean:
                print(f"[WARN] Could not fully clean downloads directory: {e_clean}")

            self.status_label.setText("Roblox client updated successfully!")
            self.package_progress_label.setText("Launching...")
            self.progress_bar.setValue(100)

            # --- WebView2 check and install ---
            if not is_webview2_installed():
                self.status_label.setText("Installing WebView2 Runtime...")
                self.package_progress_label.setText("WebView2 is required for Roblox. Installing now...")
                QApplication.processEvents()
                install_webview2_runtime(CLIENT_DIR)
                if is_webview2_installed():
                    self.package_progress_label.setText("WebView2 installed successfully.")
                else:
                    self.package_progress_label.setText("WebView2 installation failed or was skipped.")
                QApplication.processEvents()
            # --- End WebView2 check ---

            QTimer.singleShot(100, self.launch_roblox)
        except PermissionError as pe: # Catch PermissionError specifically
            self.status_label.setText("Client update process failed.")
            self.package_progress_label.setText(f"Error: PermissionError - {pe.strerror}. File: {pe.filename}")
            print(f"[ERROR] PermissionError during extraction: {pe}")
            self.retry_button.setVisible(True)
        except Exception as e:
            self.status_label.setText("Client update process failed.")
            self.package_progress_label.setText(f"Error: {type(e).__name__} - {e}")
            import traceback; traceback.print_exc()
            self.retry_button.setVisible(True)


    def launch_roblox(self):
        args_list = []
        player_exe_name = "RobloxPlayerBeta.exe" 
        
        if self.launch_target_is_launcher:
            player_exe_name = "RobloxPlayerLauncher.exe"
            if not self.launch_uri:
                self.status_label.setText("Error: Launch URI required.")
                self.package_progress_label.setText(f"Cannot launch {player_exe_name} without URI.")
                self.retry_button.setVisible(True)
                return
            args_list = [str(CLIENT_DIR / player_exe_name), self.launch_uri]
        else:
            args_list = [str(CLIENT_DIR / player_exe_name)]
            if self.launch_uri:
                 args_list.append(self.launch_uri)

        player_exe_path = CLIENT_DIR / player_exe_name
        if not player_exe_path.exists():
            self.status_label.setText(f"Error: {player_exe_name} not found.")
            self.package_progress_label.setText(f"Path: {player_exe_path}. Update may be incomplete.")
            self.retry_button.setVisible(True)
            return

        try:
            print(f"[DEBUG] Launching: {' '.join(args_list)}")
            creation_flags = 0
            if platform.system() == "Windows":
                creation_flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)
            subprocess.Popen(args_list, creationflags=creation_flags)
            self.package_progress_label.setText(f"{player_exe_name} launched!")
            self.retry_button.setVisible(False)
            # --- Show menu after launching Roblox ---
            QTimer.singleShot(1500, self.show_menu_and_close)
        except Exception as e:
            self.status_label.setText(f"Failed to launch {player_exe_name}.")
            self.package_progress_label.setText(f"Error: {e}")
            print(f"[ERROR] Launch failed: {e}")
            self.retry_button.setVisible(True)

    def show_menu_and_close(self):
        self.close()
        self.menu_window = FluxeonMenuWindow()
        self.menu_window.show()

class FluxeonMenuWindow(QWidget):
    # ... (Same as before) ...
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Fluxeon Menu v{FLUXEON_VERSION}")
        self.setFixedSize(350, 200)
        self.updater_window = None 
        layout = QVBoxLayout()
        label = QLabel(f"Fluxeon Control Panel\nVersion: {FLUXEON_VERSION}\n(More features coming soon!)")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter); label.setWordWrap(True)
        layout.addWidget(label)
        launch_roblox_button = QPushButton("Launch Roblox App")
        launch_roblox_button.setToolTip("Checks for Roblox updates then launches RobloxPlayerBeta.exe.")
        launch_roblox_button.clicked.connect(self.launch_roblox_app_from_menu)
        layout.addWidget(launch_roblox_button)
        self.setLayout(layout)

    def launch_roblox_app_from_menu(self):
        if self.updater_window and self.updater_window.isVisible():
            self.updater_window.activateWindow() 
            return
        self.hide() 
        self.updater_window = FluxeonUpdater(launch_uri=None, launch_target_is_launcher=True)
        self.updater_window.show()

def get_version_from_source(source: str) -> str | None:
    # ... (Same as before) ...
    match = re.search(r'FLUXEON_VERSION\s*=\s*["\']([^"\']+)["\']', source)
    return match.group(1) if match else None

def auto_update():
    # ... (Same as before, ensure FLUXEON_MAIN_SCRIPT_URL is correct) ...
    script_path = Path(__file__)
    is_writable_location = os.access(script_path.parent, os.W_OK)
    is_frozen = getattr(sys, 'frozen', False)

    if not is_writable_location or is_frozen:
        if is_frozen: print(f"Fluxeon running as frozen executable. Skipping self-update.")
        else: print(f"Fluxeon script directory '{script_path.parent}' not writable. Skipping self-update.")
        return

    print(f"Current Fluxeon version: {FLUXEON_VERSION}.")
    try:
        resp = http_session.get(FLUXEON_MAIN_SCRIPT_URL, timeout=10) 
        resp.raise_for_status()
        remote_source = resp.text
        remote_version_str = get_version_from_source(remote_source)

        if remote_version_str:
            print(f"Remote Fluxeon version: {remote_version_str}")
            
            current_parts = list(map(int, FLUXEON_VERSION.split('.')))
            remote_parts = list(map(int, remote_version_str.split('.')))
            
            max_len = max(len(current_parts), len(remote_parts))
            current_parts.extend([0] * (max_len - len(current_parts)))
            remote_parts.extend([0] * (max_len - len(remote_parts)))

            if remote_parts > current_parts:
                print(f"Updating Fluxeon: {FLUXEON_VERSION} -> {remote_version_str}")
                temp_script_path = script_path.with_suffix(script_path.suffix + ".flux_tmp")
                try:
                    temp_script_path.write_text(remote_source, encoding="utf-8")
                    backup_path = None # Initialize to avoid NameError if first rename fails
                    try:
                        if script_path.exists():
                            backup_path = script_path.with_suffix(script_path.suffix + ".bak")
                            if backup_path.exists(): backup_path.unlink(missing_ok=True) # missing_ok for Python 3.8+
                            script_path.rename(backup_path)
                        shutil.move(str(temp_script_path), str(script_path))
                        print("Fluxeon updated. Restarting...")
                        QApplication.quit() 
                        os.execv(sys.executable, [sys.executable] + sys.argv) 
                    except Exception as move_err:
                        print(f"Error replacing script (manual restart may be needed): {move_err}")
                        if backup_path and backup_path.exists() and not script_path.exists():
                            backup_path.rename(script_path) # Try to restore
                except Exception as write_err:
                    print(f"Error writing Fluxeon update: {write_err}")
                    if 'temp_script_path' in locals() and temp_script_path.exists(): temp_script_path.unlink(missing_ok=True)
            else:
                print("Fluxeon is up to date.")
        else:
            print("Could not determine remote Fluxeon version from script source.")
    except requests.exceptions.RequestException as e:
        print(f"Fluxeon self-update check failed (Network): {e}")
    except Exception as e:
        print(f"Fluxeon self-update failed (General): {e}")
        import traceback
        traceback.print_exc()


def determine_launch_mode_and_data():
    # ... (Same as before) ...
    args = sys.argv
    if "-menu" in args: return LaunchModes.MENU, None
    uri_arg = None
    try: 
        player_arg_index = args.index("-player")
        if player_arg_index + 1 < len(args):
            uri_arg = args[player_arg_index + 1]
    except ValueError: 
        if len(args) == 2 and args[1].startswith("roblox-player:"):
            uri_arg = args[1]

    if uri_arg:
        if not ("roblox-player:" in uri_arg and any(kw in uri_arg for kw in ["launchmode:play", "gameinfo:", "launchmode:plugin", "taskid:"])):
            print(f"Warning: Launch argument '{uri_arg}' may not be a standard Roblox game/plugin URI.")
        return LaunchModes.PLAYER_URI, uri_arg
    
    if len(args) == 1: return LaunchModes.CHOICE, None
    
    error_message = ("Unrecognized arguments.\n\nSupported options:\n"
                     "  (no arguments)         - Show choice dialog\n"
                     "  -menu                  - Open Fluxeon Menu\n"
                     "  -player <launch_uri>   - Launch Roblox game via URI\n"
                     "  <launch_uri>           - (If only arg) Launch via URI")
    return LaunchModes.ERROR, error_message


if __name__ == "__main__":
    # ... (Logging setup same as before) ...
    if not getattr(sys, 'frozen', False):
        log_dir = FLUXEON_DIR / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file_path = log_dir / "fluxeon_bootstrapper.log"
        try:
            if log_file_path.exists():
                backup_log_path = log_dir / "fluxeon_bootstrapper.log.bak"
                if backup_log_path.exists(): backup_log_path.unlink(missing_ok=True)
                log_file_path.rename(backup_log_path)

            sys.stdout = open(log_file_path, 'w', encoding='utf-8', buffering=1) # Line buffering
            sys.stderr = sys.stdout
            print(f"--- Fluxeon Bootstrapper v{FLUXEON_VERSION} Log Start ({time.asctime()}) ---")
            print(f"Python Version: {sys.version}")
            print(f"Platform: {platform.system()} {platform.release()}")
            print(f"Arguments: {sys.argv}")
            print(f"Current Working Directory: {Path.cwd()}")
            print(f"Script Path: {Path(__file__).resolve() if '__file__' in globals() else 'N/A (frozen or interactive?)'}")

        except Exception as e:
            # If logging fails, print to original stderr and continue
            sys.stderr.write(f"Error setting up logging: {e}\n")


    exit_code_val = 0 
    try:
        auto_update() 
    except Exception as e:
        print(f"[ERROR] During auto_update process: {e}")

    app = QApplication(sys.argv)
    mode, data = determine_launch_mode_and_data()
    print(f"[INFO] Determined launch mode: {mode}, Data: {data}")
    main_window = None

    if mode == LaunchModes.ERROR:
        print(f"[ERROR] Argument error: {data}")
        QMessageBox.critical(None, "Fluxeon Argument Error", str(data))
        exit_code_val = 1
    elif mode == LaunchModes.PLAYER_URI:
        # Always show the FluxeonUpdater window, even if up to date, before launching Roblox
        main_window = FluxeonUpdater(launch_uri=str(data), launch_target_is_launcher=True)
        # Show menu after updater finishes (handled in FluxeonUpdater)
    elif mode == LaunchModes.MENU:
        main_window = FluxeonMenuWindow()
    elif mode == LaunchModes.CHOICE:
        dialog = QMessageBox(QMessageBox.Icon.Question, "Fluxeon Choice", "How would you like to proceed?")
        btn_launch_app = dialog.addButton("Launch Roblox App", QMessageBox.ButtonRole.YesRole)
        btn_open_menu = dialog.addButton("Open Fluxeon Menu", QMessageBox.ButtonRole.NoRole)
        btn_cancel = dialog.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        dialog.exec()
        
        clicked_button = dialog.clickedButton()
        if clicked_button == btn_launch_app:
            # Always show the FluxeonUpdater window, even if up to date
            main_window = FluxeonUpdater(launch_uri=None, launch_target_is_launcher=True)
            # Show menu after updater finishes (handled in FluxeonUpdater)
        elif clicked_button == btn_open_menu:
            main_window = FluxeonMenuWindow()
        else: 
            main_window = None 
            exit_code_val = 0 
    else: 
        msg = f"Internal error: Unhandled launch mode '{mode}'."
        print(f"[ERROR] {msg}")
        QMessageBox.critical(None, "Fluxeon Internal Error", msg)
        main_window = None
        exit_code_val = 1
        
    if main_window:
        main_window.show()
        exit_code_val = app.exec()
    elif exit_code_val == 0 and mode not in [LaunchModes.PLAYER_URI, LaunchModes.MENU, LaunchModes.CHOICE]:
         if mode != LaunchModes.ERROR: # Don't print warning if it was already an error handled.
            print("[WARN] No main window shown and no explicit choice made to exit. This might be an unhandled state or silent operation.")

    print(f"[INFO] Fluxeon exiting with code: {exit_code_val}")
    http_session.close() 
    if hasattr(sys.stdout, 'close') and not getattr(sys.stdout, 'closed', True) and sys.stdout is not sys.__stdout__:
        print(f"--- Fluxeon Bootstrapper Log End ({time.asctime()}) ---")
        sys.stdout.close()
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
    sys.exit(exit_code_val)
