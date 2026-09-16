#!/usr/bin/env python3
"""
Spotify Playlist Downloader By YSHERBO
----------------------------
1. Fetches tracks from a Spotify playlist (OAuth)
2. Downloads audio from YouTube Music via yt-dlp
3. Embeds ID3 tags + album art from Spotify
 
Setup:
    pip install spotipy yt-dlp mutagen requests
 
    export SPOTIFY_CLIENT_ID="..."
    export SPOTIFY_CLIENT_SECRET="..."
 
    Add https://127.0.0.1:8888/callback to your Spotify app's Redirect URIs.
 
Usage:
    python spotify_downloader.py <playlist_url> [output_dir]
"""
 
import os, sys, re, time, shutil, argparse, tempfile, requests, urllib.parse
from pathlib import Path
from builtins import ImportError
 
try:
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
except ImportError:
    sys.exit("Missing dependency: pip install spotipy")
 
try:
    import yt_dlp
except ImportError:
    sys.exit("Missing dependency: pip install yt-dlp")
 
try:
    from mutagen.id3 import ID3, TIT2, TPE1, TALB, TPE2, TRCK, TPOS, TDRC, APIC, COMM, error as ID3Error
except ImportError:
    sys.exit("Missing dependency: pip install mutagen")
 
# ── CONFIG ────────────────────────────────────────────────────────────────────
 
CLIENT_ID     = os.environ.get("SPOTIFY_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
REDIRECT_URI  = "https://127.0.0.1:8888/callback"
MARKET        = "EG"
CACHE_PATH    = ".spotify_cache"
 
AUDIO_QUALITY = "320"
SLEEP         = 1.5
RETRIES       = 2
 
# ── SPOTIFY ───────────────────────────────────────────────────────────────────
 
def spotify_client(
    client_id=None,
    client_secret=None,
    redirect_uri=None,
    redirect_url=None,
    api_status_callback=None,
):
    client_id = client_id or CLIENT_ID
    client_secret = client_secret or CLIENT_SECRET
    redirect_uri = redirect_uri or REDIRECT_URI
    if not client_id or not client_secret:
        sys.exit("[ERROR] Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET env vars.")
    auth_manager = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope="playlist-read-private playlist-read-collaborative",
        cache_path=CACHE_PATH,
        open_browser=redirect_url is None,
    )
    if redirect_url:
        code = auth_manager.parse_response_code(redirect_url)
        auth_manager.get_access_token(code, as_dict=False)
    client = spotipy.Spotify(auth_manager=auth_manager)
    if api_status_callback and hasattr(client._session, "hooks"):
        def report_api_status(response, *args, **kwargs):
            api_status_callback(
                response.headers.get("X-RateLimit-Remaining"),
                response.headers.get("Retry-After"),
            )

        client._session.hooks["response"].append(report_api_status)
    return client


def spotify_auth_required(client_id, client_secret, redirect_uri=REDIRECT_URI):
    auth_manager = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope="playlist-read-private playlist-read-collaborative",
        cache_path=CACHE_PATH,
        open_browser=False,
    )
    return auth_manager.get_cached_token() is None


def spotify_authorization_url(client_id, client_secret, redirect_uri=REDIRECT_URI):
    auth_manager = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope="playlist-read-private playlist-read-collaborative",
        cache_path=CACHE_PATH,
        open_browser=False,
    )
    return auth_manager.get_authorize_url()
 
 
def playlist_id(url: str) -> str:
    m = re.search(r"playlist/([A-Za-z0-9]+)", url)
    return m.group(1) if m else url.strip()


def track_id(url: str) -> str:
    m = re.search(r"track/([A-Za-z0-9]+)", url)
    return m.group(1) if m else url.strip()


def track_data(t: dict) -> dict:
    album = t.get("album", {})
    return {
        "title": t["name"],
        "artists": [a["name"] for a in t.get("artists", [])],
        "album": album.get("name", ""),
        "album_artist": [a["name"] for a in album.get("artists", [])],
        "track_num": t.get("track_number", 0),
        "disc_num": t.get("disc_number", 1),
        "year": (album.get("release_date", "") or "")[:4],
        "isrc": t.get("external_ids", {}).get("isrc", ""),
        "cover_url": album["images"][0]["url"] if album.get("images") else None,
    }


def get_track(sp, tr_id: str) -> dict:
    return track_data(sp.track(tr_id, market=MARKET))
 
 
def get_tracks(sp, pl_id: str) -> tuple[str, str, list[dict]]:
    """Returns (playlist_name, owner, list_of_track_dicts)"""
    pl = sp.playlist(pl_id, market=MARKET)
    name  = pl.get("name", pl_id)
    owner = pl.get("owner", {}).get("display_name", "")
 
    tracks = []
    page = sp.playlist_items(pl_id, market=MARKET, additional_types=["track"], limit=100)
 
    while True:
        for item in page.get("items", []):
            # Spotify returns track under "track" or "item" depending on API version
            t = item.get("track") or item.get("item")
            if not t or t.get("is_local") or t.get("type") == "episode":
                continue
            if not t.get("name"):
                continue
 
            tracks.append(track_data(t))
 
        if page.get("next"):
            page = sp.next(page)
        else:
            break
 
    return name, owner, tracks
 
 
# ── DOWNLOAD ──────────────────────────────────────────────────────────────────
 
def safe_name(s: str) -> str:
    return re.sub(r'[<>:"/\\|?*\n\r]', "_", s).strip()
 
 
def download(track: dict, dest: Path, progress_callback=None) -> Path | None:
    artist = track["artists"][0] if track["artists"] else ""
    query  = f"ytsearch1:{artist} - {track['title']} audio"
    fname  = safe_name(f"{artist} - {track['title']}")
    final  = dest / f"{fname}.mp3"

    if final.exists():
        print(f"  [skip] {final.name}")
        if progress_callback:
            progress_callback({
                "status": "finished",
                "downloaded_bytes": 1,
                "total_bytes": 1,
            })
        return final

    # Use ytsearch1 to find the best matching result directly.
    with tempfile.TemporaryDirectory(prefix="spdl_") as tmp:
        out_tpl = str(Path(tmp) / "out.%(ext)s")
        opts = {
            "format":        "bestaudio/best",
            "outtmpl":       out_tpl,
            "quiet":         True,
            "no_warnings":   True,
            "noplaylist":    True,
            "progress_hooks": [progress_callback] if progress_callback else [],
            "postprocessors": [{
                "key":              "FFmpegExtractAudio",
                "preferredcodec":   "mp3",
                "preferredquality": AUDIO_QUALITY,
            }],
        }

        for attempt in range(RETRIES + 1):
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([query])

                tmp_mp3 = Path(tmp) / "out.mp3"
                if tmp_mp3.exists():
                    shutil.move(str(tmp_mp3), str(final))
                    return final
                else:
                    mp3s = list(Path(tmp).glob("*.mp3"))
                    if mp3s:
                        shutil.move(str(mp3s[0]), str(final))
                        return final
                    print(f"  [warn] Downloaded but no mp3 found in tmp dir. Tmp files: {[p.name for p in Path(tmp).iterdir()]}")

            except Exception as e:
                if attempt < RETRIES:
                    print(f"  [retry {attempt+1}] {e}")
                    time.sleep(2)
                else:
                    print(f"  [fail] {e}")
                    return None
 
    return None
 
 
# ── TAGGING ───────────────────────────────────────────────────────────────────
 
def fetch_cover(url: str) -> bytes | None:
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return r.content
    except Exception:
        return None
 
 
def tag(mp3: Path, track: dict):
    try:
        tags = ID3(str(mp3))
    except ID3Error:
        tags = ID3()
 
    def s(v): return "; ".join(v) if isinstance(v, list) else str(v)
 
    tags.delall("TIT2"); tags.add(TIT2(encoding=3, text=track["title"]))
    tags.delall("TPE1"); tags.add(TPE1(encoding=3, text=s(track["artists"])))
    tags.delall("TALB"); tags.add(TALB(encoding=3, text=track["album"]))
    tags.delall("TPE2"); tags.add(TPE2(encoding=3, text=s(track["album_artist"] or track["artists"])))
 
    if track["track_num"]:
        tags.delall("TRCK"); tags.add(TRCK(encoding=3, text=str(track["track_num"])))
    if track["disc_num"] and track["disc_num"] > 1:
        tags.delall("TPOS"); tags.add(TPOS(encoding=3, text=str(track["disc_num"])))
    if track["year"]:
        tags.delall("TDRC"); tags.add(TDRC(encoding=3, text=track["year"]))
    if track["isrc"]:
        tags.delall("COMM"); tags.add(COMM(encoding=3, lang="eng", desc="ISRC", text=track["isrc"]))
 
    if track.get("cover_url"):
        img = fetch_cover(track["cover_url"])
        if img:
            tags.delall("APIC")
            tags.add(APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=img))
 
    tags.save(str(mp3), v2_version=3)
 
 
# ── MAIN ──────────────────────────────────────────────────────────────────────
 
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("playlist", help="Spotify playlist URL or ID")
    ap.add_argument("output",   nargs="?", default="./downloads")
    ap.add_argument("--no-tags", action="store_true")
    args = ap.parse_args()
 
    sp = spotify_client()
    pl = playlist_id(args.playlist)
 
    print(f"[*] Fetching playlist…")
    name, owner, tracks = get_tracks(sp, pl)
    total = len(tracks)
 
    print(f"\n    {name}  —  {owner}")
    print(f"    {total} tracks\n")
 
    if not total:
        print("[!] Playlist is empty or no tracks found.")
        return
 
    out = Path(args.output) / safe_name(name)
    out.mkdir(parents=True, exist_ok=True)
 
    ok, failed = 0, []
 
    for i, t in enumerate(tracks, 1):
        label = f"{', '.join(t['artists'])} — {t['title']}"
        print(f"[{i:>3}/{total}] {label}")
 
        mp3 = download(t, out)
        if mp3:
            if not args.no_tags:
                tag(mp3, t)
            print(f"       ✓ {mp3.name}")
            ok += 1
        else:
            failed.append(label)
 
        time.sleep(SLEEP)
 
    print(f"\n{'─'*50}")
    print(f"Done  {ok}/{total}  →  {out}")
    if failed:
        print(f"\nFailed ({len(failed)}):")
        for f in failed: print(f"  ✗ {f}")
 
 
if __name__ == "__main__":
    main()
 
