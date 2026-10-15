# Apple Music History Scripts

Small utilities for preserving Apple Music playlist states as git history.

The data repository lives separately at `~/repos/apple-music-playlist-history`
with remote `git@github.com:unitof/apple-music-playlist-history.git`.
The following Drive location is a Finder alias, not a directory usable by shell scripts:

`~/Library/CloudStorage/GoogleDrive-j@cobford.com/My Drive/Filing Cabinet/Account Data Exports & Backups/Apple Music Playlist History`

## Current Conventions

- One playlist per file.
- `Favorite Songs.tsv` is tab-separated with columns:
  `persistent_id`, `title`, `artist`, `album`, `url`.
- Historical commits use `GIT_AUTHOR_DATE` for the playlist state date.
- Commit dates are the actual date the history repo was updated.
- Use `git cic` for commits so the Codex co-author trailer is included.

## Scripts

- `scripts/export_current_favorite_songs.swift`: exports Favorite Songs (by distinguished kind 52), or a named playlist via `--playlist NAME`, through `iTunesLibrary.framework`. The filename is retained for compatibility.
- `scripts/backblaze_musicdb_manifest.py`: parses local Backblaze `bz_done_*.dat` logs and creates weekly `Library.musicdb` restore manifests.
- `scripts/march_csv_to_playlist_tsv.py`: converts the recovered March 6 parser CSV into the canonical playlist TSV.
- `scripts/diff_playlist_states.py`: compares two canonical playlist TSV files by `persistent_id`.
- `scripts/capture_current_snapshot.zsh`: exports and validates requested playlists before updating and committing their individual TSV files. Repeat `--playlist NAME` to capture several in one commit; default is Favorite Songs only.

## Backblaze Credentials

The local manifest step does not need API keys:

```zsh
scripts/backblaze_musicdb_manifest.py
```

It writes:

- `data/backblaze-all-musicdb.tsv`
- `data/backblaze-weekly-musicdb.tsv`

For API/automation work, copy `.env.example` to `.env` and fill only what is needed. The `.env` file is git-ignored.

Backblaze B2 keys come from the Backblaze web console:

1. Sign in to Backblaze.
2. Go to **B2 Cloud Storage**.
3. Open **Application Keys**.
4. Choose **Add a New Application Key**.
5. Prefer a least-privilege key for the restore bucket/snapshot, with read/list permissions.
6. Copy the key ID and application key immediately; Backblaze only shows the secret key once.

Important: B2 application keys are for B2 Cloud Storage. They are useful after a Computer Backup restore is saved to B2, but they do not appear to initiate Computer Backup restores by themselves. Creating the point-in-time Computer Backup restore may still require browser/session automation against the Backblaze web console.

## Capture Current State

From the playlist-history repo, the minimal command is:

```zsh
/Users/jacob/repos/scripts/apple-music-history/scripts/capture_current_snapshot.zsh
```

Or explicitly:

```zsh
/Users/jacob/repos/scripts/apple-music-history/scripts/capture_current_snapshot.zsh \
  --playlist-repo "$HOME/repos/apple-music-playlist-history"
```

Blank commit policy is controlled with `--blank=auto|always|never`.

- `auto` is the default: if no playlist change is detected, create a blank commit only when the last commit is more than 24 hours old.
- `always` records every successful no-change capture.
- `never` skips no-change captures.

Capture commits locally; run `git push` in the data repository to sync GitHub.
The daily job and the data repo's `npm run snapshot` capture Favorite Songs and
Noggy. To capture both directly, append `--playlist "Favorite Songs" --playlist Noggy`.
Every requested playlist must exist uniquely and be nonempty; if an export
fails, no playlist file is updated. This intentionally refuses emptying/deletion
until manually reviewed. Playlist names containing slashes are not supported.
Named playlists may contain repeated tracks; order and occurrences are preserved.
Only built-in Favorite Songs requires unique persistent IDs. The existing
`diff_playlist_states.py` compares distinct IDs, not repeated occurrences.

## Daily Capture Without An LLM

Install a per-user macOS LaunchAgent (default: 10:00 AM local time):

```zsh
python3 scripts/install_daily_agent.py
```

Use `--include-noggy` to include Noggy in the scheduled job. For the existing
public-upload workflow, use `--include-noggy --push` after explicitly approving
publication of Noggy's metadata and local file URLs. Without this flag, the
schedule continues to capture Favorite Songs only.

Use `--hour 14 --minute 30` to choose a different time. This generates
`~/Library/LaunchAgents/com.unitof.apple-music-history.plist` and loads it.
The Mac must be logged in; missed runs during sleep are coalesced on wake.
No Codex automation, model invocation, or API key is involved. The installer
compiles and ad-hoc signs the Swift exporter once under
`~/Library/Application Support/apple-music-history/export-favorite-songs`;
the daily job runs that binary without invoking the Swift compiler. Reinstall
after changing exporter source or upgrading the toolchain/OS.

The daily job exports Favorite Songs and Noggy into separate TSV files and commits changed states (or an unchanged
state for each successful daily run). It captures locally by default. Install
with `--push` only after approving uploads to the configured Git upstream:
`unitof/apple-music-playlist-history` was PUBLIC when checked on October 14, 2026.
The TSVs include song metadata, persistent IDs, and local file URLs. The user
approved public daily uploads and subsequently requested Noggy in the same workflow.
It does not force an Apple cloud sync, change Music.app, or
rewrite Git history. Keep Music's local library synced separately.

It uses a repository lock, refuses dirty checkouts, times out exports after
120 seconds, and rejects empty/malformed snapshots. Push failures leave local
commits intact for the next run; remote divergence needs manual resolution.
Git SSH runs noninteractively, so unattended access must already work. The
existing `git cic` helper supplies commit trailers; it does not invoke an LLM.

Logs: `~/Library/Logs/apple-music-history/daily.log` and `daily.error.log`.

```zsh
launchctl print gui/$(id -u)/com.unitof.apple-music-history
launchctl kickstart gui/$(id -u)/com.unitof.apple-music-history
launchctl bootout gui/$(id -u)/com.unitof.apple-music-history
```

To permanently uninstall, unload first and remove only the generated plist.
The script source and playlist history remain in their existing repositories.

The scheduler uses Apple's [per-user LaunchAgent mechanism](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html).
Live interpreted Swift jobs timed out during compiler import resolution despite
direct exports succeeding. The installer uses Standard limits and a precompiled
exporter to avoid compilation in launchd. Retest through
launchctl after changes, and never infer success from loading the plist alone.

## Historical Investigation (June 2026)

- The playlist-history repo initially had two known states for `Favorite Songs.tsv`.
- The March 6 state came from a Time Machine `Library.musicdb` snapshot at `2026-03-06-114914`.
- The current state came from `iTunesLibrary.framework` against the live local Music.app library on `2026-06-22`.
- The March 6 database used Apple Music's private `hfma` format. The useful parser probe was a relaxed scratch run of `rinsuki/musicdb2sqlite`; it interpreted `rate_like = 2` as the Favorite Songs candidate.
- Time Machine only exposed one useful historical snapshot on `/Volumes/The Hold`.
- Backblaze local `bz_done_*.dat` logs remain the likely source for deeper historical `Library.musicdb` versions. Keep Backblaze/Time Machine recovery code here, not in the playlist-history repo.

## Notes for Continued Work

- The live export path is supported by Apple's public `iTunesLibrary.framework`; no Music.app preference switching is needed.
- The export preserves the order returned by `iTunesLibrary.framework`, matching the current committed playlist file.
- If a future parser/exporter changes ordering, expect a noisy one-time diff unless the existing history is rewritten or normalized.
- The playlist-history repo should remain mostly data: `Favorite Songs.tsv`, README, and a tiny command wrapper only.
