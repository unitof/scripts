#!/bin/zsh
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export GIT_TERMINAL_PROMPT=0
export GIT_SSH_COMMAND="/usr/bin/ssh -o BatchMode=yes -o ConnectTimeout=15"
script_dir=${0:A:h}
playlist_repo=${APPLE_MUSIC_HISTORY_REPO:-$HOME/repos/apple-music-playlist-history}

echo "$(date -Iseconds) Starting Favorite Songs daily capture"
if "$script_dir/capture_current_snapshot.zsh" --playlist-repo "$playlist_repo" --blank=always --push; then
  echo "$(date -Iseconds) Capture and push succeeded"
else
  result=$?
  echo "$(date -Iseconds) Capture or push failed (exit=$result); inspect daily.error.log" >&2
  exit "$result"
fi
