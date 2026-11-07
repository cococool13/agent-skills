"""Symlink boundary for fingerprint_run. Uses synthetic temp files only."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
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

    def _fingerprint(self, forbid_secret_name=True):
        self.opened = []
        buf = io.StringIO()
        argv = ["fingerprint_run.py", str(self.checkout)]
        with self._track_open(), patch.object(sys, "argv", argv), redirect_stdout(buf):
            code = self.mod.main()
        self.assertEqual(code, 0)
        self._assert_opened_stay_inside()
        payload = buf.getvalue()
        self.assertNotIn("synthetic-target-contents", payload)
        self.assertNotIn("synthetic-internal-secret", payload)
        self.assertNotIn("synthetic-hidden", payload)
        if forbid_secret_name:
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

    def _marker(self, kind, path):
        return hashlib.sha256(f"{kind}:{path.as_posix()}".encode()).hexdigest()

    def _rewrite_same_stat(self, path, text):
        st = path.stat()
        path.write_text(text, encoding="utf-8")
        os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns))

    def _assert_secret_unread(self, secret):
        secret_real = secret.resolve()
        content_hash = hashlib.sha256(secret.read_bytes()).hexdigest()
        for opened in self.opened:
            resolved = opened.resolve()
            self.assertNotEqual(resolved, secret_real, f"read secret via {opened}")
            self.assertFalse(
                self.mod.looks_secret(resolved),
                f"read secret-named target via {opened}",
            )
        self.assertNotIn(content_hash, "".join(str(item) for item in self.opened))

    def test_regular_file_matches_bytes_and_symlink_does_not(self):
        notes = self.checkout / "notes.txt"
        notes.write_text("legitimate-v1\n", encoding="utf-8")
        alias = self.checkout / "alias.txt"
        alias.symlink_to("notes.txt")
        expected = hashlib.sha256(b"legitimate-v1\n").hexdigest()
        self.assertEqual(self.mod.digest_file(self.checkout, notes), expected)
        alias_digest = self.mod.digest_file(self.checkout, alias)
        self.assertEqual(alias_digest, self._marker("symlink", alias))
        self.assertNotEqual(alias_digest, expected)
        notes.write_text("legitimate-v2\n", encoding="utf-8")
        self.assertEqual(
            self.mod.digest_file(self.checkout, notes),
            hashlib.sha256(b"legitimate-v2\n").hexdigest(),
        )
        self.assertEqual(alias_digest, self.mod.digest_file(self.checkout, alias))

    def test_internal_secret_alias_chain_and_dir_link_are_not_read(self):
        real = self.checkout / "real"
        real.mkdir()
        secret = real / "mock-secret.key"
        secret.write_text("synthetic-internal-secret-v1\n", encoding="utf-8")
        alias = self.checkout / "ordinary.txt"
        alias.symlink_to(Path("real") / "mock-secret.key")
        hop = self.checkout / "hop.txt"
        hop.symlink_to("ordinary.txt")
        dirlink = self.checkout / "dirlink"
        dirlink.symlink_to("real", target_is_directory=True)
        through_dir = dirlink / "mock-secret.key"
        notes = self.checkout / "notes.txt"
        notes.write_text("legitimate-v1\n", encoding="utf-8")
        outside_dir = self.outside / "nested"
        outside_dir.mkdir()
        hidden = outside_dir / "hidden.txt"
        hidden.write_text("synthetic-hidden-v1\n", encoding="utf-8")
        linked_dir = self.checkout / "linked-dir"
        linked_dir.symlink_to(outside_dir, target_is_directory=True)
        through_outside = linked_dir / "hidden.txt"

        self.opened = []
        with self._track_open():
            alias_digest = self.mod.digest_file(self.checkout, alias)
            hop_digest = self.mod.digest_file(self.checkout, hop)
            through_digest = self.mod.digest_file(self.checkout, through_dir)
            outside_digest = self.mod.digest_file(self.checkout, through_outside)
            secret_digest = self.mod.digest_file(self.checkout, secret)
            notes_digest = self.mod.digest_file(self.checkout, notes)
        self._assert_secret_unread(secret)
        self._assert_opened_stay_inside()
        self.assertEqual(notes_digest, hashlib.sha256(b"legitimate-v1\n").hexdigest())
        self.assertEqual(alias_digest, self._marker("symlink", alias))
        self.assertEqual(hop_digest, self._marker("symlink", hop))
        self.assertEqual(through_digest, self._marker("symlink", through_dir))
        self.assertEqual(outside_digest, self._marker("outside-symlink", through_outside))
        self.assertNotEqual(alias_digest, hashlib.sha256(secret.read_bytes()).hexdigest())
        self.assertNotEqual(secret_digest, hashlib.sha256(secret.read_bytes()).hexdigest())
        self.assertNotIn(secret.resolve(), [item.resolve() for item in self.opened])

        self._rewrite_same_stat(secret, "synthetic-internal-secret-v2\n")
        hidden.write_text("synthetic-hidden-v2-expanded\n", encoding="utf-8")
        self.assertEqual(alias_digest, self.mod.digest_file(self.checkout, alias))
        self.assertEqual(hop_digest, self.mod.digest_file(self.checkout, hop))
        self.assertEqual(through_digest, self.mod.digest_file(self.checkout, through_dir))
        self.assertEqual(outside_digest, self.mod.digest_file(self.checkout, through_outside))
        self.assertEqual(notes_digest, self.mod.digest_file(self.checkout, notes))

    def _assert_internal_alias_fingerprint(self):
        real = self.checkout / "real"
        real.mkdir()
        secret = real / "mock-secret.key"
        secret.write_text("synthetic-internal-secret-v1\n", encoding="utf-8")
        (self.checkout / "ordinary.txt").symlink_to(Path("real") / "mock-secret.key")
        (self.checkout / "hop.txt").symlink_to("ordinary.txt")
        (self.checkout / "dirlink").symlink_to("real", target_is_directory=True)
        (self.checkout / "notes.txt").write_text("legitimate-v1\n", encoding="utf-8")
        (self.checkout / "package.json").write_text('{"name":"demo","rev":1}\n', encoding="utf-8")
        outside_dir = self.outside / "nested"
        outside_dir.mkdir()
        hidden = outside_dir / "hidden.txt"
        hidden.write_text("synthetic-hidden-v1\n", encoding="utf-8")
        (self.checkout / "linked-dir").symlink_to(outside_dir, target_is_directory=True)

        before = self._fingerprint(forbid_secret_name=False)
        self.assertNotIn("synthetic-internal-secret-v1", json.dumps(before))
        self.assertNotIn("synthetic-hidden-v1", json.dumps(before))
        self._assert_secret_unread(secret)
        self._rewrite_same_stat(secret, "synthetic-internal-secret-v2\n")
        hidden.write_text("synthetic-hidden-v2-expanded\n", encoding="utf-8")
        after_secret = self._fingerprint(forbid_secret_name=False)
        self.assertEqual(before["dirtyDigest"], after_secret["dirtyDigest"])
        self.assertEqual(before["configHash"], after_secret["configHash"])
        (self.checkout / "notes.txt").write_text("legitimate-v2\n", encoding="utf-8")
        after_notes = self._fingerprint(forbid_secret_name=False)
        self.assertNotEqual(after_secret["dirtyDigest"], after_notes["dirtyDigest"])

    def test_non_git_internal_secret_alias_is_not_fingerprinted(self):
        self._assert_internal_alias_fingerprint()

    def test_git_internal_secret_alias_is_not_fingerprinted(self):
        self._git_init()
        self._assert_internal_alias_fingerprint()

    def test_external_file_symlink_chain_is_not_read(self):
        link = self.checkout / "ordinary.txt"
        link.symlink_to(self.secret)
        hop = self.checkout / "hop.txt"
        hop.symlink_to("ordinary.txt")
        with self._track_open():
            external = self.mod.digest_file(self.checkout, link)
            chained = self.mod.digest_file(self.checkout, hop)
        self._assert_opened_stay_inside()
        self.assertEqual(self.opened, [])
        content_hash = hashlib.sha256(self.secret.read_bytes()).hexdigest()
        self.assertNotEqual(external, content_hash)
        self.assertNotEqual(chained, content_hash)
        self.assertEqual(external, self._marker("outside-symlink", link))
        self.assertEqual(chained, self._marker("outside-symlink", hop))
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

    def test_config_symlink_to_internal_secret_is_not_read(self):
        secret = self.checkout / "mock-secret.key"
        secret.write_text("synthetic-internal-secret-v1\n", encoding="utf-8")
        (self.checkout / "package.json").symlink_to("mock-secret.key")
        with self._track_open():
            first = self.mod.config_hash(self.checkout)
        self._assert_secret_unread(secret)
        self._rewrite_same_stat(secret, "synthetic-internal-secret-v2\n")
        second = self.mod.config_hash(self.checkout)
        self.assertEqual(first, second)
        self.assertNotEqual(first, "none")


if __name__ == "__main__":
    unittest.main()
