# Apple Music History Scripts

Small utilities for preserving Apple Music playlist states as git history.

The data repository lives separately at:

`~/Library/CloudStorage/GoogleDrive-j@cobford.com/My Drive/Filing Cabinet/Account Data Exports & Backups/Apple Music Playlist History`

## Current Conventions

- One playlist per file.
- `Favorite Songs.tsv` is tab-separated with columns:
  `persistent_id`, `title`, `artist`, `album`, `url`.
- Historical commits use `GIT_AUTHOR_DATE` for the playlist state date.
- Commit dates are the actual date the history repo was updated.
- Use `git cic` for commits so the Codex co-author trailer is included.

## Scripts

- `scripts/export_current_favorite_songs.swift`: exports the current Apple built-in `Favorite Songs` playlist through `iTunesLibrary.framework`.
- `scripts/march_csv_to_playlist_tsv.py`: converts the recovered March 6 parser CSV into the canonical playlist TSV.
- `scripts/diff_playlist_states.py`: compares two canonical playlist TSV files by `persistent_id`.
- `scripts/capture_current_snapshot.zsh`: exports the current local `Favorite Songs.tsv` and commits it in the playlist-history repo.

## Capture Current State

From the playlist-history repo, the minimal command is:

```zsh
/Users/jacob/repos/script-applemusichistory/scripts/capture_current_snapshot.zsh
```

Or explicitly:

```zsh
/Users/jacob/repos/script-applemusichistory/scripts/capture_current_snapshot.zsh \
  --playlist-repo "$HOME/Library/CloudStorage/GoogleDrive-j@cobford.com/My Drive/Filing Cabinet/Account Data Exports & Backups/Apple Music Playlist History"
```

Blank commit policy is controlled with `--blank=auto|always|never`.

- `auto` is the default: if no playlist change is detected, create a blank commit only when the last commit is more than 24 hours old.
- `always` records every successful no-change capture.
- `never` skips no-change captures.

## Current State of the Investigation

- The playlist-history repo currently has two known states for `Favorite Songs.tsv`.
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
