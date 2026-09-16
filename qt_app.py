#!/usr/bin/env python3
"""Qt 6 interface for the Spotify playlist downloader."""

import sys
import threading
import webbrowser
from pathlib import Path

from PySide6.QtCore import QObject, QThread, QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from main import (
    CLIENT_ID,
    CLIENT_SECRET,
    REDIRECT_URI,
    SLEEP,
    download,
    get_track,
    get_tracks,
    playlist_id,
    safe_name,
    spotify_auth_required,
    spotify_authorization_url,
    spotify_client,
    tag,
    track_id,
)


class FormDialog(QDialog):
    def __init__(self, title, description, fields, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(description))
        form = QFormLayout()
        self.entries = {}
        for name, secret in fields:
            entry = QLineEdit()
            entry.setPlaceholderText(name)
            entry.setEchoMode(QLineEdit.Password if secret else QLineEdit.Normal)
            form.addRow(name, entry)
            self.entries[name] = entry
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self):
        return {name: entry.text().strip() for name, entry in self.entries.items()}

    def accept(self):
        values = self.values()
        if any(not value for value in values.values()):
            QMessageBox.warning(self, "Missing information", "All fields are required.")
            return
        super().accept()


class DownloadWorker(QObject):
    finished = Signal(str, bool)
    log = Signal(str)
    progress = Signal(int, int, str, float, str)
    api_status = Signal(object, object)

    def __init__(self, mode, source, output, credentials, redirect_url):
        super().__init__()
        self.mode = mode
        self.source = source
        self.output = output
        self.credentials = credentials
        self.redirect_url = redirect_url

    def run(self):
        try:
            self.log.emit("Connecting to Spotify...")
            client_id, client_secret = self.credentials
            client = spotify_client(
                client_id,
                client_secret,
                REDIRECT_URI,
                self.redirect_url,
                self.api_status.emit,
            )
            if self.mode == "song":
                track = get_track(client, track_id(self.source))
                name, owner, tracks = track["title"], ", ".join(track["artists"]), [track]
            else:
                name, owner, tracks = get_tracks(client, playlist_id(self.source))
            if not tracks:
                self.finished.emit("Playlist is empty or no tracks found.", True)
                return

            destination = self.output if self.mode == "song" else self.output / safe_name(name)
            destination.mkdir(parents=True, exist_ok=True)
            failed = []
            total = len(tracks)
            self.log.emit(f"{name} by {owner} - {total} track(s)")

            for index, track in enumerate(tracks, 1):
                label = f"{', '.join(track['artists'])} - {track['title']}"
                filename = safe_name(label)
                self.log.emit(f"[{index}/{total}] {label}")
                if self.mode == "metadata":
                    mp3 = destination / f"{filename}.mp3"
                    self.progress.emit(index, total, label, 1.0, "metadata")
                else:
                    mp3 = download(
                        track,
                        destination,
                        lambda status: self._progress(index, total, label, status),
                    )
                if self.mode == "metadata" and not mp3.exists():
                    self.log.emit(f"Metadata skipped; MP3 not found: {mp3.name}")
                    failed.append(label)
                elif mp3:
                    tag(mp3, track)
                    self.log.emit(f"Saved: {mp3.name}")
                else:
                    failed.append(label)
                    self.log.emit(f"Failed: {label}")
                if index < total:
                    threading.Event().wait(SLEEP)

            summary = f"Finished: {total - len(failed)}/{total} tracks saved to {destination}"
            if failed:
                summary += f" ({len(failed)} failed)"
            self.finished.emit(summary, True)
        except Exception as error:
            self.finished.emit(f"Error: {error}", False)

    def _progress(self, index, total, label, status):
        downloaded = status.get("downloaded_bytes", 0)
        total_bytes = status.get("total_bytes") or status.get("total_bytes_estimate")
        fraction = downloaded / total_bytes if total_bytes else 0
        speed = status.get("speed")
        speed_text = f"{speed / 1024 / 1024:.1f} MiB/s" if speed else status.get("status", "downloading")
        self.progress.emit(index, total, label, fraction, speed_text)


class DownloaderWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Spotify Downloader - Qt 6")
        self.resize(820, 680)
        self.credentials = (CLIENT_ID, CLIENT_SECRET) if CLIENT_ID and CLIENT_SECRET else None
        self.thread = None
        self.worker = None

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(28, 24, 28, 24)

        nav = QHBoxLayout()
        root.addLayout(nav)
        self.pages = QStackedWidget()
        self.entries = {}
        for mode, title, placeholder, description in (
            ("playlist", "Download playlist", "Spotify playlist URL or ID", "Download every track in a playlist."),
            ("song", "Download song", "Spotify track URL or ID", "Download one song as an MP3."),
            ("metadata", "Get metadata", "Spotify playlist URL or ID", "Tag existing playlist MP3 files only."),
        ):
            button = QPushButton(title)
            button.clicked.connect(lambda checked=False, index=self.pages.count(): self.pages.setCurrentIndex(index))
            nav.addWidget(button)
            page = QWidget()
            page_layout = QVBoxLayout(page)
            heading = QLabel(title)
            heading.setStyleSheet("font-size: 20px; font-weight: 600;")
            page_layout.addWidget(heading)
            page_layout.addWidget(QLabel(description))
            entry = QLineEdit()
            entry.setPlaceholderText(placeholder)
            page_layout.addWidget(entry)
            self.entries[mode] = entry
            self.pages.addWidget(page)
        about_button = QPushButton("About")
        about_button.clicked.connect(lambda: self.pages.setCurrentIndex(3))
        nav.addWidget(about_button)

        about = QWidget()
        about_layout = QVBoxLayout(about)
        about_layout.addWidget(QLabel("Spotify Downloader\nCreated by YSherbo"))
        site = QPushButton("ysherbo.github.io")
        site.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://ysherbo.github.io")))
        about_layout.addWidget(site, alignment=Qt.AlignLeft)
        self.pages.addWidget(about)
        root.addWidget(self.pages)

        output_row = QHBoxLayout()
        output_row.addWidget(QLabel("Save to"))
        self.output_entry = QLineEdit(str(Path.cwd() / "downloads"))
        output_row.addWidget(self.output_entry)
        browse = QPushButton("Browse")
        browse.clicked.connect(self.choose_folder)
        output_row.addWidget(browse)
        root.addLayout(output_row)

        self.download_button = QPushButton("Download")
        self.download_button.clicked.connect(self.start_download)
        root.addWidget(self.download_button)
        self.status = QLabel("Ready")
        root.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        root.addWidget(self.progress)
        self.api_status = QLabel("API requests remaining: checking...")
        root.addWidget(self.api_status)
        self.log_view = QTextEdit(readOnly=True)
        root.addWidget(self.log_view, stretch=1)

        if not self.credentials:
            self.prompt_credentials()

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose download folder")
        if folder:
            self.output_entry.setText(folder)

    def prompt_credentials(self):
        dialog = FormDialog(
            "Spotify credentials",
            "Enter your Spotify application credentials.",
            [("Client ID", False), ("Client secret", True)],
            self,
        )
        if dialog.exec() == QDialog.Accepted:
            values = dialog.values()
            self.credentials = (values["Client ID"], values["Client secret"])

    def prompt_redirect(self):
        dialog = FormDialog(
            "Spotify redirect URL",
            "Authorize Spotify in your browser, then paste the complete redirected URL.",
            [("Redirect URL", False)],
            self,
        )
        return dialog.values()["Redirect URL"] if dialog.exec() == QDialog.Accepted else None

    def start_download(self):
        if self.thread and self.thread.isRunning():
            return
        mode = ("playlist", "song", "metadata", "about")[self.pages.currentIndex()]
        if mode == "about":
            return
        source = self.entries[mode].text().strip()
        output = Path(self.output_entry.text().strip()).expanduser()
        if not source or not str(output):
            QMessageBox.warning(self, "Missing information", "Enter a source and output folder.")
            return
        if not self.credentials:
            self.prompt_credentials()
        if not self.credentials:
            return
        try:
            client_id, client_secret = self.credentials
            redirect_url = None
            if spotify_auth_required(client_id, client_secret, REDIRECT_URI):
                webbrowser.open(spotify_authorization_url(client_id, client_secret, REDIRECT_URI))
                redirect_url = self.prompt_redirect()
                if not redirect_url:
                    return
        except Exception as error:
            self.show_error(str(error))
            return

        self.set_busy(True)
        self.log_view.clear()
        self.thread = QThread()
        self.worker = DownloadWorker(mode, source, output, self.credentials, redirect_url)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.log.connect(self.log_view.append)
        self.worker.progress.connect(self.update_progress)
        self.worker.api_status.connect(self.update_api_status)
        self.worker.finished.connect(self.download_finished)
        self.worker.finished.connect(self.thread.quit)
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def set_busy(self, busy):
        self.download_button.setEnabled(not busy)
        self.progress.setVisible(busy)
        self.status.setText("Downloading..." if busy else "Ready")

    def update_progress(self, index, total, label, fraction, state):
        self.progress.setValue(int((((index - 1) + fraction) / total) * 100))
        self.progress.setFormat(f"{index}/{total} - {fraction * 100:.0f}%")
        self.status.setText(f"{label} ({state})")

    def update_api_status(self, remaining, retry_after):
        if remaining is not None:
            self.api_status.setText(f"API requests remaining: {remaining}")
        elif retry_after is not None:
            self.api_status.setText(f"API rate limited; retry after {retry_after}s")
        else:
            self.api_status.setText("API requests remaining: not provided by Spotify")

    def download_finished(self, message, completed):
        self.set_busy(False)
        self.progress.setValue(100 if completed else 0)
        self.status.setText("Ready" if completed else "Failed")
        self.log_view.append(message)
        if not completed:
            self.show_error(message.removeprefix("Error: ").strip())

    def show_error(self, message):
        QMessageBox.critical(self, "Error", message)


def main():
    app = QApplication(sys.argv)
    window = DownloaderWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
