#!/usr/bin/env zsh
set -euo pipefail

script_dir=${0:A:h}
playlist_repo=${APPLE_MUSIC_HISTORY_REPO:-$PWD}
blank_policy=auto
playlist_file="Favorite Songs.tsv"
push_after=no

usage() {
  cat <<'EOF'
usage: capture_current_snapshot.zsh [--playlist-repo PATH] [--blank=auto|always|never] [--push]

Exports the current local Music.app Favorite Songs playlist and commits it in
the playlist-history repo.

Blank commit policy:
  auto    create a blank commit only when no changes are detected and the last
          commit is more than 24 hours old (default)
  always  create a blank commit whenever no changes are detected
  never   never create a blank commit when no changes are detected
EOF
}

while (( $# )); do
  case "$1" in
    --playlist-repo)
      playlist_repo=$2
      shift 2
      ;;
    --playlist-repo=*)
      playlist_repo=${1#*=}
      shift
      ;;
    --blank=*)
      blank_policy=${1#*=}
      shift
      ;;
    --no-blank)
      blank_policy=never
      shift
      ;;
    --push)
      push_after=yes
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

case "$blank_policy" in
  auto|always|never) ;;
  *)
    echo "--blank must be one of: auto, always, never" >&2
    exit 2
    ;;
esac

playlist_repo=${playlist_repo:A}
target=$playlist_repo/$playlist_file

if [[ ! -d "$playlist_repo/.git" ]]; then
  echo "not a git repo: $playlist_repo" >&2
  exit 1
fi

zmodload zsh/system
lock_file="$playlist_repo/.git/apple-music-snapshot.lock"
touch "$lock_file"
if ! zsystem flock -t 0 -f lock_fd "$lock_file"; then
  echo "another playlist capture is running" >&2
  exit 1
fi

if [[ -n "$(git -C "$playlist_repo" status --porcelain)" ]]; then
  echo "playlist repo has uncommitted changes; refusing to overwrite snapshot" >&2
  git -C "$playlist_repo" status --short >&2
  exit 1
fi

tmp=$(mktemp "${TMPDIR:-/tmp}/applemusic-favorite-songs.XXXXXX")
trap 'rm -f "$tmp"' EXIT

export_command=(swift "$script_dir/export_current_favorite_songs.swift")
if [[ -n ${APPLE_MUSIC_HISTORY_EXPORTER:-} ]]; then
  export_command=("$APPLE_MUSIC_HISTORY_EXPORTER")
fi
/usr/bin/perl -e 'alarm 120; exec {$ARGV[0]} @ARGV or die "exec failed: $!\n"' \
  "${export_command[@]}" > "$tmp"

if ! awk -F '\t' '
  NR == 1 { if ($0 != "persistent_id\ttitle\tartist\talbum\turl") exit 1; next }
  NF != 5 || $1 !~ /^[0-9]+$/ || seen[$1]++ { bad = 1 }
  END { if (NR < 2 || bad) exit 1 }
' "$tmp"; then
  echo "empty or malformed playlist export; refusing to overwrite snapshot" >&2
  exit 1
fi

snapshot_date=$(date +%Y-%m-%dT%H:%M:%S%z)

if [[ ! -f "$target" ]] || ! cmp -s "$tmp" "$target"; then
  cp "$tmp" "$target"
  git -C "$playlist_repo" add "$playlist_file"
  GIT_AUTHOR_DATE="$snapshot_date" git -C "$playlist_repo" cic -m "Record Favorite Songs current state"
else
  should_blank=no
  case "$blank_policy" in
  always)
    should_blank=yes
    ;;
  never)
    should_blank=no
    ;;
  auto)
    last_commit_epoch=$(git -C "$playlist_repo" log -1 --format=%ct 2>/dev/null || echo 0)
    now_epoch=$(date +%s)
    if (( now_epoch - last_commit_epoch > 86400 )); then
      should_blank=yes
    fi
    ;;
  esac

  if [[ "$should_blank" == yes ]]; then
    GIT_AUTHOR_DATE="$snapshot_date" git -C "$playlist_repo" cic --allow-empty -m "Record Favorite Songs unchanged state"
  else
    echo "No playlist changes detected; blank commit skipped (policy=$blank_policy)."
  fi
fi

if [[ "$push_after" == yes ]]; then
  git -C "$playlist_repo" push
fi
