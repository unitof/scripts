#!/usr/bin/env zsh
set -euo pipefail

script_dir=${0:A:h}
playlist_repo=${APPLE_MUSIC_HISTORY_REPO:-$PWD}
blank_policy=auto
playlist_names=()
push_after=no

usage() {
  cat <<'EOF'
usage: capture_current_snapshot.zsh [--playlist-repo PATH] [--playlist NAME ...] [--blank=auto|always|never] [--push]

Exports requested local Music.app playlists and commits them together in
the playlist-history repo. Default: Favorite Songs. Repeat --playlist for more.

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
      (( $# >= 2 )) || { usage >&2; exit 2; }
      playlist_repo=$2
      shift 2
      ;;
    --playlist)
      (( $# >= 2 )) || { usage >&2; exit 2; }
      playlist_names+=("$2")
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

(( ${#playlist_names} )) || playlist_names=("Favorite Songs")
typeset -A seen_names
for name in "${playlist_names[@]}"; do
  if [[ -z $name || $name == */* || $name == *$'\n'* || $name == *$'\r'* || $name == *$'\t'* || -n ${seen_names[$name]:-} ]]; then
    echo "invalid or duplicate playlist name: $name" >&2
    exit 2
  fi
  seen_names[$name]=1
done
playlist_repo=${playlist_repo:A}

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

temporary=$(mktemp -d "${TMPDIR:-/tmp}/applemusic-playlists.XXXXXX")
trap 'rm -rf "$temporary"' EXIT

export_command=(swift "$script_dir/export_current_favorite_songs.swift")
if [[ -n ${APPLE_MUSIC_HISTORY_EXPORTER:-} ]]; then
  export_command=("$APPLE_MUSIC_HISTORY_EXPORTER")
fi
playlist_files=()
changed=no
for name in "${playlist_names[@]}"; do
  playlist_file="$name.tsv"
  playlist_files+=("$playlist_file")
  tmp="$temporary/$playlist_file"
  /usr/bin/perl -e 'alarm 120; exec {$ARGV[0]} @ARGV or die "exec failed: $!\n"' \
    "${export_command[@]}" --playlist "$name" > "$tmp"

  unique_ids=no
  if [[ $name == "Favorite Songs" ]]; then
    unique_ids=yes
  fi
  if ! awk -F '\t' -v unique_ids="$unique_ids" '
  NR == 1 { if ($0 != "persistent_id\ttitle\tartist\talbum\turl") exit 1; next }
  NF != 5 || $1 !~ /^[0-9]+$/ || (unique_ids == "yes" && seen[$1]++) { bad = 1 }
  END { if (NR < 2 || bad) exit 1 }
' "$tmp"; then
    echo "empty or malformed playlist export for $name; refusing to overwrite snapshots" >&2
    exit 1
  fi
  target="$playlist_repo/$playlist_file"
  if [[ ! -f "$target" ]] || ! cmp -s "$tmp" "$target"; then
    changed=yes
  fi
done

snapshot_date=$(date +%Y-%m-%dT%H:%M:%S%z)

label=${(j:, :)playlist_names}
if [[ "$changed" == yes ]]; then
  for playlist_file in "${playlist_files[@]}"; do
    cp "$temporary/$playlist_file" "$playlist_repo/$playlist_file"
  done
  git -C "$playlist_repo" add -- "${playlist_files[@]}"
  GIT_AUTHOR_DATE="$snapshot_date" git -C "$playlist_repo" cic -m "Record $label current state"
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
    GIT_AUTHOR_DATE="$snapshot_date" git -C "$playlist_repo" cic --allow-empty -m "Record $label unchanged state"
  else
    echo "No playlist changes detected; blank commit skipped (policy=$blank_policy)."
  fi
fi

if [[ "$push_after" == yes ]]; then
  git -C "$playlist_repo" push
fi
