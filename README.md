# Spotify Playlist Downloader

A simple Python tool to download audio from a Spotify playlist using Spotify metadata and YouTube Music via `yt-dlp`.

## Features

- Fetches playlist tracks from Spotify using OAuth
- Downloads audio from YouTube Music with `yt-dlp`
- Converts audio to MP3
- Embeds ID3 tags and album artwork from Spotify metadata

## Requirements

- Python 3.8+
- `spotipy`
- `yt-dlp`
- `mutagen`
- `requests`

## Setup

1. Install dependencies:

```bash
pip install spotipy yt-dlp mutagen requests
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

This will create a directory named after the playlist inside `./downloads`.

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
