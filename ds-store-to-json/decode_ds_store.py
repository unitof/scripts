#!/usr/bin/env python3
"""Decode a .DS_Store file and emit JSON."""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import plistlib
import sys
from pathlib import Path
from typing import Any

try:
    from ds_store import DSStore
except ImportError:
    print(
        "Missing dependency: ds-store\nInstall with: python3 -m pip install ds-store",
        file=sys.stderr,
    )
    raise SystemExit(2)


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()

    if isinstance(value, bytes):
        if value.startswith(b"bplist00"):
            try:
                return {
                    "encoding": "bplist",
                    "value": _json_safe(plistlib.loads(value)),
                }
            except Exception:
                pass
        return {
            "encoding": "base64",
            "value": base64.b64encode(value).decode("ascii"),
        }

    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]

    if hasattr(value, "_asdict"):
        return _json_safe(value._asdict())

    if hasattr(value, "__dict__"):
        return _json_safe(vars(value))

    return repr(value)


def decode_ds_store(path: Path) -> dict[str, Any]:
    records: list[dict[str, Any]] = []

    with DSStore.open(str(path), "r") as ds:
        for rec in ds:
            records.append(
                {
                    "filename": rec.filename,
                    "code": rec.code,
                    "type": rec.type,
                    "value": _json_safe(rec.value),
                }
            )

    return {
        "path": str(path.resolve()),
        "record_count": len(records),
        "records": records,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Decode a .DS_Store file and emit JSON."
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".DS_Store",
        help="Path to .DS_Store (default: ./.DS_Store)",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Write JSON to this file instead of stdout",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="JSON indentation (default: 2)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    path = Path(args.path)
    if not path.exists():
        print(f"File not found: {path}", file=sys.stderr)
        return 1

    payload = decode_ds_store(path)
    data = json.dumps(payload, indent=args.indent, sort_keys=True)

    if args.output:
        Path(args.output).write_text(data + "\n", encoding="utf-8")
    else:
        print(data)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
