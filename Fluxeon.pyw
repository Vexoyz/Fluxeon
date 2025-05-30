import sys
import os
from pathlib import Path
import requests
import subprocess
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QProgressBar, QPushButton
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer

LOCALAPPDATA = os.getenv("LOCALAPPDATA")
FLUXEON_DIR = Path(LOCALAPPDATA) / "Fluxeon"
CLIENT_DIR = FLUXEON_DIR / "Client"
INSTALLER_PATH = FLUXEON_DIR / "RobloxInstaller.exe"

VERSION_API_URL = "https://clientsettingscdn.roblox.com/v2/client-version/WindowsPlayer"
INSTALLER_URL = "https://www.roblox.com/download/client"

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
            headers = {"User-Agent": "Mozilla/5.0"}
            self.status_changed.emit("Starting download...")
            with requests.get(self.url, stream=True, headers=headers) as r:
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
            print("Download failed:", e)
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

        self.local_version_file = CLIENT_DIR / "version.txt"

        self.start_update_process()

    def start_update_process(self):
        self.retry_button.setVisible(False)
        self.status_label.setText("Fetching latest Roblox version...")
        self.progress_bar.setValue(0)

        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            r = requests.get(VERSION_API_URL, timeout=10, headers=headers)
            r.raise_for_status()
            data = r.json()
            self.latest_version = data.get("clientVersionUpload", "unknown")
            self.status_label.setText(f"Latest version: {self.latest_version}")
            self.download_installer()
        except Exception as e:
            self.status_label.setText(f"Failed to get latest version: {e}")
            self.retry_button.setVisible(True)

    def download_installer(self):
        self.downloader = DownloaderThread(INSTALLER_URL, INSTALLER_PATH)
        self.downloader.progress_changed.connect(self.progress_bar.setValue)
        self.downloader.status_changed.connect(self.status_label.setText)
        self.downloader.finished.connect(self.on_download_finished)
        self.downloader.start()

    def on_download_finished(self, success: bool):
        if success:
            self.status_label.setText("Running installer...")
            self.run_installer()
        else:
            self.status_label.setText("Download failed. See console for details.")
            self.retry_button.setVisible(True)

    def run_installer(self):
        CLIENT_DIR.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run([str(INSTALLER_PATH), "/silent"], check=True)
            self.local_version_file.write_text(self.latest_version)
            self.status_label.setText("Installation complete. Launching Roblox...")
            self.launch_roblox()
        except subprocess.CalledProcessError as e:
            self.status_label.setText(f"Installer failed: {e}")
            self.retry_button.setVisible(True)

    def launch_roblox(self):
        player_exe = CLIENT_DIR / "RobloxPlayerBeta.exe"
        if not player_exe.exists():
            self.status_label.setText("RobloxPlayerBeta.exe not found after install.")
            self.retry_button.setVisible(True)
            return

        try:
            subprocess.Popen([str(player_exe), self.launch_uri])
            self.status_label.setText("Roblox launched successfully!")
            self.retry_button.setVisible(False)
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
