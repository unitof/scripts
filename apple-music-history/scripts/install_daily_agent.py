#!/usr/bin/env python3
"""Install the per-user launchd job without invoking an LLM."""

import argparse
import os
from pathlib import Path
import plistlib
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hour", type=int, choices=range(24), default=10)
    parser.add_argument("--minute", type=int, choices=range(60), default=0)
    parser.add_argument("--push", action="store_true", help="Enable uploads to the Git upstream (may be public)")
    parser.add_argument("--include-noggy", action="store_true", help="Also capture Noggy; with --push its data is uploaded too")
    parser.add_argument("--all-playlists", action="store_true", help="Capture all locally exposed playlists; --push publishes all")
    parser.add_argument("--playlist-repo", type=Path,
                        default=Path.home() / "repos/apple-music-playlist-history")
    args = parser.parse_args()
    repo = args.playlist_repo.expanduser().resolve()
    if not (repo / ".git").is_dir():
        parser.error(f"not a git checkout: {repo}")
    label = "com.unitof.apple-music-history"
    home = Path.home()
    logs = home / "Library/Logs/apple-music-history"
    agents = home / "Library/LaunchAgents"
    logs.mkdir(parents=True, exist_ok=True)
    agents.mkdir(parents=True, exist_ok=True)
    destination = agents / f"{label}.plist"
    binaries = home / "Library/Application Support/apple-music-history"
    binaries.mkdir(parents=True, exist_ok=True)
    exporter = binaries / "export-favorite-songs"
    source = Path(__file__).resolve().with_name("export_current_favorite_songs.swift")
    with tempfile.TemporaryDirectory(dir=binaries) as temporary:
        compiled = Path(temporary) / "export-favorite-songs"
        subprocess.run(["xcrun", "swiftc", str(source), "-framework", "iTunesLibrary",
                        "-o", str(compiled)], check=True, timeout=180)
        subprocess.run(["codesign", "--force", "--sign", "-", str(compiled)],
                       check=True, timeout=30)
        compiled.replace(exporter)
    plist = {
        "Label": label,
        "ProgramArguments": ["/bin/zsh", str(Path(__file__).resolve().with_name("run_daily_snapshot.zsh"))],
        "WorkingDirectory": str(repo),
        "EnvironmentVariables": {"HOME": str(home), "APPLE_MUSIC_HISTORY_REPO": str(repo),
                                 "APPLE_MUSIC_HISTORY_PUSH": "1" if args.push else "0",
                                 "APPLE_MUSIC_HISTORY_NOGGY": "1" if args.include_noggy else "0",
                                 "APPLE_MUSIC_HISTORY_ALL": "1" if args.all_playlists else "0",
                                 "APPLE_MUSIC_HISTORY_EXPORTER": str(exporter)},
        "StartCalendarInterval": {"Hour": args.hour, "Minute": args.minute},
        "LimitLoadToSessionType": "Aqua",
        "ProcessType": "Standard",
        "StandardOutPath": str(logs / "daily.log"),
        "StandardErrorPath": str(logs / "daily.error.log"),
        "Umask": 0o077,
    }
    domain = f"gui/{os.getuid()}"
    service = f"{domain}/{label}"
    loaded = subprocess.run(["launchctl", "print", service], capture_output=True).returncode == 0
    if loaded:
        subprocess.run(["launchctl", "bootout", service], check=True)
    with destination.open("wb") as file:
        plistlib.dump(plist, file)
    destination.chmod(0o600)
    subprocess.run(["plutil", "-lint", str(destination)], check=True)
    subprocess.run(["launchctl", "bootstrap", domain, str(destination)], check=True)
    print(f"Installed {destination}: daily at {args.hour:02d}:{args.minute:02d} local time")


if __name__ == "__main__":
    main()
