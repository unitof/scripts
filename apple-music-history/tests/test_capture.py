import os
import fcntl
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/capture_current_snapshot.zsh"
HEADER = "persistent_id\ttitle\tartist\talbum\turl\n"
ORIGINAL = HEADER + "123\tOriginal\tArtist\tAlbum\t\n"
CHANGED = HEADER + "456\tNew song\tArtist\tAlbum\t\n"
TRAILER = "Co-authored-by: Codex (test fixture) <codex@openai.com>"


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="playlist test ")
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.repo = root / "repo"
        self.repo.mkdir()
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Snapshot Test")
        self.git("config", "user.email", "snapshot@example.invalid")
        self.git("config", "commit.gpgsign", "false")
        self.git("config", "alias.cic",
                 f'!f() {{ git commit "$@" --trailer "{TRAILER}"; }}; f')
        self.target = self.repo / "Favorite Songs.tsv"
        self.target.write_text(ORIGINAL)
        self.git("add", self.target.name)
        self.git("cic", "-m", "Fixture")
        self.before = self.git("rev-parse", "HEAD")
        self.export = root / "export.tsv"
        self.export.write_text(ORIGINAL)
        binaries = root / "bin"
        binaries.mkdir()
        stub = binaries / "swift"
        stub.write_text('''#!/bin/sh
[ "${FAIL_EXPORT:-0}" = 0 ] || exit 1
case "$*" in
  *--all-playlists) cat "$FAKE_ALL_EXPORT" ;;
  *Noggy)
    [ "${FAIL_NOGGY:-0}" = 0 ] || exit 1
    cat "$FAKE_NOGGY_EXPORT"
    ;;
  *) cat "$FAKE_EXPORT" ;;
esac
''')
        stub.chmod(0o755)
        self.noggy_export = root / "noggy.tsv"
        self.noggy_export.write_text(CHANGED)
        self.env = {**os.environ, "PATH": f"{binaries}:{os.environ['PATH']}",
                    "FAKE_EXPORT": str(self.export), "TMPDIR": str(root),
                    "FAKE_NOGGY_EXPORT": str(self.noggy_export)}
        self.all_export = root / "all.json"
        self.env["FAKE_ALL_EXPORT"] = str(self.all_export)

    def inventory(self):
        item = dict(zip(("persistent_id", "title", "artist", "album", "url"),
                        ("123", "Original", "Artist", "Album", "")))
        def playlist(pid, name, items, kind=0, distinguished=0, parent=None):
            return dict(persistent_id=pid, name=name, items=items, kind=kind,
                        distinguished_kind=distinguished, parent_id=parent, visible=True)
        return dict(schema_version=1, complete=True, playlists=[
            playlist("1", "Favorite Songs", [item], distinguished=52),
            playlist("2", "Noggy", [item, item]),
            playlist("3", "same/name", [], parent="5"),
            playlist("4", "same/name", [item]),
            playlist("5", "Folder", [], kind=3),
        ])

    def export_all(self, payload=None, *args):
        self.all_export.write_text(json.dumps(payload if payload is not None else self.inventory()))
        return self.capture("--all-playlists", *args)

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.repo), *args],
                                       text=True, stderr=subprocess.DEVNULL).strip()

    def capture(self, *args):
        return subprocess.run(["/bin/zsh", str(SCRIPT), "--playlist-repo", str(self.repo),
                               *args], env=self.env, capture_output=True, text=True, timeout=20)

    def assert_preserved(self):
        self.assertEqual(self.target.read_text(), ORIGINAL)
        self.assertEqual(self.git("rev-parse", "HEAD"), self.before)

    def test_changed_export_committed(self):
        self.export.write_text(CHANGED)
        result = self.capture()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.target.read_text(), CHANGED)
        self.assertEqual(self.git("status", "--porcelain"), "")
        self.assertRegex(self.git("log", "-1", "--format=%B"),
                         r"Co-authored-by: Codex \([^\n]+\) <codex@openai.com>")

    def test_unchanged_never(self):
        self.assertEqual(self.capture("--blank=never").returncode, 0)
        self.assert_preserved()

    def test_precompiled_exporter(self):
        self.env["APPLE_MUSIC_HISTORY_EXPORTER"] = str(Path(self.temp.name) / "bin/swift")
        self.export.write_text(CHANGED)
        result = self.capture()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.target.read_text(), CHANGED)

    def test_unchanged_always(self):
        self.assertEqual(self.capture("--blank=always").returncode, 0)
        self.assertNotEqual(self.git("rev-parse", "HEAD"), self.before)
        self.assertEqual(self.git("diff", "HEAD^", "HEAD", "--stat"), "")

    def test_multiple_playlists_committed_together(self):
        self.export.write_text(CHANGED)
        result = self.capture("--playlist", "Favorite Songs", "--playlist", "Noggy")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.target.read_text(), CHANGED)
        self.assertEqual((self.repo / "Noggy.tsv").read_text(), CHANGED)
        self.assertEqual(self.git("rev-parse", "HEAD^"), self.before)

    def test_second_export_failure_preserves_all_snapshots(self):
        self.export.write_text(CHANGED)
        self.env["FAIL_NOGGY"] = "1"
        result = self.capture("--playlist", "Favorite Songs", "--playlist", "Noggy")
        self.assertNotEqual(result.returncode, 0)
        self.assert_preserved()
        self.assertFalse((self.repo / "Noggy.tsv").exists())

    def test_named_playlist_preserves_repeated_tracks(self):
        repeated = CHANGED + CHANGED.splitlines(True)[1]
        self.noggy_export.write_text(repeated)
        result = self.capture("--playlist", "Favorite Songs", "--playlist", "Noggy")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.repo / "Noggy.tsv").read_text(), repeated)

    def test_second_invalid_export_preserves_all_snapshots(self):
        self.export.write_text(CHANGED)
        self.noggy_export.write_text(HEADER)
        result = self.capture("--playlist", "Favorite Songs", "--playlist", "Noggy")
        self.assertNotEqual(result.returncode, 0)
        self.assert_preserved()
        self.assertFalse((self.repo / "Noggy.tsv").exists())

    def test_multiple_unchanged_one_empty_commit(self):
        (self.repo / "Noggy.tsv").write_text(CHANGED)
        self.git("add", "Noggy.tsv")
        self.git("cic", "-m", "Noggy fixture")
        before = self.git("rev-parse", "HEAD")
        result = self.capture("--playlist", "Favorite Songs", "--playlist", "Noggy", "--blank=always")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.git("rev-parse", "HEAD^"), before)
        self.assertEqual(self.git("diff", "HEAD^", "HEAD", "--stat"), "")

    def test_invalid_playlist_arguments(self):
        for arguments in [("--playlist",), ("--playlist", "../escape"),
                          ("--playlist", "Noggy", "--playlist", "Noggy"),
                          ("--playlist", "")]:
            with self.subTest(arguments=arguments):
                self.assertEqual(self.capture(*arguments).returncode, 2)
                self.assert_preserved()

    def test_dirty_checkout_refused(self):
        (self.repo / "unrelated.txt").write_text("keep")
        self.assertNotEqual(self.capture().returncode, 0)
        self.assert_preserved()

    def test_failed_export_refused(self):
        self.env["FAIL_EXPORT"] = "1"
        self.assertNotEqual(self.capture().returncode, 0)
        self.assert_preserved()

    def test_concurrent_capture_refused(self):
        with (self.repo / ".git/apple-music-snapshot.lock").open("w") as lock:
            fcntl.lockf(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = self.capture()
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("another playlist capture", result.stderr)
            self.assert_preserved()

    def test_invalid_exports_refused(self):
        for content in ["", HEADER, "wrong header\n" + ORIGINAL.splitlines(True)[1],
                        HEADER + "123\ttoo few\n", ORIGINAL + ORIGINAL.splitlines(True)[1]]:
            with self.subTest(content=content):
                self.export.write_text(content)
                self.assertNotEqual(self.capture().returncode, 0)
                self.assert_preserved()

    def test_push_failure_keeps_local_commit(self):
        self.export.write_text(CHANGED)
        self.assertNotEqual(self.capture("--push").returncode, 0)
        self.assertEqual(self.target.read_text(), CHANGED)
        self.assertNotEqual(self.git("rev-parse", "HEAD"), self.before)
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_push_retries_pending_commit_without_change(self):
        remote = Path(self.temp.name) / "remote.git"
        subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
        self.git("remote", "add", "origin", str(remote))
        self.git("push", "-u", "origin", "main")
        self.export.write_text(CHANGED)
        self.assertEqual(self.capture().returncode, 0)
        result = self.capture("--blank=never", "--push")
        self.assertEqual(result.returncode, 0, result.stderr)
        remote_head = subprocess.check_output(["git", "--git-dir", str(remote),
                                               "rev-parse", "main"], text=True).strip()
        self.assertEqual(remote_head, self.git("rev-parse", "HEAD"))

    def test_all_preserves_order_repeats_folders_and_duplicate_names(self):
        payload = self.inventory()
        other = dict(payload["playlists"][0]["items"][0], persistent_id="456", title="Next\tline\n\\")
        payload["playlists"][1]["items"].insert(1, other)
        result = self.export_all(payload)
        self.assertEqual(result.returncode, 0, result.stderr)
        index = json.loads((self.repo / "playlists.json").read_text())
        self.assertEqual(len(index["playlists"]), 5)
        self.assertEqual((self.repo / "playlists/3.tsv").read_text(), HEADER)
        self.assertEqual((self.repo / "playlists/5.tsv").read_text(), HEADER)
        noggy = (self.repo / "Noggy.tsv").read_text().splitlines()
        self.assertEqual([line.split("\t")[0] for line in noggy[1:]], ["123", "456", "123"])
        self.assertIn("Next\\tline\\n\\\\", noggy[2])
        self.assertEqual(self.git("rev-parse", "HEAD^"), self.before)
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_all_rename_keeps_identity_and_legacy_filename(self):
        self.assertEqual(self.export_all().returncode, 0)
        payload = self.inventory()
        payload["playlists"][1]["name"] = "Renamed / Noggy"
        payload["playlists"][3]["name"] = "Renamed"
        result = self.export_all(payload)
        self.assertEqual(result.returncode, 0, result.stderr)
        entries = json.loads((self.repo / "playlists.json").read_text())["playlists"]
        self.assertEqual(entries[1]["file"], "Noggy.tsv")
        self.assertEqual(entries[3]["file"], "playlists/4.tsv")
        self.assertEqual(self.git("diff", "HEAD^", "HEAD", "--name-only"), "playlists.json")

    def test_all_removals_only_remove_indexed_files(self):
        self.assertEqual(self.export_all().returncode, 0)
        unrelated = self.repo / "playlists/999.tsv"
        unrelated.write_text("keep me\n")
        self.git("add", ".")
        self.git("cic", "-m", "Unrelated fixture")
        payload = self.inventory()
        payload["playlists"] = [p for p in payload["playlists"] if p["persistent_id"] != "4"]
        result = self.export_all(payload)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.repo / "playlists/4.tsv").exists())
        self.assertEqual(unrelated.read_text(), "keep me\n")
        self.assertIn("Original", self.git("show", "HEAD^:playlists/4.tsv"))

    def test_all_unchanged_blank_policy(self):
        self.assertEqual(self.export_all().returncode, 0)
        before = self.git("rev-parse", "HEAD")
        self.assertEqual(self.export_all(None, "--blank=never").returncode, 0)
        self.assertEqual(self.git("rev-parse", "HEAD"), before)
        self.assertEqual(self.export_all(None, "--blank=always").returncode, 0)
        self.assertEqual(self.git("rev-parse", "HEAD^"), before)
        self.assertEqual(self.git("diff", "HEAD^", "HEAD", "--stat"), "")

    def test_all_invalid_inventory_preserves_files(self):
        original = self.inventory()
        variants = []
        for key, value in [("complete", False), ("playlists", [])]:
            variants.append(dict(original, **{key: value}))
        variants.append(dict(original, playlists=original["playlists"][1:]))
        duplicate = copy.deepcopy(original)
        duplicate["playlists"].append(duplicate["playlists"][0])
        variants.append(duplicate)
        invalid = copy.deepcopy(original)
        invalid["playlists"][-1]["items"] = [{"persistent_id": "123"}]
        variants.append(invalid)
        empty = copy.deepcopy(original)
        empty["playlists"][0]["items"] = []
        variants.append(empty)
        for payload in variants:
            with self.subTest(payload=payload):
                self.assertNotEqual(self.export_all(payload).returncode, 0)
                self.assert_preserved()
                self.assertFalse((self.repo / "playlists.json").exists())

    def test_all_refuses_mixed_selection(self):
        self.assertEqual(self.capture("--all-playlists", "--playlist", "Noggy").returncode, 2)
        self.assert_preserved()

    def test_all_refuses_unindexed_collision(self):
        path = self.repo / "playlists/4.tsv"
        path.parent.mkdir()
        path.write_text("keep me\n")
        self.git("add", ".")
        self.git("cic", "-m", "Collision fixture")
        before = self.git("rev-parse", "HEAD")
        result = self.export_all()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.git("rev-parse", "HEAD"), before)
        self.assertEqual(path.read_text(), "keep me\n")
        self.assertFalse((self.repo / "playlists.json").exists())

    def test_all_refuses_unsafe_previous_index(self):
        (self.repo / "playlists.json").write_text(json.dumps(dict(schema_version=1,
            playlists=[dict(persistent_id="4", file="../outside.tsv")])))
        self.git("add", ".")
        self.git("cic", "-m", "Unsafe fixture")
        before = self.git("rev-parse", "HEAD")
        self.assertNotEqual(self.export_all().returncode, 0)
        self.assertEqual(self.git("rev-parse", "HEAD"), before)
        self.assertEqual(self.target.read_text(), ORIGINAL)


if __name__ == "__main__":
    unittest.main()
