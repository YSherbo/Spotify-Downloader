#!/usr/bin/env python3
"""Native GTK 4 interface for the Spotify playlist downloader."""

import threading
import time
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from main import (
    SLEEP,
    download,
    get_tracks,
    playlist_id,
    safe_name,
    spotify_client,
    tag,
)


class DownloaderWindow(Gtk.ApplicationWindow):
    def __init__(self, app: Gtk.Application):
        super().__init__(application=app, title="Spotify Playlist Downloader")
        self.set_default_size(760, 620)
        self.set_size_request(520, 480)
        self._worker = None

        header = Gtk.HeaderBar()
        header.set_show_title_buttons(True)
        self.set_titlebar(header)

        title = Gtk.Label(label="Spotify Downloader")
        title.add_css_class("title-3")
        header.set_title_widget(title)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        root.set_margin_top(24)
        root.set_margin_bottom(24)
        root.set_margin_start(28)
        root.set_margin_end(28)
        self.set_child(root)

        intro = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        root.append(intro)
        heading = Gtk.Label(label="Download a playlist")
        heading.set_xalign(0)
        heading.add_css_class("title-2")
        intro.append(heading)
        subtitle = Gtk.Label(label="Fetch tracks from Spotify and save tagged MP3 files.")
        subtitle.set_xalign(0)
        subtitle.add_css_class("dim-label")
        intro.append(subtitle)

        form = Gtk.Grid(column_spacing=12, row_spacing=12)
        root.append(form)

        playlist_label = Gtk.Label(label="Playlist")
        playlist_label.set_xalign(0)
        form.attach(playlist_label, 0, 0, 1, 1)
        self.playlist_entry = Gtk.Entry(placeholder_text="Spotify playlist URL or ID")
        self.playlist_entry.set_hexpand(True)
        self.playlist_entry.connect("activate", self._start_download)
        form.attach(self.playlist_entry, 1, 0, 2, 1)

        output_label = Gtk.Label(label="Save to")
        output_label.set_xalign(0)
        form.attach(output_label, 0, 1, 1, 1)
        output_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        output_row.set_hexpand(True)
        form.attach(output_row, 1, 1, 2, 1)
        self.output_entry = Gtk.Entry(text=str(Path.cwd() / "downloads"))
        self.output_entry.set_hexpand(True)
        output_row.append(self.output_entry)
        self.output_button = Gtk.Button(icon_name="folder-open-symbolic", tooltip_text="Choose a folder")
        self.output_button.connect("clicked", self._choose_folder)
        output_row.append(self.output_button)

        self.tags_check = Gtk.CheckButton(label="Embed Spotify tags and cover art")
        self.tags_check.set_active(True)
        form.attach(self.tags_check, 1, 2, 2, 1)

        action_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        root.append(action_row)
        self.download_button = Gtk.Button(label="Download")
        self.download_button.set_icon_name("folder-download-symbolic")
        self.download_button.add_css_class("suggested-action")
        self.download_button.connect("clicked", self._start_download)
        action_row.append(self.download_button)
        self.status_label = Gtk.Label(label="Ready")
        self.status_label.set_xalign(0)
        self.status_label.set_hexpand(True)
        self.status_label.add_css_class("dim-label")
        action_row.append(self.status_label)

        self.progress = Gtk.ProgressBar()
        self.progress.set_show_text(True)
        self.progress.set_visible(False)
        root.append(self.progress)

        frame = Gtk.Frame(label="Activity")
        frame.set_vexpand(True)
        root.append(frame)
        scroll = Gtk.ScrolledWindow()
        scroll.set_min_content_height(180)
        frame.set_child(scroll)
        self.log_view = Gtk.TextView()
        self.log_view.set_editable(False)
        self.log_view.set_cursor_visible(False)
        self.log_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.log_view.set_vexpand(True)
        scroll.set_child(self.log_view)

    def _append_log(self, text: str):
        buffer = self.log_view.get_buffer()
        end = buffer.get_end_iter()
        buffer.insert(end, f"{text}\n")
        self.log_view.scroll_to_iter(buffer.get_end_iter(), 0, False, 0, 1)

    def _set_busy(self, busy: bool):
        self.playlist_entry.set_sensitive(not busy)
        self.output_entry.set_sensitive(not busy)
        self.output_button.set_sensitive(not busy)
        self.tags_check.set_sensitive(not busy)
        self.download_button.set_sensitive(not busy)
        self.download_button.set_label("Downloading..." if busy else "Download")
        if busy:
            self.progress.set_visible(True)

    def _choose_folder(self, _button):
        dialog = Gtk.FileDialog(title="Choose download folder")
        dialog.select_folder(self, None, self._folder_selected)

    def _folder_selected(self, dialog, result):
        try:
            folder = dialog.select_folder_finish(result)
        except GLib.Error:
            return
        if folder:
            self.output_entry.set_text(folder.get_path())

    def _start_download(self, _widget):
        if self._worker and self._worker.is_alive():
            return

        playlist = self.playlist_entry.get_text().strip()
        output = self.output_entry.get_text().strip()
        if not playlist:
            self.status_label.set_text("Enter a playlist URL or ID")
            self.playlist_entry.grab_focus()
            return
        if not output:
            self.status_label.set_text("Choose an output folder")
            return

        self._set_busy(True)
        self.progress.set_fraction(0)
        self.progress.set_text("Connecting to Spotify...")
        self.log_view.get_buffer().set_text("")
        self._worker = threading.Thread(
            target=self._download_playlist,
            args=(playlist, Path(output).expanduser(), self.tags_check.get_active()),
            daemon=True,
        )
        self._worker.start()

    def _download_playlist(self, playlist: str, output: Path, add_tags: bool):
        try:
            self._ui_log("Connecting to Spotify...")
            name, owner, tracks = get_tracks(spotify_client(), playlist_id(playlist))
            total = len(tracks)
            GLib.idle_add(self._playlist_loaded, name, owner, total)
            if not total:
                GLib.idle_add(self._finished, "Playlist is empty or no tracks found.", True)
                return

            destination = output / safe_name(name)
            destination.mkdir(parents=True, exist_ok=True)
            failed = []
            for index, track in enumerate(tracks, 1):
                label = f"{', '.join(track['artists'])} - {track['title']}"
                GLib.idle_add(self._track_started, index, total, label)
                try:
                    mp3 = download(track, destination)
                    if mp3 and add_tags:
                        tag(mp3, track)
                    if mp3:
                        self._ui_log(f"Saved: {mp3.name}")
                    else:
                        failed.append(label)
                        self._ui_log(f"Failed: {label}")
                except Exception as error:
                    failed.append(label)
                    self._ui_log(f"Failed: {label} ({error})")
                if index < total:
                    time.sleep(SLEEP)

            summary = f"Finished: {total - len(failed)}/{total} tracks saved to {destination}"
            if failed:
                summary += f" ({len(failed)} failed)"
            GLib.idle_add(self._finished, summary, True)
        except Exception as error:
            GLib.idle_add(self._finished, f"Error: {error}", False)

    def _ui_log(self, text: str):
        GLib.idle_add(self._append_log, text)

    def _playlist_loaded(self, name: str, owner: str, total: int):
        owner_text = f" by {owner}" if owner else ""
        self._append_log(f"{name}{owner_text} - {total} tracks")
        self.progress.set_text(f"0/{total} tracks")
        return GLib.SOURCE_REMOVE

    def _track_started(self, index: int, total: int, label: str):
        self.status_label.set_text(label)
        self.progress.set_fraction((index - 1) / total)
        self.progress.set_text(f"{index}/{total} tracks")
        self._append_log(f"[{index}/{total}] {label}")
        return GLib.SOURCE_REMOVE

    def _finished(self, message: str, completed: bool):
        self._set_busy(False)
        self.progress.set_fraction(1 if completed else 0)
        self.progress.set_text(message)
        self.status_label.set_text("Ready" if completed else "Could not complete download")
        self._append_log(message)
        return GLib.SOURCE_REMOVE


class DownloaderApplication(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.github.ysherbo.SpotifyDownloader")

    def do_activate(self):
        window = self.props.active_window
        if window is None:
            window = DownloaderWindow(self)
        window.present()


def main():
    app = DownloaderApplication()
    return app.run()


if __name__ == "__main__":
    main()
