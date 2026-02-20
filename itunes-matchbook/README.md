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
| `2` | Matched | High | Manually confirmed in Music.app (`Such Great Heights`, `Brother, Sister`) plus cloud-backed behavior in data. |
| `3` | Uploaded | High | 100% `storeItemID = 0`, mostly personal-file kinds (`MPEG audio`, `AAC`). |
| `8` | Subscription (Apple Music) | High | Dominated by `Apple Music AAC audio file`; all have `storeItemID > 0`. |
| `9` | No Longer Available | Medium-High | Confirmed for at least one track in Music UI: `Vampire Pills` showed `Cloud Status: No Longer Available` and has `cloudType=9`. |
| `0` | Waiting / unavailable cloud item | Medium | Confirmed `Waiting` on `Lord, Save Me from Myself` (AAC copy); `The First Noel` shows cloud location with no status and download failures (`This item cannot be downloaded`, error `7608`). |

## Manual confirmations (2026-02-20)
- `Such Great Heights` (Fake Dad, `cloudType=2`) -> `Cloud Status: Matched`
- `Brother, Sister` (Beta Radio, `cloudType=2`) -> `Cloud Status: Matched`
- `Lord, Save Me from Myself` (Jon Foreman, AAC copy, `cloudType=0`) -> `Cloud Status: Waiting`
- `The First Noel` (Carinthia, `cloudType=0`) -> `Location: Cloud`, no status shown in Info, and download errors in Music.app:
  - `This item cannot be downloaded`
  - `An unknown error occurred (7608)`
  - Same failure reproduced from iOS

## Error correlation (The First Noel)
Exact error strings observed:
- iOS: `This item cannot be downloaded. The item you have requested is not available for download.`
- macOS: `This item cannot be downloaded.`
- macOS: `There was a problem downloading “The First Noel / The First Noel - Single / Carinthia”. An unknown error occurred (7608).`

Library-field correlation for this failing entry:
- `cloudType=0` (`waiting_or_unavailable`)
- `locationType=3` (`Cloud`)
- `isCloud=1`
- `hasLocation=0` (no local file URL)
- `storeItemID=0`
- `kind=MPEG audio file`

## Remaining uncertainty
- `cloudType=0` may include more than one failure subtype (for example, explicit `Waiting` vs no status text + download error). More examples will sharpen this.

## Script
Initial helper script:
- `scripts/cloudscan.swift`

Examples:

```bash
swift scripts/cloudscan.swift --counts
swift scripts/cloudscan.swift --find-title "Vampire Pills"
swift scripts/cloudscan.swift --cloud-type 9 --limit 50
swift scripts/cloudscan.swift --status matched --limit 50
swift scripts/cloudscan.swift --problems --limit 200
```

## Notes for future scripts
- Keep operations read-only.
- Build focused scripts rather than one large tool.
- Prefer explicit outputs that are easy to diff and pipe into `rg`, `sort`, or `jq`.
