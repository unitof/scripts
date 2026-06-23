#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable


DEFAULT_BZ_DONE_DIR = Path("/Library/Backblaze.bzpkg/bzdata/bzbackup/bzdatacenter")
DEFAULT_TARGET = "/Users/jacob/Music/Music/Music Library.musiclibrary/Library.musicdb"


@dataclass(frozen=True)
class MusicDbVersion:
    uploaded_at: datetime
    action: str
    file_id: str
    sha1: str
    size: int
    path: str
    log_file: str
    line_number: int

    @property
    def iso_week(self) -> str:
        year, week, _ = self.uploaded_at.isocalendar()
        return f"{year}-W{week:02d}"


def parse_backblaze_timestamp(value: str) -> datetime:
    return datetime.strptime(value, "%Y%m%d%H%M%S")


def iter_versions(bz_done_dir: Path, target_path: str) -> Iterable[MusicDbVersion]:
    target_bytes = target_path.encode()

    for log_path in sorted(bz_done_dir.glob("bz_done_*_0.dat")):
        with log_path.open("rb") as file:
            for line_number, raw_line in enumerate(file, 1):
                if target_bytes not in raw_line:
                    continue

                line = raw_line.decode("utf-8", "replace").rstrip("\n")
                parts = line.split("\t")
                if len(parts) < 14 or parts[-1] != target_path:
                    continue

                action = parts[1]
                if action != "+":
                    continue

                size = int(parts[12]) if parts[12].isdigit() else 0
                yield MusicDbVersion(
                    uploaded_at=parse_backblaze_timestamp(parts[3]),
                    action=action,
                    file_id=parts[4],
                    sha1=parts[8],
                    size=size,
                    path=parts[-1],
                    log_file=str(log_path),
                    line_number=line_number,
                )


def latest_per_week(versions: Iterable[MusicDbVersion]) -> list[MusicDbVersion]:
    selected: dict[str, MusicDbVersion] = {}
    for version in versions:
        current = selected.get(version.iso_week)
        if current is None or version.uploaded_at > current.uploaded_at:
            selected[version.iso_week] = version
    return [selected[key] for key in sorted(selected)]


def write_tsv(rows: Iterable[MusicDbVersion], output_path: Path) -> None:
    fieldnames = [
        "iso_week",
        "uploaded_at",
        "suggested_restore_to",
        "size",
        "sha1",
        "file_id",
        "path",
        "log_file",
        "line_number",
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            # Backblaze's Computer Backup UI is point-in-time. Use the next
            # minute in the UI so this uploaded version exists in the restore view.
            restore_to = row.uploaded_at.replace(second=0)
            if row.uploaded_at.second:
                restore_to += timedelta(minutes=1)

            writer.writerow({
                "iso_week": row.iso_week,
                "uploaded_at": row.uploaded_at.isoformat(sep=" "),
                "suggested_restore_to": restore_to.isoformat(sep=" "),
                "size": row.size,
                "sha1": row.sha1,
                "file_id": row.file_id,
                "path": row.path,
                "log_file": row.log_file,
                "line_number": row.line_number,
            })


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a Backblaze weekly restore manifest for Apple Music Library.musicdb."
    )
    parser.add_argument("--bz-done-dir", type=Path, default=DEFAULT_BZ_DONE_DIR)
    parser.add_argument("--target-path", default=DEFAULT_TARGET)
    parser.add_argument("--since", default="2025-06-22", help="inclusive YYYY-MM-DD cutoff")
    parser.add_argument("--output", type=Path, default=Path("data/backblaze-weekly-musicdb.tsv"))
    parser.add_argument("--all-output", type=Path, default=Path("data/backblaze-all-musicdb.tsv"))
    args = parser.parse_args()

    since = datetime.strptime(args.since, "%Y-%m-%d")
    versions = [version for version in iter_versions(args.bz_done_dir, args.target_path) if version.uploaded_at >= since]
    weekly = latest_per_week(versions)

    write_tsv(versions, args.all_output)
    write_tsv(weekly, args.output)

    print(f"uploaded_versions={len(versions)}")
    print(f"unique_sha1s={len({version.sha1 for version in versions})}")
    print(f"weekly_samples={len(weekly)}")
    print(f"all_output={args.all_output}")
    print(f"weekly_output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
