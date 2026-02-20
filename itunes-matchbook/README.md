# script-itunesmatchsearch

Read-only tooling for Music.app iCloud/Match analysis on macOS.

## What we confirmed (2026-02-20)
- Primary library package is:
  - `/Users/jacob/Music/Music/Music Library.musiclibrary`
- These files are not SQLite (they are Apple `hfma` format):
  - `Library.musicdb`
  - `Application.musicdb`
  - `Library Preferences.musicdb`
- `sqlite3` cannot query them (`Error: file is not a database`).
- The queryable path for per-track cloud metadata is Swift + `iTunesLibrary` framework (`ITLibrary` / `ITLibMediaItem`).

## Useful fields for this project
- Public:
  - `isCloud` (bool)
  - `locationType` (`1` local file, `3` remote/cloud)
  - `kind`
  - `storeItemID`
- Private (via KVC, empirically available):
  - `cloudType`
  - `cloudPlaybackEndpointType`
  - `subscriptionAdamID`
  - `cloudUniversalLibraryID`

## Observed cloudType distribution (16,686 media items)
- `cloudType=8`: 10,000
- `cloudType=2`: 2,315
- `cloudType=3`: 2,198
- `cloudType=1`: 2,011
- `cloudType=9`: 131
- `cloudType=0`: 31

## Provisional cloudType mapping
These mappings are inferred from local evidence and should be treated as provisional unless noted.

| cloudType | Proposed status | Confidence | Why |
|---|---|---|---|
| `1` | Purchased | High | 100% `storeItemID > 0`; mostly `Purchased AAC audio file`, `Purchased MPEG-4 video file`, digital booklets. |
| `2` | Matched | Medium | Mostly `storeItemID > 0`, non-purchased file kinds (`AAC`, `MP3`), cloud-backed behavior. |
| `3` | Uploaded | High | 100% `storeItemID = 0`, mostly personal-file kinds (`MPEG audio`, `AAC`). |
| `8` | Subscription (Apple Music) | High | Dominated by `Apple Music AAC audio file`; all have `storeItemID > 0`. |
| `9` | No Longer Available | Medium-High | Confirmed for at least one track in Music UI: `Vampire Pills` showed `Cloud Status: No Longer Available` and has `cloudType=9`. |
| `0` | Unknown (legacy/error/ineligible class) | Low | Rare (`31` items), `storeItemID = 0`, remote/cloud only in this library. Needs manual confirmation. |

## Manual checks requested
If you can open Info in Music.app and tell us `Cloud Status` for these example tracks, we can lock down uncertain mappings:

- For `cloudType=2` (currently "Matched", medium confidence):
  - `Such Great Heights` by Fake Dad
  - `Brother, Sister` by Beta Radio
- For `cloudType=0` (unknown):
  - `The First Noel` by Carinthia
  - `Lord, Save Me from Myself` by Jon Foreman

## Script
Initial helper script:
- `scripts/cloudscan.swift`

Examples:

```bash
swift scripts/cloudscan.swift --counts
swift scripts/cloudscan.swift --find-title "Vampire Pills"
swift scripts/cloudscan.swift --cloud-type 9 --limit 50
```

## Notes for future scripts
- Keep operations read-only.
- Build focused scripts rather than one large tool.
- Prefer explicit outputs that are easy to diff and pipe into `rg`, `sort`, or `jq`.

