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

    def test_local_maintenance_survives_upstream_and_is_idempotent(self):
        source = self.root / 'source'
        (source / 'scripts').mkdir(parents=True)
        (source / 'SKILL.md').write_text('local guidance\n')
        (source / 'scripts/repair.py').write_text('local repair\n')
        self.overlay.MAINTENANCE_SOURCE = source
        dest = self.overlay.AGENTS / 'maintain-skill-library'
        dest.mkdir()
        (dest / 'SKILL.md').write_text('upstream guidance\n')
        self.overlay.restore_local_maintenance()
        self.assertEqual((dest / 'SKILL.md').read_text(), 'local guidance\n')
        self.assertEqual((dest / 'scripts/repair.py').read_text(), 'local repair\n')
        with patch.object(self.overlay.shutil, 'copy2', side_effect=AssertionError('unnecessary copy')):
            self.overlay.restore_local_maintenance()

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

    def test_repeated_description_overlay_does_not_rewrite_file(self):
        skill = self.root / 'SKILL.md'
        skill.write_text('---\nname: sample\ndescription: old\n---\nBody\n')
        self.assertTrue(self.overlay._replace_description(skill, 'Use when testing.'))
        with patch.object(Path, 'write_text', side_effect=AssertionError('unnecessary write')):
            self.assertFalse(self.overlay._replace_description(skill, 'Use when testing.'))

    def test_body_overlay_refuses_unknown_upstream_without_overwriting(self):
        skill = self.overlay.AGENTS / 'emil-design-eng/SKILL.md'
        skill.parent.mkdir()
        text = '# Guide\n## Initial Response\nNew upstream instructions.\n## The Animation Decision Framework\nKeep.\n'
        skill.write_text(text)
        with self.assertRaisesRegex(ValueError, 'exact instruction override'):
            self.overlay.patch_emil_design_eng_body()
        self.assertEqual(skill.read_text(), text)

    def test_body_overlay_preserves_already_adapted_skill(self):
        skill = self.overlay.AGENTS / 'emil-design-eng/SKILL.md'
        skill.parent.mkdir()
        text = '# Guide\n## Review format\nLocal adaptation.\n'
        skill.write_text(text)
        with patch.object(Path, 'write_text', side_effect=AssertionError('unnecessary write')):
            self.overlay.patch_emil_design_eng_body()
        self.assertEqual(skill.read_text(), text)


class RetirementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.prune = load('prune', 'prune-cursor-scan-paths.py')
        for name, rel in [('HOME','.'),('AGENTS','.agents/skills'),('CURSOR','.cursor/skills'),('CODEX','.codex/skills'),('CLAUDE','.claude/skills'),('GROK','.grok/skills')]:
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
        (self.prune.CLAUDE / 'example').symlink_to(self.skill)
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

    def test_broken_grok_link_is_candidate_but_working_alias_is_preserved(self):
        broken = self.prune.GROK / 'retired'
        broken.symlink_to(self.prune.AGENTS / 'retired')
        working = self.prune.GROK / 'example'
        working.symlink_to(self.skill)
        self.assertEqual(self.prune.candidates(), [broken])
        dest = self.prune.archive([broken])
        self.assertTrue((dest / '.grok/retired').is_symlink())
        self.assertTrue(working.is_symlink())


class SkillSyncTests(unittest.TestCase):
    def test_node_alias_matches_version_components(self):
        sync = load('sync_node', 'sync-claude-skills.py')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            sync.NVM = root / 'nvm'
            sync.NODE_LINK = root / 'node-current'
            alias = sync.NVM / 'alias/default'
            alias.parent.mkdir(parents=True)
            versions = sync.NVM / 'versions/node'
            for version in ('v26.1.0', 'v26.1.2', 'v26.10.0', 'v26.10.1'):
                (versions / version).mkdir(parents=True)
            for requested, expected in [('26.1', 'v26.1.2'), ('v26.1.0', 'v26.1.0'), ('26', 'v26.10.1')]:
                with self.subTest(alias=requested):
                    alias.write_text(requested + '\n')
                    sync.sync_node_link()
                    self.assertEqual(sync.NODE_LINK.resolve(), (versions / expected).resolve())

    def test_unmatched_node_alias_preserves_existing_runtime(self):
        sync = load('sync_node_missing', 'sync-claude-skills.py')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            sync.NVM = root / 'nvm'
            sync.NODE_LINK = root / 'node-current'
            alias = sync.NVM / 'alias/default'
            alias.parent.mkdir(parents=True)
            alias.write_text('26.1\n')
            installed = sync.NVM / 'versions/node/v26.10.0'
            installed.mkdir(parents=True)
            sync.NODE_LINK.symlink_to(installed)
            self.assertIn('no install matches', sync.sync_node_link())
            self.assertEqual(sync.NODE_LINK.resolve(), installed.resolve())

    def test_host_copies_are_reported_without_moves_or_cross_host_links(self):
        sync = load('sync', 'sync-claude-skills.py')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            sync.CANON = root / 'canon'
            sync.HOST_BUILTINS = root / 'builtins'
            sync.PONYTAIL = root / 'plugins'
            sync.VIEWS = {'claude': root / 'claude'}
            for parent in (sync.CANON, sync.HOST_BUILTINS):
                skill = parent / 'create-hook'
                skill.mkdir(parents=True)
                (skill / 'SKILL.md').write_text('Cursor-only instructions\n')
            with patch.object(sync, 'sync_node_link', return_value='node unchanged'):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(sync.main(), 0)
            self.assertTrue((sync.CANON / 'create-hook/SKILL.md').is_file())
            self.assertFalse((sync.VIEWS['claude'] / 'create-hook').exists())
            self.assertEqual(sync.host_copies(), ['create-hook'])

    def test_custom_shared_skill_can_override_a_builtin_name(self):
        sync = load('sync_custom', 'sync-claude-skills.py')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            sync.CANON = root / 'canon'
            sync.HOST_BUILTINS = root / 'builtins'
            sync.PONYTAIL = root / 'plugins'
            for parent, text in ((sync.CANON, 'Host-aware shared instructions'), (sync.HOST_BUILTINS, 'Cursor-only instructions')):
                skill = parent / 'create-hook'
                skill.mkdir(parents=True)
                (skill / 'SKILL.md').write_text(text)
            self.assertEqual(sync.host_copies(), [])
            self.assertEqual(sync.wanted(), {'create-hook': sync.CANON / 'create-hook'})


if __name__ == '__main__': unittest.main()
