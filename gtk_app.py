#!/usr/bin/env python3
"""Native GTK 4 interface for the Spotify playlist downloader."""

import threading
import time
import webbrowser
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

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


class DownloaderWindow(Gtk.ApplicationWindow):
    def __init__(self, app: Gtk.Application):
        super().__init__(application=app, title="Spotify Playlist Downloader")
        self.set_default_size(760, 620)
        self.set_size_request(520, 480)
        self._worker = None
        self._credentials = None
        self._redirect_uri = REDIRECT_URI

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

        self.nav = Gtk.StackSwitcher()
        self.nav.set_halign(Gtk.Align.START)
        root.append(self.nav)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.stack.set_vexpand(False)
        self.nav.set_stack(self.stack)
        root.append(self.stack)

        playlist_page, self.playlist_entry = self._input_page(
            "Download playlist", "Playlist URL or ID", "Fetch and download every track in a playlist."
        )
        song_page, self.song_entry = self._input_page(
            "Download song", "Track URL or ID", "Download one Spotify track as an MP3."
        )
        metadata_page, self.metadata_entry = self._input_page(
            "Get metadata", "Playlist URL or ID", "Apply Spotify tags and cover art to existing MP3 files."
        )
        self.stack.add_titled(playlist_page, "playlist", "Download playlist")
        self.stack.add_titled(song_page, "song", "Download song")
        self.stack.add_titled(metadata_page, "metadata", "Get metadata")

        about = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        about.set_margin_top(12)
        about_label = Gtk.Label(label="Spotify Downloader\nCreated by YSherbo", justify=Gtk.Justification.LEFT)
        about_label.set_xalign(0)
        about.append(about_label)
        about_link = Gtk.LinkButton(uri="https://ysherbo.github.io", label="ysherbo.github.io")
        about_link.set_halign(Gtk.Align.START)
        about.append(about_link)
        self.stack.add_titled(about, "about", "About")

        output_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        root.append(output_row)
        output_label = Gtk.Label(label="Save to")
        output_row.append(output_label)
        self.output_entry = Gtk.Entry(text=str(Path.cwd() / "downloads"))
        self.output_entry.set_hexpand(True)
        output_row.append(self.output_entry)
        self.output_button = Gtk.Button(icon_name="folder-open-symbolic", tooltip_text="Choose a folder")
        self.output_button.connect("clicked", self._choose_folder)
        output_row.append(self.output_button)

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
        self.api_status_label = Gtk.Label(label="API requests remaining: checking...")
        self.api_status_label.set_xalign(0)
        self.api_status_label.add_css_class("dim-label")
        root.append(self.api_status_label)

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

        if CLIENT_ID and CLIENT_SECRET:
            self._credentials = (CLIENT_ID, CLIENT_SECRET)
        else:
            GLib.idle_add(self._prompt_credentials)

    def _input_page(self, title, placeholder, description):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        page.set_margin_top(8)
        heading = Gtk.Label(label=title)
        heading.set_xalign(0)
        heading.add_css_class("title-2")
        page.append(heading)
        subtitle = Gtk.Label(label=description)
        subtitle.set_xalign(0)
        subtitle.add_css_class("dim-label")
        page.append(subtitle)
        entry = Gtk.Entry(placeholder_text=placeholder)
        entry.set_hexpand(True)
        entry.connect("activate", self._start_download)
        page.append(entry)
        return page, entry

    def _append_log(self, text: str):
        buffer = self.log_view.get_buffer()
        end = buffer.get_end_iter()
        buffer.insert(end, f"{text}\n")
        self.log_view.scroll_to_iter(buffer.get_end_iter(), 0, False, 0, 1)

    def _set_busy(self, busy: bool):
        self.playlist_entry.set_sensitive(not busy)
        self.song_entry.set_sensitive(not busy)
        self.metadata_entry.set_sensitive(not busy)
        self.output_entry.set_sensitive(not busy)
        self.output_button.set_sensitive(not busy)
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

        mode = self.stack.get_visible_child_name()
        entries = {
            "playlist": self.playlist_entry,
            "song": self.song_entry,
            "metadata": self.metadata_entry,
        }
        if mode == "about":
            return
        source = entries[mode]
        playlist = source.get_text().strip()
        output = self.output_entry.get_text().strip()
        if not playlist:
            self.status_label.set_text(f"Enter a {('track' if mode == 'song' else 'playlist')} URL or ID")
            source.grab_focus()
            return
        if not output:
            self.status_label.set_text("Choose an output folder")
            return

        self._ensure_credentials(lambda: self._ensure_authorization(
            lambda redirect_url: self._launch_download(
                mode, playlist, Path(output).expanduser(), redirect_url,
            ),
        ))

    def _ensure_credentials(self, callback):
        if self._credentials:
            callback()
        else:
            self._prompt_credentials(callback)

    def _prompt_credentials(self, callback=None):
        self._show_form(
            "Spotify credentials",
            "Enter your Spotify application credentials.",
            [("Client ID", False), ("Client secret", True)],
            lambda values: self._credentials_entered(values, callback),
        )
        return GLib.SOURCE_REMOVE

    def _credentials_entered(self, values, callback):
        self._credentials = (values["Client ID"], values["Client secret"])
        if callback:
            callback()

    def _ensure_authorization(self, callback):
        client_id, client_secret = self._credentials
        try:
            if not spotify_auth_required(client_id, client_secret, self._redirect_uri):
                callback(None)
                return
            webbrowser.open(spotify_authorization_url(
                client_id, client_secret, self._redirect_uri,
            ))
            self._show_form(
                "Spotify redirect URL",
                "Authorize the app in your browser, then paste the complete redirected URL.",
                [("Redirect URL", False)],
                lambda values: callback(values["Redirect URL"]),
            )
        except Exception as error:
            self._show_error(str(error))

    def _launch_download(self, mode, source, output, redirect_url):
        self._set_busy(True)
        self.progress.set_fraction(0)
        self.progress.set_text("Connecting to Spotify...")
        self.log_view.get_buffer().set_text("")
        self._worker = threading.Thread(
            target=self._download_playlist,
            args=(
                mode,
                source,
                output,
                redirect_url,
            ),
            daemon=True,
        )
        self._worker.start()

    def _download_playlist(
        self,
        mode: str,
        playlist: str,
        output: Path,
        redirect_url: str | None,
    ):
        try:
            self._ui_log("Connecting to Spotify...")
            client_id, client_secret = self._credentials
            client = spotify_client(
                client_id,
                client_secret,
                self._redirect_uri,
                redirect_url,
                self._api_status_received,
            )
            if mode == "song":
                track = get_track(client, track_id(playlist))
                name = track["title"]
                owner = ", ".join(track["artists"])
                tracks = [track]
            else:
                name, owner, tracks = get_tracks(client, playlist_id(playlist))
            total = len(tracks)
            GLib.idle_add(self._playlist_loaded, name, owner, total)
            if not total:
                GLib.idle_add(self._finished, "Playlist is empty or no tracks found.", True)
                return

            destination = output if mode == "song" else output / safe_name(name)
            destination.mkdir(parents=True, exist_ok=True)
            failed = []
            for index, track in enumerate(tracks, 1):
                label = f"{', '.join(track['artists'])} - {track['title']}"
                GLib.idle_add(self._track_started, index, total, label)
                try:
                    filename = safe_name(
                        f"{track['artists'][0] if track['artists'] else ''} - {track['title']}"
                    )
                    if mode != "metadata":
                        mp3 = download(
                            track,
                            destination,
                            lambda status, current_index=index, current_label=label: self._download_progress(
                                current_index, total, current_label, status,
                            ),
                        )
                    else:
                        mp3 = destination / f"{filename}.mp3"
                        GLib.idle_add(self._track_progress, index, total, label, 1.0, "Metadata")
                    if mode == "metadata" and not mp3.exists():
                        self._ui_log(f"Metadata skipped; MP3 not found: {mp3.name}")
                        mp3 = None
                    if mp3:
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

    def _api_status_received(self, remaining, retry_after):
        GLib.idle_add(self._update_api_status, remaining, retry_after)

    def _update_api_status(self, remaining, retry_after):
        if remaining is not None:
            text = f"API requests remaining: {remaining}"
        elif retry_after is not None:
            text = f"API rate limited; retry after {retry_after}s"
        else:
            text = "API requests remaining: not provided by Spotify"
        self.api_status_label.set_text(text)
        return GLib.SOURCE_REMOVE

    def _download_progress(self, index, total, label, status):
        downloaded = status.get("downloaded_bytes", 0)
        total_bytes = status.get("total_bytes") or status.get("total_bytes_estimate")
        fraction = downloaded / total_bytes if total_bytes else 0
        speed = status.get("speed")
        speed_text = f" - {speed / 1024 / 1024:.1f} MiB/s" if speed else ""
        state = status.get("status", "downloading")
        GLib.idle_add(self._track_progress, index, total, label, fraction, f"{state}{speed_text}")

    def _track_progress(self, index, total, label, fraction, state):
        overall = ((index - 1) + fraction) / total
        self.progress.set_fraction(overall)
        self.progress.set_text(f"{index}/{total} tracks - {fraction * 100:.0f}%")
        self.status_label.set_text(f"{label} ({state})")
        return GLib.SOURCE_REMOVE

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
        if not completed:
            self._show_error(message.removeprefix("Error: ").strip())
        return GLib.SOURCE_REMOVE

    def _show_form(self, title, description, fields, callback):
        window = Gtk.Window(title=title, transient_for=self, modal=True)
        window.set_default_size(460, 220)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(20)
        box.set_margin_bottom(20)
        box.set_margin_start(20)
        box.set_margin_end(20)
        window.set_child(box)
        description_label = Gtk.Label(label=description, wrap=True)
        description_label.set_xalign(0)
        box.append(description_label)
        entries = {}
        for field_name, secret in fields:
            entry = Gtk.Entry(placeholder_text=field_name)
            entry.set_visibility(not secret)
            entry.set_hexpand(True)
            box.append(entry)
            entries[field_name] = entry
        submit = Gtk.Button(label="Continue")
        submit.add_css_class("suggested-action")
        box.append(submit)

        def submit_form(_button):
            values = {name: entry.get_text().strip() for name, entry in entries.items()}
            if fields and not all(values.values()):
                self._show_error("All fields are required.")
                return
            window.destroy()
            callback(values)

        submit.connect("clicked", submit_form)
        window.present()

    def _show_error(self, message):
        dialog = Gtk.AlertDialog(message=message)
        dialog.set_detail("The operation could not be completed.")
        dialog.show(self)


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
