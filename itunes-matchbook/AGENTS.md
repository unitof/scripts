# AGENTS.md

## Project intent
- Build small, reusable scripts for inspecting Music.app iCloud/Match metadata.
- Keep scripts read-only against the library unless a user explicitly asks for write actions.

## Ground truth found on this machine
- Primary library package: `/Users/jacob/Music/Music/Music Library.musiclibrary`
- `Library.musicdb`/`Application.musicdb`/`Library Preferences.musicdb` are `hfma` format, not SQLite.
- Querying `cloud status` requires the `iTunesLibrary` framework (Swift), not `sqlite3` on `.musicdb`.

## Codex sandbox permissions notes
- In Codex sandboxed runs, Swift may fail writing module cache under `~/.cache/clang/ModuleCache`.
- Use `swift -module-cache-path /tmp/swift-module-cache ...` for one-liners/scripts to keep cache writes in a writable path.
- Accessing `ITLibrary(apiVersion: "1.0")` from sandbox can fail with XPC lookup restriction (`com.apple.amp.library.framework`, error `159`).
- For `iTunesLibrary` queries, run read-only Swift commands with escalated permissions when this sandbox error appears.

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
- `storePlaylistID` on `ITLibMediaItem` behaves as the album/collection Adam ID for store-linked tracks.
- `Paper Route / Audio Stories 01` removed tracks all have `storePlaylistID=1501691349` and `storeItemID` values `1501691351...1501691355`.

## Useful one-liners
- All missing/problem songs (`cloudType 0/9`):
  - `swift scripts/cloudscan.swift --status problems --limit 10000`
- Strict Apple Music songs now unavailable:
  - `swift scripts/cloudscan.swift --cloud-type 9 --limit 10000 | awk -F'\\t' 'NR==1 || $9 ~ /^Apple Music AAC audio file$/'`
- Current distinguished playlists in library:
  - `swift -e 'import iTunesLibrary; let lib = try ITLibrary(apiVersion:\"1.0\"); for p in lib.allPlaylists where p.distinguishedKind.rawValue != 0 { print(\"\\(p.distinguishedKind.rawValue)\\t\\(p.name)\\titems=\\(p.items.count)\") }'`
- Album store ID fallback for removed tracks (artist + album filter):
  - `swift -module-cache-path /tmp/swift-module-cache -e 'import Foundation; import iTunesLibrary; let lib = try ITLibrary(apiVersion: "1.0"); for i in lib.allMediaItems where (($0.artist?.name ?? "") == "Paper Route") && (($0.album.title ?? "") == "Audio Stories 01") { let o = i as NSObject; print("\\(i.title)\tstoreItemID=\\((o.value(forKey: "storeItemID") as? NSNumber)?.intValue ?? 0)\tstorePlaylistID=\\((o.value(forKey: "storePlaylistID") as? NSNumber)?.intValue ?? 0)") }'`

## Safety rules
- Never modify files under `~/Music/Music/Music Library.musiclibrary` from this repo's scripts.
- Prefer `ITLibrary` + `allMediaItems` and read-only reporting.
- Treat `cloudType` mappings as empirical unless explicitly confirmed.

## Script conventions
- Put scripts in `scripts/`.
- Keep output grep-friendly: tab-separated fields or explicit `key=value`.
- Include `--help` and `--limit` in scripts that list tracks.

## Export refresh handoff
- Current project directory: `/Users/jacob/repos/scripts/itunes-matchbook`; Git root: `/Users/jacob/repos/scripts`. Earlier names were `script-itunesmatchsearch` and `script-itunesmatchbook`.
- Latest report destination used: `/Users/jacob/Desktop/MISSINGSONGS.txt` (tab-separated despite its extension). The deleted Ben Randall album was saved separately in `MISSINGSONGS_supplement.txt` on Desktop.
- The scanner currently emits base columns only. Playback enrichment was done with temporary Swift scripts, not a committed reusable command.
- Preserve a timestamped snapshot before refreshing. Generate and validate the entire enriched export in a temporary file, then atomically replace the destination; do not truncate a valuable report before the library query succeeds.
- Supplemental columns previously exported: `Play Count`, `Last Played`, `Skip Count`, `Skip Date`, `Play Status`, `Rating`, `Rating Computed`. These were report labels, not verified Music UI names. Rating/favorite are user actions, not automatic playback updates.
- Query playback fields directly from each selected media item in the same library snapshot. Preserve `persistentID` in future exports for precise identity. Never pick an arbitrary first match by store ID: catalog IDs can be shared by originals and replacement copies.
- Compare row identities, not complete rows whose counters/dates change. Report additions and removals separately. Leaving the problem report does not prove a song was deleted: its cloud state may have changed.
- `cloudType=0` alone does not prove failure: newly imported local Gem tracks also had code 0. Distinguish local imports from remote problem entries using location fields.
- The Apple Music AAC kind filter identifies a subset, not all Apple Music acquisitions; known unavailable examples such as Vampire Pills had plain AAC kind.
- Favorite playlist membership (kind 52) is an observable proxy, not proof of the exact on-disk favorite storage layout. Its membership and Applications absence were historical observations; query afresh.
- No play-count write or migration was performed. The Gem originals disappeared, but the mechanism (automatic replacement versus user deletion) was not established.
