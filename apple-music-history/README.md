# Apple Music History Scripts

Small utilities for preserving Apple Music playlist states as git history.

The data repository lives separately at:

`~/Library/CloudStorage/GoogleDrive-j@cobford.com/My Drive/Filing Cabinet/Account Data Exports & Backups/Apple Music Playlist History`

Current conventions:

- One playlist per file.
- `Favorite Songs.tsv` is tab-separated with columns:
  `persistent_id`, `title`, `artist`, `album`, `url`.
- Historical commits use `GIT_AUTHOR_DATE` for the playlist state date.
- Commit dates are the actual date the history repo was updated.

## Scripts

- `scripts/export_current_favorite_songs.swift`: exports the current Apple built-in `Favorite Songs` playlist through `iTunesLibrary.framework`.
- `scripts/march_csv_to_playlist_tsv.py`: converts the recovered March 6 parser CSV into the canonical playlist TSV.
- `scripts/diff_playlist_states.py`: compares two canonical playlist TSV files by `persistent_id`.
