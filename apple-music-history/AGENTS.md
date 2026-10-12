# Playlist History Handoff

- Scripts live here within the `~/repos/scripts` Git repository.
- Data lives in a separate Git checkout at `~/repos/apple-music-playlist-history`, remote `git@github.com:unitof/apple-music-playlist-history.git`.
- The Drive item named Apple Music Playlist History is a Finder alias. Do not pass it as `--playlist-repo`. Its target checkout was missing on October 11, 2026 and was restored from GitHub; do not assume unpushed history was recovered.
- When asked to update, commit documentation changes first, then wrapper/code changes if needed, then capture and commit playlist data. Stage only relevant files and use `git cic` for the configured co-author trailer.
- Inspect both repositories for pending changes first. Capture refuses a dirty data checkout; preserve unrelated work.
- Run `scripts/capture_current_snapshot.zsh --playlist-repo "$HOME/repos/apple-music-playlist-history"`. It reads Music through iTunesLibrary without modifying the library and captures only Favorite Songs.
- Verify the export is nonempty and has the expected header before accepting a large diff. Compare membership by persistent_id using `scripts/diff_playlist_states.py`; framework ordering can cause noisy line diffs.
- Capture commits locally but does not push. When asked to sync, push the data repository and report additions/removals and the commit. Push requested docs changes as appropriate too.
- Never directly edit Music database files or switch library preferences to take a snapshot.
