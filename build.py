import argparse
import os
import subprocess
import sys

def main():
    parser = argparse.ArgumentParser(description="Build Spotify Downloader")
    
    # OS Flags
    os_group = parser.add_mutually_exclusive_group(required=True)
    os_group.add_argument("--windows", action="store_true", help="Build for Windows")
    os_group.add_argument("--mac", action="store_true", help="Build for macOS")
    os_group.add_argument("--linux", action="store_true", help="Build for Linux")
    
    # API Credentials
    parser.add_argument("--client", type=str, default="", help="Spotify Client ID")
    parser.add_argument("--secret", type=str, default="", help="Spotify Client Secret")
    
    # UI Framework Flags
    ui_group = parser.add_mutually_exclusive_group(required=True)
    ui_group.add_argument("--qt", action="store_true", help="Build Qt version")
    ui_group.add_argument("--gtk", action="store_true", help="Build GTK version")
    
    args = parser.parse_args()

    # Determine which UI module to load
    ui_module = "qt_app" if args.qt else "gtk_app"

    # Generate a temporary entry script with direct imports
    # Direct top-level imports ensure PyInstaller's AST scanner picks them up
    entry_script = "build_entry.py"
    entry_code = f"""import os
import sys

# Inject Spotify API credentials into environment
if "{args.client}":
    os.environ["SPOTIFY_CLIENT_ID"] = "{args.client}"
if "{args.secret}":
    os.environ["SPOTIFY_CLIENT_SECRET"] = "{args.secret}"

# Directly import the selected UI module
import {ui_module}
sys.exit({ui_module}.main())
"""
    
    with open(entry_script, "w", encoding="utf-8") as f:
        f.write(entry_code)

    print(f"[*] Generated temporary entry point for {ui_module}...")

    # Construct the PyInstaller command with explicit hidden imports
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--windowed", 
        "--name", "SpotifyDownloader",
        "--hidden-import", "main",
        "--hidden-import", ui_module,
        "--hidden-import", "spotipy",
        "--hidden-import", "yt_dlp",
        "--hidden-import", "mutagen",
        "--hidden-import", "requests",
    ]

    # Explicitly include the correct UI framework
    if args.qt:
        cmd.extend(["--hidden-import", "PySide6"])
        print("[*] Configuring build for Linux (Qt)...")
    elif args.gtk:
        cmd.extend(["--hidden-import", "gi"])
        print("[*] Configuring build for Linux (GTK)...")

    cmd.append(entry_script)

    # Run PyInstaller
    try:
        print("[*] Running PyInstaller...")
        subprocess.run(cmd, check=True)
        print("[+] Build completed successfully! Check the 'dist' folder.")
    except subprocess.CalledProcessError as e:
        print(f"[-] Build failed with error code: {e.returncode}")
    finally:
        # Clean up the temporary entry point
        if os.path.exists(entry_script):
            os.remove(entry_script)

if __name__ == "__main__":
    main()