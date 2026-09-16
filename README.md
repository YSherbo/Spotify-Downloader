# Spotify Playlist Downloader

A simple Python tool to download audio from a Spotify playlist using Spotify metadata and YouTube Music via `yt-dlp`.

## Features

- Fetches playlist tracks from Spotify using OAuth
- Downloads audio from YouTube Music with `yt-dlp`
- Converts audio to MP3
- Embeds ID3 tags and album artwork from Spotify metadata
- Provides both a command-line interface and a native GTK 4 interface
- Provides a separate Qt 6 interface for desktop packaging

## Requirements

- Python 3.8+
- `spotipy`
- `yt-dlp`
- `mutagen`
- `requests`
- GTK 4 and PyGObject (`python3-gi`, `gir1.2-gtk-4.0` on Debian/Ubuntu)
- PySide6 for the Qt 6 interface
- `ffmpeg` (required by `yt-dlp` for MP3 conversion)

## Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

On Debian/Ubuntu, install the native GTK runtime separately:

```bash
sudo apt install python3-gi gir1.2-gtk-4.0 ffmpeg
```

2. Set Spotify credentials in environment variables:

```bash
export SPOTIFY_CLIENT_ID="your-client-id"
export SPOTIFY_CLIENT_SECRET="your-client-secret"
```

3. Configure your Spotify app redirect URI:

Add `https://127.0.0.1:8888/callback` to the Redirect URIs in your Spotify Developer Dashboard.

## Usage

```bash
python main.py <playlist_url> [output_dir]
```

- `playlist_url` — Spotify playlist URL or playlist ID
- `output_dir` — optional output directory (default: `./downloads`)

### Example

```bash
python main.py https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M
```

This creates a directory named after the playlist inside `./downloads`.

### GTK app

Launch the native GTK 4 interface with:

```bash
python gtk_app.py
```

The app follows the system theme, font, and icon theme. Use the navigation bar to choose one of these actions:

- **Download playlist** — download every track in a Spotify playlist as MP3 files.
- **Download song** — download one Spotify track URL or ID as an MP3 file.
- **Get metadata** — apply Spotify tags and cover art to existing playlist MP3 files without downloading music.
- **About** — view the author and website link.

Choose an output folder and press **Download**. The GUI shows each song's download percentage and speed. Downloads run off the UI thread so the window remains responsive while Spotify and YouTube are working.

When Spotify credentials are not present in the environment, the app opens a window for the Client ID and Client Secret. When Spotify authorization is needed, it opens the authorization page and asks for the complete redirected URL in a GUI window. Authentication and download errors are shown in GUI error dialogs.

The app displays Spotify's `X-RateLimit-Remaining` value when the API returns it. Spotify does not include that value in every response, so the GUI reports when the remaining-request count is unavailable.

### Qt 6 app

Launch the separate Qt 6 interface with:

```bash
python qt_app.py
```

Build a desktop executable on the current platform with PyInstaller:

```bash
python -m pip install pyinstaller
python build_qt.py
```

The executable is placed under `dist/SpotifyDownloaderQt`. The repository also includes a GitHub Actions workflow that builds Linux and Windows artifacts on their native runners.

## Options

- `--no-tags` — download the MP3 files without embedding Spotify metadata tags and cover art

## Notes

- The script uses the first search result from YouTube Music via `ytsearch1:` and may not always find an exact match.
- If a file already exists, it is skipped.
- The script only downloads track items and ignores local files and episodes.

## Troubleshooting

- If the script exits with a missing dependency error, install the required package shown in the message.
- Make sure the Spotify app credentials are valid and that the redirect URI exactly matches the registered URI.
- If downloads fail repeatedly, verify that `yt-dlp` can access YouTube Music from your network.

## License

This project is provided as-is.
