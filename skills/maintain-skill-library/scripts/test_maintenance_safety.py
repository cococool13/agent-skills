"""Exercise local overlay safety without touching a real client or library."""
import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

BASE = Path(__file__).parent

def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, BASE / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class OverlaySafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.overlay = load('overlays', 'post-update-patches.py')
        self.overlay.AGENTS = self.root / 'agents'
        self.overlay.GROK_SKILLS = self.root / 'grok'
        self.overlay.AGENTS.mkdir()
        self.overlay.GROK_SKILLS.mkdir()

    def test_app_owned_link_survives_overlay(self):
        app = self.root / 'app-owned'
        app.mkdir()
        link = self.overlay.GROK_SKILLS / 'ego-browser'
        link.symlink_to(app)
        self.overlay.prune_grok_skill_duplicates()
        self.assertTrue(link.is_symlink())
        self.assertEqual(link.resolve(), app.resolve())

    def test_canonical_alias_waits_for_retirement_approval(self):
        skill = self.overlay.AGENTS / 'example'
        skill.mkdir()
        link = self.overlay.GROK_SKILLS / 'example'
        link.symlink_to(skill)
        self.overlay.prune_grok_skill_duplicates()
        self.assertTrue(link.is_symlink())

    def test_description_preserves_literal_backslashes_and_metadata(self):
        import json
        skill = self.root / 'SKILL.md'
        skill.write_text('---\nname: sample\ndescription: old\nmetadata:\n  owner: local\n---\nBody\n')
        desc = r'Use when checking C:\new\tools or literal \s regexes.'
        self.assertTrue(self.overlay._replace_description(skill, desc))
        line = next(line for line in skill.read_text().splitlines() if line.startswith('description:'))
        self.assertEqual(json.loads(line.split(':', 1)[1]), desc)
        self.assertIn('metadata:\n  owner: local\n', skill.read_text())
        self.assertTrue(skill.read_text().endswith('---\nBody\n'))


class RetirementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.prune = load('prune', 'prune-cursor-scan-paths.py')
        for name, rel in [('HOME','.'),('AGENTS','.agents/skills'),('CURSOR','.cursor/skills'),('CODEX','.codex/skills'),('CLAUDE','.claude/skills')]:
            value = self.root / rel
            value.mkdir(parents=True, exist_ok=True)
            setattr(self.prune, name, value)
        self.skill = self.prune.AGENTS / 'example'
        self.skill.mkdir()
        (self.skill / 'SKILL.md').write_text('keep\n')

    def test_default_scan_does_not_move_or_create_files(self):
        link = self.prune.CODEX / 'example'
        link.symlink_to(self.skill)
        before = sorted(str(p.relative_to(self.root)) for p in self.root.rglob('*'))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.prune.main([]), 0)
        self.assertTrue(link.is_symlink())
        self.assertEqual(before, sorted(str(p.relative_to(self.root)) for p in self.root.rglob('*')))

    def test_preserves_cursor_sync_system_app_and_real_directories(self):
        (self.prune.CURSOR / 'example').symlink_to(self.skill)
        (self.prune.CODEX / '.system').mkdir()
        app = self.root / 'app'; app.mkdir()
        (self.prune.CODEX / 'app-owned').symlink_to(app)
        real = self.prune.CODEX / 'example'; real.mkdir()
        (real / 'SKILL.md').write_text('local modifications\n')
        self.assertEqual(self.prune.candidates(), [])

    def test_authorized_archive_preserves_target_and_records_recovery(self):
        link = self.prune.CODEX / 'example'; link.symlink_to(self.skill)
        dest = self.prune.archive([link])
        self.assertFalse(link.is_symlink())
        self.assertTrue((dest / '.codex/example').is_symlink())
        self.assertEqual((self.skill / 'SKILL.md').read_text(), 'keep\n')
        self.assertIn(str(link), (dest / 'MANIFEST.txt').read_text())

    def test_bulk_guard_has_no_side_effects(self):
        links = []
        for i in range(20):
            link = self.prune.CODEX / str(i); link.symlink_to(self.skill); links.append(link)
        with self.assertRaises(ValueError): self.prune.archive(links)
        self.assertTrue(all(p.is_symlink() for p in links))
        self.assertFalse((self.root / '.agents/skill-archive').exists())

    def test_changed_selection_stops_before_archive(self):
        link = self.prune.CODEX / 'app-owned'
        app = self.root / 'app'; app.mkdir(); link.symlink_to(app)
        with self.assertRaises(ValueError): self.prune.archive([link])
        self.assertTrue(link.is_symlink())
        self.assertFalse((self.root / '.agents/skill-archive').exists())


if __name__ == '__main__': unittest.main()
