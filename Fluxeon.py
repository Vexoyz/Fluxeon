import sys
import os
from pathlib import Path
import requests
import subprocess
import shutil
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QProgressBar, QPushButton
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer

LOCALAPPDATA = os.getenv("LOCALAPPDATA")
FLUXEON_DIR = Path(LOCALAPPDATA) / "Fluxeon"
CLIENT_DIR = FLUXEON_DIR / "Client"
MODS_DIR = FLUXEON_DIR / "mods"
INSTALLER_PATH = FLUXEON_DIR / "RobloxPlayerLauncher.exe"

VERSION_URL = "https://setup.rbxcdn.com/version"
INSTALLER_URL_TEMPLATE = "https://setup.rbxcdn.com/{version}/RobloxPlayerLauncher.exe"

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

        self.latest_version = None
        self.local_version_file = CLIENT_DIR / "version.txt"

        self.start_update_process()

    def start_update_process(self):
        self.retry_button.setVisible(False)
        self.status_label.setText("Fetching latest Roblox version...")
        self.progress_bar.setValue(0)
        self.latest_version = None

        try:
            r = requests.get(VERSION_URL, timeout=10)
            r.raise_for_status()
            self.latest_version = r.text.strip()
            self.status_label.setText(f"Latest version: {self.latest_version}")
            self.check_local_version()
        except Exception as e:
            self.status_label.setText(f"Failed to get latest version: {e}")
            self.retry_button.setVisible(True)

    def check_local_version(self):
        if self.local_version_file.exists():
            local_version = self.local_version_file.read_text().strip()
        else:
            local_version = None

        if local_version == self.latest_version and (CLIENT_DIR / "RobloxPlayerBeta.exe").exists():
            self.status_label.setText("Client is up to date. Launching Roblox...")
            self.progress_bar.setValue(100)
            self.launch_roblox()
        else:
            self.status_label.setText("Updating Roblox client...")
            self.download_installer()

    def download_installer(self):
        url = INSTALLER_URL_TEMPLATE.format(version=self.latest_version)
        self.downloader = DownloaderThread(url, INSTALLER_PATH)
        self.downloader.progress_changed.connect(self.progress_bar.setValue)
        self.downloader.status_changed.connect(self.status_label.setText)
        self.downloader.finished.connect(self.on_download_finished)
        self.downloader.start()

    def on_download_finished(self, success: bool):
        if success:
            self.status_label.setText("Running installer silently...")
            self.run_installer()
        else:
            # Print more info to console for debugging
            print("Download failed. See above for details.")
            self.status_label.setText("Download failed. See console for details.")
            self.retry_button.setVisible(True)

    def run_installer(self):
        # Make sure Client directory exists
        CLIENT_DIR.mkdir(parents=True, exist_ok=True)

        # Run installer silently with target folder = CLIENT_DIR
        # Roblox installer supports /S for silent and /D=path for directory (no quotes)
        # Note: /D path must be the last argument

        installer_path_str = str(INSTALLER_PATH)
        install_dir_str = str(CLIENT_DIR)

        try:
            proc = subprocess.run([installer_path_str, "/S", f"/D={install_dir_str}"], check=True)
            # Write version file after successful install
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
