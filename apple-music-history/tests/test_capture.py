import os
import fcntl
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
        stub.write_text('#!/bin/sh\n[ "${FAIL_EXPORT:-0}" = 0 ] || exit 1\ncat "$FAKE_EXPORT"\n')
        stub.chmod(0o755)
        self.env = {**os.environ, "PATH": f"{binaries}:{os.environ['PATH']}",
                    "FAKE_EXPORT": str(self.export), "TMPDIR": str(root)}

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


if __name__ == "__main__":
    unittest.main()
