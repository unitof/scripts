# AGENTS.md

## Project intent
- Build small, reusable scripts for inspecting Music.app iCloud/Match metadata.
- Keep scripts read-only against the library unless a user explicitly asks for write actions.

## Ground truth found on this machine
- Primary library package: `/Users/jacob/Music/Music/Music Library.musiclibrary`
- `Library.musicdb`/`Application.musicdb`/`Library Preferences.musicdb` are `hfma` format, not SQLite.
- Querying `cloud status` requires the `iTunesLibrary` framework (Swift), not `sqlite3` on `.musicdb`.

## Safety rules
- Never modify files under `~/Music/Music/Music Library.musiclibrary` from this repo's scripts.
- Prefer `ITLibrary` + `allMediaItems` and read-only reporting.
- Treat `cloudType` mappings as empirical unless explicitly confirmed.

## Script conventions
- Put scripts in `scripts/`.
- Keep output grep-friendly: tab-separated fields or explicit `key=value`.
- Include `--help` and `--limit` in scripts that list tracks.

