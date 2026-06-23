#!/usr/bin/env python3
import csv
import sys


def normalize_signed_64(value: str) -> str:
    number = int(value)
    if number < 0:
        number += 1 << 64
    return str(number)


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: march_csv_to_playlist_tsv.py INPUT.csv OUTPUT.tsv", file=sys.stderr)
        return 2

    input_path, output_path = sys.argv[1], sys.argv[2]

    with open(input_path, newline="") as input_file:
        rows = list(csv.DictReader(input_file))

    rows.sort(key=lambda row: (
        (row.get("artist") or "").casefold(),
        (row.get("album") or "").casefold(),
        (row.get("title") or "").casefold(),
        normalize_signed_64(row["id"]),
    ))

    with open(output_path, "w", newline="") as output_file:
        writer = csv.writer(output_file, delimiter="\t", lineterminator="\n")
        writer.writerow(["persistent_id", "title", "artist", "album", "url"])
        for row in rows:
            writer.writerow([
                normalize_signed_64(row["id"]),
                row.get("title", ""),
                row.get("artist", ""),
                row.get("album", ""),
                row.get("url", ""),
            ])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
