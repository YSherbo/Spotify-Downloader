# Spotify Playlist Downloader

A simple Python tool to download audio from a Spotify playlist using Spotify metadata and YouTube Music via `yt-dlp`.

## Features

- Fetches playlist tracks from Spotify using OAuth
- Downloads audio from YouTube Music with `yt-dlp`
- Converts audio to MP3
- Embeds ID3 tags and album artwork from Spotify metadata
- Provides both a command-line interface and a native GTK 4 interface
- Provides a separate Qt 6 interface for desktop packaging

---

## Installation (Pre-built Binaries)

Ready-to-use binaries are available under the **Releases** tab on GitHub. No Python environment or dependency setup is required for pre-built binaries.

### Windows

1. Download `SpotifyDownloader.exe` from the latest Release.
2. Double-click the file to launch the application.

### macOS

1. Download `SpotifyDownloader-macOS.zip` (or `SpotifyDownloader.app`) from Releases.
2. Extract the archive and move `SpotifyDownloader.app` to your `Applications` folder.
3. If macOS blocks execution due to Gatekeeper, right-click `SpotifyDownloader.app`, select **Open**, and confirm, or clear the quarantine attribute via terminal:

```bash
xattr -cr /Applications/SpotifyDownloader.app

```

### Linux

1. Download the `SpotifyDownloader` Linux executable from Releases.
2. Grant execution permissions and run:

```bash
chmod +x SpotifyDownloader
./SpotifyDownloader

```

---

## Requirements (Running or Building from Source)

- Python 3.8+
- `spotipy`
- `yt-dlp`
- `mutagen`
- `requests`
- `PyInstaller` (required for building binaries)
- GTK 4 and PyGObject (`python3-gi`, `gir1.2-gtk-4.0` on Debian/Ubuntu) for GTK builds
- `PySide6` for Qt 6 builds
- `ffmpeg` (required by `yt-dlp` for MP3 conversion)

---

## Building from Source

You can compile standalone single-file executables for Linux, macOS, or Windows using `build.py`.

### Build Command Syntax

```bash
python build.py (--windows | --mac | --linux) (--qt | --gtk) [--client "CLIENT_ID"] [--secret "CLIENT_SECRET"]

```

- `--windows`, `--mac`, `--linux` — target platform (must select one)
- `--qt`, `--gtk` — UI toolkit choice (must select one)
- `--client` — _(Optional)_ bake your Spotify Client ID into the executable
- `--secret` — _(Optional)_ bake your Spotify Client Secret into the executable

### Build Examples

- **Linux (Qt 6):**

```bash
python build.py --linux --qt

```

- **Linux (GTK 4):**

```bash
python build.py --linux --gtk

```

- **Windows (Qt 6 with embedded credentials):**

```bash
python build.py --windows --qt --client "your_id" --secret "your_secret"

```

- **macOS (Qt 6):**

```bash
python build.py --mac --qt

```

The compiled output will be generated inside the `dist/` directory.

---

## Setup (Source Code Execution)

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

Add `[https://127.0.0.1:8888/callback](https://127.0.0.1:8888/callback)` to the Redirect URIs in your Spotify Developer Dashboard.

---

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

---

## Options

- `--no-tags` — download the MP3 files without embedding Spotify metadata tags and cover art

---

## Notes

- The script uses the first search result from YouTube Music via `ytsearch1:` and may not always find an exact match.
- If a file already exists, it is skipped.
- The script only downloads track items and ignores local files and episodes.

---

## Troubleshooting

- If the script exits with a missing dependency error, install the required package shown in the message.
- Make sure the Spotify app credentials are valid and that the redirect URI exactly matches the registered URI.
- If downloads fail repeatedly, verify that `yt-dlp` can access YouTube Music from your network.

---

## License

steal this if u want i honestly dont care
