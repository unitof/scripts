#!/usr/bin/env python3
"""Validate and apply a complete playlist inventory; caller holds the repo lock."""

from collections import Counter
from datetime import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time


FIELDS = ("persistent_id", "title", "artist", "album", "url")
INDEX = "playlists.json"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def identifier(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9]{1,20}", value) is not None


def managed_path(value):
    return isinstance(value, str) and (
        value in ("Favorite Songs.tsv", "Noggy.tsv")
        or re.fullmatch(r"playlists/[0-9]{1,20}\.tsv", value) is not None
    )


def escape(value):
    return value.replace("\\", "\\\\").replace("\t", "\\t").replace("\r", "\\r").replace("\n", "\\n")


def build_snapshot(payload, previous):
    require(isinstance(payload, dict) and payload.get("schema_version") == 1
            and payload.get("complete") is True, "incomplete or unsupported inventory")
    playlists = payload.get("playlists")
    require(isinstance(playlists, list) and playlists, "empty playlist inventory")
    old = {}
    if previous is not None:
        require(isinstance(previous, dict) and previous.get("schema_version") == 1
                and isinstance(previous.get("playlists"), list), "invalid prior index")
        for entry in previous["playlists"]:
            require(isinstance(entry, dict) and identifier(entry.get("persistent_id"))
                    and managed_path(entry.get("file")), "unsafe prior index entry")
            require(entry["persistent_id"] not in old, "duplicate prior playlist ID")
            old[entry["persistent_id"]] = entry["file"]
        require(len(set(old.values())) == len(old), "duplicate prior snapshot path")

    names = Counter(p.get("name") for p in playlists if isinstance(p, dict) and isinstance(p.get("name"), str))
    output, entries, ids = {}, [], set()
    favorites = 0
    for playlist in playlists:
        require(isinstance(playlist, dict), "invalid playlist object")
        pid = playlist.get("persistent_id")
        require(identifier(pid) and pid not in ids, "invalid or duplicate playlist ID")
        ids.add(pid)
        require(isinstance(playlist.get("name"), str), "invalid playlist name")
        require(playlist.get("parent_id") is None or identifier(playlist["parent_id"]), "invalid parent ID")
        require(all(type(playlist.get(k)) is int and playlist[k] >= 0
                    for k in ("kind", "distinguished_kind")), "invalid playlist kind")
        require(type(playlist.get("visible")) is bool, "invalid visibility")
        items = playlist.get("items")
        require(isinstance(items, list), "invalid playlist items")
        is_favorite = playlist["distinguished_kind"] == 52
        favorites += is_favorite
        item_ids = []
        rows = ["\t".join(FIELDS)]
        for item in items:
            require(isinstance(item, dict) and all(isinstance(item.get(k), str) for k in FIELDS)
                    and identifier(item["persistent_id"]), "invalid playlist item")
            item_ids.append(item["persistent_id"])
            rows.append("\t".join(escape(item[k]) for k in FIELDS))
        if is_favorite:
            require(items and len(set(item_ids)) == len(item_ids), "missing or duplicate favorites")
        filename = old.get(pid)
        if filename is None:
            if is_favorite and "Favorite Songs.tsv" not in old.values():
                filename = "Favorite Songs.tsv"
            elif playlist["name"] == "Noggy" and names["Noggy"] == 1 and "Noggy.tsv" not in old.values():
                filename = "Noggy.tsv"
            else:
                filename = f"playlists/{pid}.tsv"
        require(filename not in output, "duplicate output path")
        output[filename] = "\n".join(rows) + "\n"
        entry = {k: playlist[k] for k in
                 ("persistent_id", "name", "parent_id", "kind", "distinguished_kind", "visible")}
        entry.update(file=filename, item_count=len(items))
        entries.append(entry)
    require(favorites == 1, "expected exactly one built-in favorites playlist")
    index = {"schema_version": 1, "playlists": sorted(entries, key=lambda entry: int(entry["persistent_id"]))}
    output[INDEX] = json.dumps(index, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    return output, set(old.values()) - set(output)


def git(repo, *args, **kwargs):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True, **kwargs).strip()


def main():
    source, repository, blank_policy = sys.argv[1:]
    require(blank_policy in ("auto", "always", "never"), "invalid blank policy")
    repo = Path(repository)
    index_path = repo / INDEX
    previous = json.loads(index_path.read_text()) if index_path.exists() else None
    payload = json.loads(Path(source).read_text())
    output, removed = build_snapshot(payload, previous)
    known_files = {entry["file"] for entry in previous["playlists"]} if previous else set()
    # Check every target and validate the complete payload before changing any file.
    for filename in set(output) | removed:
        path = repo / filename
        require(not path.is_symlink() and not path.parent.is_symlink(), "refusing symlinked snapshot path")
        require(not path.exists() or path.is_file(), "snapshot path is not a file")
        require(not path.exists() or filename in known_files
                or filename in (INDEX, "Favorite Songs.tsv", "Noggy.tsv"),
                "refusing to overwrite an unindexed file")
    changed = {name for name, contents in output.items()
               if not (repo / name).exists() or (repo / name).read_text() != contents}
    for filename in sorted(changed):
        path = repo / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(output[filename])
    for filename in sorted(removed):
        (repo / filename).unlink(missing_ok=True)
    date = datetime.now().astimezone().isoformat(timespec="seconds")
    env = {**os.environ, "GIT_AUTHOR_DATE": date}
    if changed or removed:
        git(repo, "add", "-A", "--", *sorted(changed | removed))
        print(git(repo, "cic", "-m", "Record all playlists current state", env=env))
    elif blank_policy == "always" or (blank_policy == "auto" and time.time() - int(git(repo, "log", "-1", "--format=%ct")) > 86400):
        print(git(repo, "cic", "--allow-empty", "-m", "Record all playlists unchanged state", env=env))
    else:
        print("No playlist changes detected; blank commit skipped.")
    print(f"Captured {len(payload['playlists'])} playlists; changed files={len(changed)}; removed files={len(removed)}")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"All-playlist capture failed: {error}", file=sys.stderr)
        sys.exit(1)
