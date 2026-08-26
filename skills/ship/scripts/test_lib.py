#!/usr/bin/env python3
"""Unit tests for /ship file classification and commit messages."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from lib import bucket_file, looks_secret, plans_deploy, suggest_msg


class BucketTests(unittest.TestCase):
    def test_secrets(self):
        self.assertEqual(bucket_file(".env", True), "secret")
        self.assertEqual(bucket_file("foo/.env.local", False), "secret")
        self.assertEqual(bucket_file("credentials.json", True), "secret")
        self.assertEqual(bucket_file("id_ed25519", True), "secret")

    def test_noise(self):
        self.assertEqual(bucket_file(".DS_Store", True), "noise")
        self.assertEqual(bucket_file(".uizze/live/app-root.json", True), "noise")
        self.assertEqual(bucket_file("foo.tsbuildinfo", True), "noise")
        self.assertEqual(bucket_file("src/app.tsx", False), "commit")

    def test_archive_untracked_only(self):
        self.assertEqual(bucket_file("_archive/old.md", True), "archive")
        self.assertEqual(bucket_file("_archive/old.md", False), "commit")

    def test_agent_docs_are_commit(self):
        self.assertEqual(bucket_file("AGENTS.md", False), "commit")
        self.assertEqual(bucket_file("CLAUDE.md", False), "commit")

    def test_large_untracked(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            blob = repo / "dump.bin"
            blob.write_bytes(b"x" * (5 * 1024 * 1024 + 1))
            self.assertEqual(bucket_file("dump.bin", True, repo), "noise")
            self.assertEqual(bucket_file("dump.bin", False, repo), "commit")


class MessageTests(unittest.TestCase):
    def test_agent_docs(self):
        self.assertEqual(suggest_msg(["AGENTS.md", "CLAUDE.md"]), "docs: refresh agent files")

    def test_markdown(self):
        self.assertEqual(suggest_msg(["README.md", "changelog.md"]), "docs: update project notes")

    def test_single(self):
        self.assertEqual(suggest_msg(["web/app/layout.tsx"]), "chore: update layout.tsx")

    def test_always_returns(self):
        self.assertTrue(suggest_msg(["a.ts", "b.ts"]).startswith("chore:"))


class PlansDeployTests(unittest.TestCase):
    def test_local_only_claude_skips(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "CLAUDE.md").write_text(
                "Local-only workspace — **not a general trading app and not a deploy target.**\n"
            )
            self.assertFalse(plans_deploy(repo))

    def test_opt_out_beats_wrangler(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "CLAUDE.md").write_text("not a deploy target\n")
            (repo / "wrangler.toml").write_text("name = 'x'\n")
            self.assertFalse(plans_deploy(repo))

    def test_wrangler_with_claude_plans(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "CLAUDE.md").write_text("# Site\n")
            (repo / "wrangler.toml").write_text("name = 'x'\n")
            self.assertTrue(plans_deploy(repo))

    def test_no_surface_skips(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "CLAUDE.md").write_text("# Notes\n")
            self.assertFalse(plans_deploy(repo))

    def test_no_claude_skips(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "wrangler.toml").write_text("name = 'x'\n")
            self.assertFalse(plans_deploy(repo))


class ApplyOkTests(unittest.TestCase):
    def test_ok_accepts_action_and_note(self):
        from apply import _ok

        out = _ok({"op": "commit", "repo": "/tmp"}, "staged 3")
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["note"], "staged 3")
        self.assertEqual(out["op"], "commit")


class SecretContentTests(unittest.TestCase):
    def test_detects_pat_shape(self):
        self.assertTrue(looks_secret("export x=ghp_" + ("a" * 36)))
        self.assertFalse(looks_secret("const token = process.env.API_KEY"))


class CurrentRepoScopeTests(unittest.TestCase):
    def test_lib_has_no_projects_walk(self):
        import lib

        self.assertFalse(hasattr(lib, "find_checkouts"))
        self.assertFalse(hasattr(lib, "classify_checkouts"))
        self.assertFalse(hasattr(lib, "PROJECTS"))
        self.assertFalse(hasattr(lib, "SKIP_WALK"))

    def test_worktrees_has_no_global_cleanup(self):
        import worktrees

        self.assertFalse(hasattr(worktrees, "cleanup_all"))
        self.assertFalse(hasattr(worktrees, "orphan_worktree_dirs"))
        self.assertTrue(callable(worktrees.cleanup_repo))

    def test_cleanup_repo_does_not_touch_other_repos(self):
        import subprocess

        import worktrees

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            a = root / "alpha"
            b = root / "beta"
            trash = root / "trash"
            a.mkdir()
            b.mkdir()
            for repo in (a, b):
                subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
                leftover = repo / ".worktrees" / "stale"
                leftover.mkdir(parents=True)
                (leftover / "marker.txt").write_text(repo.name)
            worktrees.cleanup_repo(a, trash=trash)
            self.assertFalse((a / ".worktrees" / "stale").exists())
            self.assertTrue((b / ".worktrees" / "stale" / "marker.txt").is_file())

    def test_build_without_repo_plans_nothing(self):
        import ship as ship_mod

        orig = ship_mod.current_repo
        ship_mod.current_repo = lambda: None
        try:
            payload = ship_mod.build(skip_fetch=True, plan_only=True)
        finally:
            ship_mod.current_repo = orig
        self.assertIsNone(payload["current"])
        self.assertEqual(payload["actions"], [])
        self.assertEqual(payload["worktrees"]["removed"], 0)


if __name__ == "__main__":
    unittest.main()
