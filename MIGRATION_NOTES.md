# Script Monorepo Migration Notes

Source thread: `codex://threads/019ef249-ee3c-7861-af98-a717e0209de9`

These notes recreate the useful context from the projectless Codex thread that
planned and executed this repository migration.

## Goal

Consolidate the existing `~/repos/script-*` repositories into a single
portable monorepo while keeping each script bundle independent.

Requirements:

- One Git repository so one clone installs or syncs all scripts.
- One top-level folder per script bundle.
- No shared runtime, package manager, or root framework unless a script needs
  it later.
- Path-filtered history should work naturally, for example:

  ```zsh
  git log --oneline -- ds-store-to-json
  git log --oneline -- apple-music-history
  git log --oneline -- itunes-matchbook
  ```

## Imported Repositories

| Source repo | Monorepo folder |
| --- | --- |
| `/Users/jacob/repos/script-DS_StoreToJSON` | `ds-store-to-json/` |
| `/Users/jacob/repos/script-applemusichistory` | `apple-music-history/` |
| `/Users/jacob/repos/script-itunesmatchbook` | `itunes-matchbook/` |
| `/Users/jacob/repos/script-rereminder` | `rereminder/` |

## Migration Approach

The migration used `git-filter-repo` instead of `git subtree add`.

The decisive reason was history filtering: a plain subtree import preserves old
commits, but those commits still refer to their original root-level paths, so
`git log -- <new-folder>` only shows the subtree merge. Rewriting each source
repo with `--to-subdirectory-filter` makes every historical commit live under
the final monorepo folder, which satisfies the filtered-log requirement.

The source repositories were not rewritten directly. Each source was cloned into
a disposable temp directory and the rewrite was applied there.

Implementation detail from the actual run: `git clone --no-local` was needed
for the disposable clones. `git clone --no-hardlinks` was not enough in one case;
`git-filter-repo` rejected the local clone as not fresh enough.

## Source Cleanup Commits

Before importing, the pending source-repo changes were committed with `git cic`:

- `068ccfa Handle byte tokens in DS_Store records`
- `20a5c92 Add Backblaze Music database manifest tooling`
- `c7a3ea7 Document iTunes Match sandbox notes`

Those commits are included in this monorepo's rewritten histories.

## Monorepo Commits

The target repo was initialized, then each rewritten history was merged with its
own merge commit:

- `31ab0b4 Initialize script monorepo`
- `1fac06a Import ds-store-to-json history`
- `efbaecb Import apple-music-history history`
- `2e45da6 Import itunes-matchbook history`
- `e10b185 Import rereminder history`

## Reproducible Command Shape

Install the one-time migration tool:

```zsh
brew install git-filter-repo
```

Prepare disposable clones and rewrite each history under its final folder:

```zsh
rm -rf /tmp/script-scripts-import
mkdir -p /tmp/script-scripts-import

git clone --no-local /Users/jacob/repos/script-DS_StoreToJSON /tmp/script-scripts-import/ds-store-to-json
git -C /tmp/script-scripts-import/ds-store-to-json filter-repo --to-subdirectory-filter ds-store-to-json

git clone --no-local /Users/jacob/repos/script-applemusichistory /tmp/script-scripts-import/apple-music-history
git -C /tmp/script-scripts-import/apple-music-history filter-repo --to-subdirectory-filter apple-music-history

git clone --no-local /Users/jacob/repos/script-itunesmatchbook /tmp/script-scripts-import/itunes-matchbook
git -C /tmp/script-scripts-import/itunes-matchbook filter-repo --to-subdirectory-filter itunes-matchbook
```

Merge each rewritten history into the monorepo:

```zsh
cd /Users/jacob/repos/script-scripts

git fetch /tmp/script-scripts-import/ds-store-to-json main:refs/heads/import/ds-store-to-json
git merge --allow-unrelated-histories --no-ff --no-commit import/ds-store-to-json
git cic -m "Import ds-store-to-json history"

git fetch /tmp/script-scripts-import/apple-music-history main:refs/heads/import/apple-music-history
git merge --allow-unrelated-histories --no-ff --no-commit import/apple-music-history
git cic -m "Import apple-music-history history"

git fetch /tmp/script-scripts-import/itunes-matchbook main:refs/heads/import/itunes-matchbook
git merge --allow-unrelated-histories --no-ff --no-commit import/itunes-matchbook
git cic -m "Import itunes-matchbook history"

git branch -D import/ds-store-to-json import/apple-music-history import/itunes-matchbook
rm -rf /tmp/script-scripts-import
```

## Verification Performed

Tracked file contents were compared against the cleaned source repos. The first
broader dry run also surfaced ignored local Apple Music artifacts such as `.env`
and `data/*.tsv`; those were intentionally not imported.

Syntax and smoke checks from the migration:

```zsh
python3 -m py_compile ds-store-to-json/decode_ds_store.py apple-music-history/scripts/*.py
zsh -n apple-music-history/scripts/capture_current_snapshot.zsh
swift -module-cache-path /tmp/swift-module-cache itunes-matchbook/scripts/cloudscan.swift --counts
```

Path-filtered logs after import:

```zsh
git log --oneline -- ds-store-to-json
# 068ccfa Handle byte tokens in DS_Store records
# f3c12b4 Initial commit: add DS_Store to JSON decoder script

git log --oneline -- apple-music-history
# 20a5c92 Add Backblaze Music database manifest tooling
# 85a67bc Add current snapshot capture workflow
# 3df4674 Add Apple Music history scripts

git log --oneline -- itunes-matchbook
# c7a3ea7 Document iTunes Match sandbox notes
# 7a87697 Document session handoff findings for cloudType and favorites
# b866bbb Add problem-focused cloud scan filters and error correlation notes
# d356644 Refine cloudType mapping with manual status confirmations
# 43be9a0 Initialize iTunes Match search repo with cloudType findings
```

Final migration state:

- The monorepo was clean after import and verification.
- The original source repos were left in place.
- `script-itunesmatchbook` was clean but one commit ahead of its old
  `origin/main`, because the local notes commit was created before import.

## Homebrew Notes

Homebrew packaging was intentionally deferred.

The repo can remain a simple script monorepo: future scripts can start as a new
top-level folder only. If a script later needs `brew install` support, add a
formula for that script at that time.

Useful tap constraints from the planning thread:

- A tap can be a normal Git URL when installed with the two-argument `brew tap`
  form, so this repository does not have to be named `homebrew-*`.
- Homebrew formulas still need formula filenames as package identities.
- For an unofficial tap with no `Formula/` directory, root-level `*.rb` formula
  files can work, but Homebrew will not discover formulas from arbitrary script
  subdirectories.
