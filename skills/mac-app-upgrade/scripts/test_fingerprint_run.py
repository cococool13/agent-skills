"""Symlink boundary for fingerprint_run. Uses synthetic temp files only."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


def load_fingerprint(path: Path):
    name = "fingerprint_run_" + path.parent.parent.name.replace("-", "_")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FingerprintBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir="/tmp")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.outside = self.root / "outside"
        self.outside.mkdir()
        self.secret = self.outside / "mock-secret.key"
        self.secret.write_text("synthetic-target-contents-v1\n", encoding="utf-8")
        self.checkout = self.root / "checkout"
        self.checkout.mkdir()
        script = Path(__file__).resolve().with_name("fingerprint_run.py")
        self.mod = load_fingerprint(script)
        self.opened = []

    def _track_open(self):
        real_open = Path.open

        def tracking_open(path_obj, *args, **kwargs):
            self.opened.append(Path(path_obj))
            return real_open(path_obj, *args, **kwargs)

        return patch.object(Path, "open", tracking_open)

    def _assert_opened_stay_inside(self):
        root = self.checkout.resolve()
        for opened in self.opened:
            resolved = opened.resolve()
            self.assertTrue(
                resolved.is_relative_to(root),
                f"read outside checkout: {opened} -> {resolved}",
            )

    def _fingerprint(self):
        self.opened = []
        buf = io.StringIO()
        argv = ["fingerprint_run.py", str(self.checkout)]
        with self._track_open(), patch.object(sys, "argv", argv), redirect_stdout(buf):
            code = self.mod.main()
        self.assertEqual(code, 0)
        self._assert_opened_stay_inside()
        payload = buf.getvalue()
        self.assertNotIn("synthetic-target-contents", payload)
        self.assertNotIn("mock-secret.key", payload)
        secret_hash = hashlib.sha256(self.secret.read_bytes()).hexdigest()
        self.assertNotIn(secret_hash, payload)
        return json.loads(payload)

    def _plant_checkout_files(self):
        (self.checkout / "notes.txt").write_text("legitimate-v1\n", encoding="utf-8")
        (self.checkout / "package.json").write_text(
            '{"name":"demo","rev":1}\n', encoding="utf-8"
        )
        (self.checkout / "alias.txt").symlink_to("notes.txt")
        (self.checkout / "ordinary.txt").symlink_to(
            Path("..") / "outside" / "mock-secret.key"
        )

    def _git_init(self):
        hooks = self.root / "hooks"
        hooks.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.checkout)], check=True)
        for args in (
            ["config", "user.email", "fingerprint-test@example.invalid"],
            ["config", "user.name", "Fingerprint Test"],
            ["config", "commit.gpgsign", "false"],
            ["config", "core.hooksPath", str(hooks)],
        ):
            subprocess.run(["git", "-C", str(self.checkout), *args], check=True)
        (self.checkout / "README.md").write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.checkout), "add", "README.md"], check=True)
        subprocess.run(
            ["git", "-C", str(self.checkout), "commit", "-q", "-m", "init"],
            check=True,
        )

    def _assert_external_target_is_ignored(self):
        self._plant_checkout_files()
        before = self._fingerprint()
        self.secret.write_text("synthetic-target-contents-v2-expanded\n", encoding="utf-8")
        after_secret = self._fingerprint()
        self.assertEqual(before["dirtyDigest"], after_secret["dirtyDigest"])
        self.assertEqual(before["configHash"], after_secret["configHash"])
        (self.checkout / "notes.txt").write_text("legitimate-v2\n", encoding="utf-8")
        after_notes = self._fingerprint()
        self.assertNotEqual(after_secret["dirtyDigest"], after_notes["dirtyDigest"])
        (self.checkout / "package.json").write_text(
            '{"name":"demo","rev":2}\n', encoding="utf-8"
        )
        after_config = self._fingerprint()
        self.assertNotEqual(after_notes["configHash"], after_config["configHash"])

    def test_non_git_external_symlink_is_not_read_or_fingerprinted(self):
        self._assert_external_target_is_ignored()

    def test_git_external_symlink_is_not_read_or_fingerprinted(self):
        self._git_init()
        self._assert_external_target_is_ignored()

    def test_in_checkout_file_and_symlink_match_bytes(self):
        notes = self.checkout / "notes.txt"
        notes.write_text("legitimate-v1\n", encoding="utf-8")
        alias = self.checkout / "alias.txt"
        alias.symlink_to("notes.txt")
        expected = hashlib.sha256(b"legitimate-v1\n").hexdigest()
        self.assertEqual(self.mod.digest_file(self.checkout, notes), expected)
        self.assertEqual(self.mod.digest_file(self.checkout, alias), expected)

        link = self.checkout / "ordinary.txt"
        link.symlink_to(self.secret)
        hop = self.checkout / "hop.txt"
        hop.symlink_to("ordinary.txt")
        with self._track_open():
            external = self.mod.digest_file(self.checkout, link)
            chained = self.mod.digest_file(self.checkout, hop)
        self._assert_opened_stay_inside()
        content_hash = hashlib.sha256(self.secret.read_bytes()).hexdigest()
        self.assertNotEqual(external, content_hash)
        self.assertNotEqual(chained, content_hash)
        self.assertEqual(
            external,
            hashlib.sha256(f"outside-symlink:{link.as_posix()}".encode()).hexdigest(),
        )
        self.assertEqual(
            chained,
            hashlib.sha256(f"outside-symlink:{hop.as_posix()}".encode()).hexdigest(),
        )
        self.secret.write_text("synthetic-target-contents-v2-expanded\n", encoding="utf-8")
        self.assertEqual(external, self.mod.digest_file(self.checkout, link))
        self.assertEqual(chained, self.mod.digest_file(self.checkout, hop))

    def test_config_symlink_outside_is_not_read(self):
        target = self.outside / "pkg.json"
        target.write_text('{"name":"synthetic","rev":1}\n', encoding="utf-8")
        (self.checkout / "package.json").symlink_to(target)
        with self._track_open():
            first = self.mod.config_hash(self.checkout)
        self._assert_opened_stay_inside()
        target.write_text('{"name":"synthetic","rev":2-expanded}\n', encoding="utf-8")
        second = self.mod.config_hash(self.checkout)
        self.assertEqual(first, second)
        self.assertNotEqual(first, "none")


if __name__ == "__main__":
    unittest.main()
