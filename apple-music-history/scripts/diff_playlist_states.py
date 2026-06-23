#!/usr/bin/env python3
import csv
import sys


def read_tsv(path: str) -> dict[str, dict[str, str]]:
    with open(path, newline="") as file:
        return {row["persistent_id"]: row for row in csv.DictReader(file, delimiter="\t")}


def sort_key(row: dict[str, str]) -> tuple[str, str, str, str]:
    return (
        row.get("artist", "").casefold(),
        row.get("album", "").casefold(),
        row.get("title", "").casefold(),
        row.get("persistent_id", ""),
    )


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: diff_playlist_states.py OLD.tsv NEW.tsv", file=sys.stderr)
        return 2

    old = read_tsv(sys.argv[1])
    new = read_tsv(sys.argv[2])

    added = sorted((new[key] for key in set(new) - set(old)), key=sort_key)
    removed = sorted((old[key] for key in set(old) - set(new)), key=sort_key)

    print(f"old={len(old)}")
    print(f"new={len(new)}")
    print(f"common={len(set(old) & set(new))}")
    print(f"added={len(added)}")
    for row in added:
        print(f"+\t{row['persistent_id']}\t{row['title']}\t{row['artist']}\t{row['album']}")
    print(f"removed={len(removed)}")
    for row in removed:
        print(f"-\t{row['persistent_id']}\t{row['title']}\t{row['artist']}\t{row['album']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
