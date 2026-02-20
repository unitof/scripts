# AGENTS.md

## Project intent
- Build small, reusable scripts for inspecting Music.app iCloud/Match metadata.
- Keep scripts read-only against the library unless a user explicitly asks for write actions.

## Ground truth found on this machine
- Primary library package: `/Users/jacob/Music/Music/Music Library.musiclibrary`
- `Library.musicdb`/`Application.musicdb`/`Library Preferences.musicdb` are `hfma` format, not SQLite.
- Querying `cloud status` requires the `iTunesLibrary` framework (Swift), not `sqlite3` on `.musicdb`.

## Session handoff (important when chat history is missing)
- Confirmed cloudType meanings in this library:
  - `0` = waiting/unavailable problem state
  - `1` = purchased
  - `2` = matched
  - `3` = uploaded
  - `8` = Apple Music subscription
  - `9` = no longer available
- `Loved/Favorite` is not exposed as a per-track `ITLibMediaItem` field via this API.
- Derive favorite state via distinguished playlist kind `52` (`Favorite Songs` in this library).
- Distinguished playlist kind `51` (Applications) is not present in this library.
- Re-adding deleted/lost songs can replace old entries (same song metadata, new persistent IDs), and old play counts can be lost if the original rows are removed.
- `Breanne Düren - Gem - EP` case: only re-added copies remained, all at `playCount=0`; no in-library old copies remained to transfer from.
- Avoid probing unknown KVC keys directly on `ITLibMediaItem`; undefined keys can crash Swift with `NSUnknownKeyException`.

## Useful one-liners
- All missing/problem songs (`cloudType 0/9`):
  - `swift scripts/cloudscan.swift --status problems --limit 10000`
- Strict Apple Music songs now unavailable:
  - `swift scripts/cloudscan.swift --cloud-type 9 --limit 10000 | awk -F'\\t' 'NR==1 || $9 ~ /^Apple Music AAC audio file$/'`
- Current distinguished playlists in library:
  - `swift -e 'import iTunesLibrary; let lib = try ITLibrary(apiVersion:\"1.0\"); for p in lib.allPlaylists where p.distinguishedKind.rawValue != 0 { print(\"\\(p.distinguishedKind.rawValue)\\t\\(p.name)\\titems=\\(p.items.count)\") }'`

## Safety rules
- Never modify files under `~/Music/Music/Music Library.musiclibrary` from this repo's scripts.
- Prefer `ITLibrary` + `allMediaItems` and read-only reporting.
- Treat `cloudType` mappings as empirical unless explicitly confirmed.

## Script conventions
- Put scripts in `scripts/`.
- Keep output grep-friendly: tab-separated fields or explicit `key=value`.
- Include `--help` and `--limit` in scripts that list tracks.
