import sys
import os
import zipfile
import requests
import subprocess
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QProgressBar,
    QPushButton, QMessageBox, QHBoxLayout
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
import winreg

# --- Config ---
LOCALAPPDATA = os.getenv("LOCALAPPDATA")
FLUXEON_DIR = Path(LOCALAPPDATA) / "Fluxeon"
CLIENT_DIR = FLUXEON_DIR / "Client"
MODS_DIR = FLUXEON_DIR / "mods"
VERSION_FILE = CLIENT_DIR / "version.txt"

# Roblox CDN URLs
VERSION_API_URL = "https://clientsettingscdn.roblox.com/v2/client-version/WindowsPlayer"
MANIFEST_URL_TEMPLATE = "https://setup.rbxcdn.com/channel/LIVE/version-{guid}-rbxPkgManifest.txt"
CDN_URL_TEMPLATE      = "https://setup.rbxcdn.com/version-{guid}-{filename}"

# Protocol registry
PROTOCOL_NAME = "roblox-player"
REGISTRY_PATH = f"Software\\Classes\\{PROTOCOL_NAME}"

class InstallerThread(QThread):
    progress_changed = pyqtSignal(int)
    status_changed = pyqtSignal(str)
    finished = pyqtSignal(bool)

    def run(self):
        try:
            self.status_changed.emit("Fetching latest version...")
            headers = {"User-Agent": "Mozilla/5.0"}
            r = requests.get(VERSION_API_URL, timeout=10, headers=headers)
            r.raise_for_status()
            data = r.json()
            guid = data.get("clientVersionUpload")
            self.status_changed.emit(f"Version: {guid}")

            # Check existing
            if VERSION_FILE.exists() and VERSION_FILE.read_text().strip() == guid:
                self.status_changed.emit("Client up to date.")
                self.finished.emit(True)
                return

            # Fetch manifest
            manifest_url = MANIFEST_URL_TEMPLATE.format(guid=guid)
            self.status_changed.emit("Downloading manifest...")
            r = requests.get(manifest_url, headers=headers)
            r.raise_for_status()
            parts = r.text.strip().split()
            # package names are every 4th item starting at index 1
            filenames = parts[1::4]

            # Download & extract
            total = len(filenames)
            CLIENT_DIR.mkdir(parents=True, exist_ok=True)
            for idx, fname in enumerate(filenames, start=1):
                self.status_changed.emit(f"Downloading {fname}...")
                url = CDN_URL_TEMPLATE.format(guid=guid, filename=fname)
                resp = requests.get(url, stream=True, headers=headers)
                resp.raise_for_status()
                zip_path = CLIENT_DIR / fname
                with open(zip_path, 'wb') as f:
                    for chunk in resp.iter_content(8192):
                        if chunk:
                            f.write(chunk)
                # extract
                with zipfile.ZipFile(zip_path, 'r') as z:
                    z.extractall(CLIENT_DIR)
                zip_path.unlink()
                pct = int(idx * 100 / total)
                self.progress_changed.emit(pct)

            # write version
            VERSION_FILE.write_text(guid)
            self.status_changed.emit("Install complete.")
            self.finished.emit(True)
        except Exception as e:
            self.status_changed.emit(f"Error: {e}")
            self.finished.emit(False)

class FluxeonUpdater(QWidget):
    def __init__(self, launch_uri=None):
        super().__init__()
        self.launch_uri = launch_uri
        self.setWindowTitle("Fluxeon Bootstrapper")
        self.setFixedSize(400, 180)

        layout = QVBoxLayout()
        self.label = QLabel("Ready")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label)

        self.bar = QProgressBar()
        self.bar.setValue(0)
        layout.addWidget(self.bar)

        self.btn = QPushButton("Install / Update Roblox")
        self.btn.clicked.connect(self.start_install)
        layout.addWidget(self.btn)

        self.retry = QPushButton("Retry")
        self.retry.clicked.connect(self.start_install)
        self.retry.setVisible(False)
        layout.addWidget(self.retry)

        self.setLayout(layout)

    def start_install(self):
        self.btn.setEnabled(False)
        self.retry.setVisible(False)
        self.thread = InstallerThread()
        self.thread.progress_changed.connect(self.bar.setValue)
        self.thread.status_changed.connect(self.label.setText)
        self.thread.finished.connect(self.on_finished)
        self.bar.setValue(0)
        self.thread.start()

    def on_finished(self, ok):
        if ok:
            self.label.setText("Launching Roblox…")
            exe = CLIENT_DIR / "RobloxPlayerBeta.exe"
            if exe.exists() and self.launch_uri:
                subprocess.Popen([str(exe), self.launch_uri])
                QTimer.singleShot(2000, self.close)
        else:
            self.retry.setVisible(True)
        self.btn.setEnabled(True)

    def setup_registry(self):
        # same as before if needed
        pass

if __name__ == "__main__":
    # parse -player arg
    uri = None
    if len(sys.argv) >= 3 and sys.argv[1] == "-player":
        uri = sys.argv[2]
    app = QApplication(sys.argv)
    w = FluxeonUpdater(uri)
    w.show()
    sys.exit(app.exec())
