import sys
import os
from pathlib import Path
import requests
import subprocess
import shutil
import zipfile
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QProgressBar, QPushButton
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
import threading

LOCALAPPDATA = os.getenv("LOCALAPPDATA")
FLUXEON_DIR = Path(LOCALAPPDATA) / "Fluxeon"
CLIENT_DIR = FLUXEON_DIR / "Client"
MODS_DIR = FLUXEON_DIR / "mods"
ZIP_PATH = FLUXEON_DIR / "RobloxApp.zip"

VERSION_API_URL = "https://clientsettingscdn.roblox.com/v2/client-version/WindowsPlayer"
ZIP_URL_TEMPLATE = "https://setup.rbxcdn.com/{version_id}-RobloxApp.zip"

BASE_URLS = [
    "https://setup.rbxcdn.com",
    "https://setup-aws.rbxcdn.com",
    "https://setup-ak.rbxcdn.com",
    "https://roblox-setup.cachefly.net",
    "https://s3.amazonaws.com/setup.roblox.com"
]
VERSION_STUDIO_HASH = "version-012732894899482c"

def find_working_base_url():
    """
    Returns the first working base url, or None if all fail.
    """
    for url in BASE_URLS:
        try:
            resp = requests.get(f"{url}/versionStudio", timeout=5)
            if resp.status_code == 200 and resp.text.strip() == VERSION_STUDIO_HASH:
                return url
        except Exception:
            continue
    return None

class DownloaderThread(QThread):
    progress_changed = pyqtSignal(int)
    status_changed = pyqtSignal(str)
    finished = pyqtSignal(bool)

    def __init__(self, url: str, save_path: Path):
        super().__init__()
        self.url = url
        self.save_path = save_path

    def run(self):
        try:
            self.status_changed.emit("Starting download...")
            with requests.get(self.url, stream=True) as r:
                r.raise_for_status()
                total_length = r.headers.get('content-length')
                if total_length is None:
                    self.save_path.write_bytes(r.content)
                    self.progress_changed.emit(100)
                else:
                    total_length = int(total_length)
                    chunk_size = 8192
                    downloaded = 0
                    with open(self.save_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=chunk_size):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                percent = int(downloaded * 100 / total_length)
                                self.progress_changed.emit(percent)
            self.status_changed.emit("Download complete.")
            self.finished.emit(True)
        except Exception as e:
            import traceback
            print("Download failed:", e)
            traceback.print_exc()
            self.status_changed.emit(f"Download failed: {e}")
            self.finished.emit(False)

class FluxeonUpdater(QWidget):
    def __init__(self, launch_uri: str):
        super().__init__()
        self.launch_uri = launch_uri
        self.setWindowTitle("Fluxeon Bootstrapper")
        self.setFixedSize(400, 150)

        layout = QVBoxLayout()
        self.status_label = QLabel("Initializing...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.retry_button = QPushButton("Retry")
        self.retry_button.clicked.connect(self.start_update_process)
        self.retry_button.setVisible(False)
        layout.addWidget(self.retry_button)

        self.setLayout(layout)

        self.latest_version_id = None
        self.local_version_file = CLIENT_DIR / "version.txt"
        self.base_url = None

        self.start_update_process()

    def start_update_process(self):
        self.retry_button.setVisible(False)
        self.status_label.setText("Finding optimal download server...")
        self.progress_bar.setValue(0)
        self.latest_version_id = None

        # Find working base url in a thread to avoid UI freeze
        def find_url_and_continue():
            self.base_url = find_working_base_url()
            if not self.base_url:
                self.status_label.setText("No working Roblox CDN found.")
                self.retry_button.setVisible(True)
                return
            QTimer.singleShot(0, self.fetch_latest_version)

        threading.Thread(target=find_url_and_continue, daemon=True).start()

    def fetch_latest_version(self):
        self.status_label.setText("Fetching latest Roblox version...")
        try:
            r = requests.get(VERSION_API_URL, timeout=10)
            r.raise_for_status()
            data = r.json()
            version_upload = data.get("clientVersionUpload", "")
            if version_upload.startswith("version-"):
                self.latest_version_id = version_upload[len("version-") :]
            else:
                self.latest_version_id = version_upload
            self.status_label.setText(f"Latest version: {self.latest_version_id}")
            self.check_local_version()
        except Exception as e:
            self.status_label.setText(f"Failed to get latest version: {e}")
            self.retry_button.setVisible(True)

    def check_local_version(self):
        if self.local_version_file.exists():
            local_version = self.local_version_file.read_text().strip()
        else:
            local_version = None

        if local_version == self.latest_version_id and (CLIENT_DIR / "RobloxPlayerBeta.exe").exists():
            self.status_label.setText("Client is up to date. Launching Roblox...")
            self.progress_bar.setValue(100)
            self.launch_roblox()
        else:
            self.status_label.setText("Updating Roblox client...")
            self.download_zip()

    def download_zip(self):
        # Use the working base url
        url = f"{self.base_url}/{self.latest_version_id}-RobloxApp.zip"
        self.downloader = DownloaderThread(url, ZIP_PATH)
        self.downloader.progress_changed.connect(self.progress_bar.setValue)
        self.downloader.status_changed.connect(self.status_label.setText)
        self.downloader.finished.connect(self.on_zip_download_finished)
        self.downloader.start()

    def on_zip_download_finished(self, success: bool):
        if success:
            self.status_label.setText("Extracting client files...")
            QTimer.singleShot(100, self.extract_zip)
        else:
            # Print more info to console for debugging
            print("Download failed. See above for details.")
            self.status_label.setText("Download failed. See console for details.")
            self.retry_button.setVisible(True)

    def extract_zip(self):
        try:
            # Ensure client dir exists and is empty
            if CLIENT_DIR.exists():
                shutil.rmtree(CLIENT_DIR)
            CLIENT_DIR.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(ZIP_PATH, 'r') as zip_ref:
                zip_ref.extractall(CLIENT_DIR)
            # Write version file after successful extraction
            self.local_version_file.write_text(self.latest_version_id)
            self.status_label.setText("Extraction complete. Launching Roblox...")
            self.launch_roblox()
        except Exception as e:
            self.status_label.setText(f"Extraction failed: {e}")
            self.retry_button.setVisible(True)

    def launch_roblox(self):
        player_exe = CLIENT_DIR / "RobloxPlayerBeta.exe"
        if not player_exe.exists():
            self.status_label.setText("RobloxPlayerBeta.exe not found after install.")
            self.retry_button.setVisible(True)
            return

        # Launch RobloxPlayerBeta.exe with the original launch URI as argument
        try:
            subprocess.Popen([str(player_exe), self.launch_uri])
            self.status_label.setText("Roblox launched successfully!")
            self.retry_button.setVisible(False)
            # Close the bootstrapper UI after launching
            QTimer.singleShot(2000, self.close)
        except Exception as e:
            self.status_label.setText(f"Failed to launch Roblox: {e}")
            self.retry_button.setVisible(True)

def parse_args():
    if len(sys.argv) < 3 or sys.argv[1] != "-player":
        print("Usage: Fluxeon.py -player <launch_uri>")
        sys.exit(1)
    return sys.argv[2]

if __name__ == "__main__":
    launch_uri = parse_args()
    app = QApplication(sys.argv)
    window = FluxeonUpdater(launch_uri)
    window.show()
    sys.exit(app.exec())
