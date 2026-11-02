"""Context audit failure cases, without touching a live library."""
import importlib.util
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('context_audit', Path(__file__).with_name('audit-context.py'))
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class ContextAuditTests(unittest.TestCase):
    def test_instruction_adapters_accept_links_and_explicit_imports(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            canonical = home / '.agents/AGENTS.md'
            canonical.parent.mkdir()
            canonical.write_text('Canonical rules\n')
            for name in ('codex', 'cursor', 'grok'):
                entry = home / f'.{name}/AGENTS.md'
                entry.parent.mkdir()
                entry.symlink_to(canonical)
            claude = home / '.claude/CLAUDE.md'
            claude.parent.mkdir()
            claude.write_text('@' + str(canonical) + '\n')
            self.assertEqual(audit.instruction_entrypoints(home, canonical), [])
            (home / 'AGENTS.md').write_text(canonical.read_text())
            problems = audit.instruction_entrypoints(home, canonical)
            self.assertEqual(len(problems), 1)
            self.assertIn('duplicates canonical', problems[0])
            (home / 'AGENTS.md').write_text('Read `~/.agents/AGENTS.md`.\n')
            self.assertEqual(audit.instruction_entrypoints(home, canonical), [])

    def test_instruction_adapters_report_missing_and_misdirected_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            canonical = home / '.agents/AGENTS.md'
            self.assertIn('canonical instructions missing', audit.instruction_entrypoints(home, canonical)[0])
            canonical.parent.mkdir()
            canonical.write_text('Canonical rules\n')
            entry = home / '.codex/AGENTS.md'
            entry.parent.mkdir()
            entry.symlink_to(home / 'missing.md')
            problems = audit.instruction_entrypoints(home, canonical)
            self.assertEqual(len(problems), 4)
            self.assertTrue(any('does not resolve' in p for p in problems))
            entry.unlink()
            entry.write_text('Stale local instructions\n')
            self.assertTrue(any('no explicit pointer' in p for p in audit.instruction_entrypoints(home, canonical)))

    def test_skipping_home_entrypoints_keeps_the_default_strict(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            canonical = home / 'AGENTS-canonical.md'
            self.assertIn('canonical instructions missing', audit.instruction_entrypoints(home, canonical, False)[0])
            canonical.write_text('Canonical rules\n')
            self.assertEqual(audit.instruction_entrypoints(home, canonical, False), [])
            self.assertEqual(len(audit.instruction_entrypoints(home, canonical)), 4)

    def test_ci_audit_command_passes_on_a_machine_without_client_homes(self):
        repo = Path(__file__).resolve().parents[3]
        gate = repo / 'scripts/check.sh'
        if not gate.is_file():
            self.skipTest('installed copy has no gate script')
        args = shlex.split(re.search(r'^python3 \S*audit-context\.py (.*)', gate.read_text(), re.M).group(1))
        self.assertIn('--skip-home-entrypoints', args)
        script = str(Path(__file__).with_name('audit-context.py'))
        with tempfile.TemporaryDirectory() as home:
            env = {**os.environ, 'HOME': home}
            ci = subprocess.run([sys.executable, script, *args], cwd=repo, env=env, capture_output=True, text=True)
            self.assertEqual(ci.returncode, 0, ci.stdout)
            self.assertIn('Home instruction entrypoints: skipped', ci.stdout)
            strict = [arg for arg in args if arg != '--skip-home-entrypoints']
            machine = subprocess.run([sys.executable, script, *strict], cwd=repo, env=env, capture_output=True, text=True)
            self.assertEqual(machine.returncode, 1)
            self.assertEqual(machine.stdout.count('instruction entrypoint missing'), 4)

    def test_ci_and_pre_push_run_the_same_gate(self):
        repo = Path(__file__).resolve().parents[3]
        workflow = repo / '.github/workflows/skills-ci.yml'
        if not workflow.is_file():
            self.skipTest('installed copy has no workflow')
        self.assertTrue(os.access(repo / 'scripts/check.sh', os.X_OK))
        self.assertIn('unset $(git rev-parse --local-env-vars)', (repo / 'scripts/check.sh').read_text())
        self.assertIn('run: scripts/check.sh', workflow.read_text())
        pre_push = (repo / 'lefthook.yml').read_text().split('pre-push:')[1]
        self.assertIn('run: scripts/check.sh', pre_push)

    def test_repo_upgrade_selftest_leaves_an_inherited_git_dir_alone(self):
        # Git exports GIT_DIR into hooks; the fixture's init and commit once hit the pushing repo.
        script = Path(__file__).resolve().parents[2] / 'repo-upgrade/scripts/preflight.py'
        clean = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
        with tempfile.TemporaryDirectory() as directory:
            outer = Path(directory) / 'outer'
            subprocess.run(['git', 'init', '-q', str(outer)], env=clean, check=True)
            config = (outer / '.git/config').read_text()
            run = subprocess.run([sys.executable, str(script), '--selftest'], capture_output=True, text=True,
                                 env={**clean, 'GIT_DIR': str(outer / '.git')})
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual((outer / '.git/config').read_text(), config)
            log = subprocess.run(['git', '-C', str(outer), 'rev-list', '--all'], env=clean, capture_output=True, text=True)
            self.assertEqual(log.stdout, '')

    def test_folded_description_stops_before_next_metadata_field(self):
        text = '---\nname: sample\ndescription: >-\n  Use when reading\n  project data.\nmetadata:\n  note: do not load\n---\nBody is not discovery text.'
        self.assertEqual(audit.metadata(text), ('sample', 'Use when reading project data.'))

    def test_quoted_literal_backslash_survives(self):
        text = r'''---
name: sample
description: "Use when matching C:\\data."
---
'''
        self.assertEqual(audit.metadata(text)[1], 'Use when matching C:\\data.')

    def test_invalid_overlay_is_error_without_rewriting_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'skills'
            overlays = Path(directory) / 'overlays'
            root.mkdir()
            overlays.mkdir()
            path = overlays / 'missing.txt'
            original = 'Use when first.\nInjected second line.\n'
            path.write_text(original)
            result = audit.audit(root, overlays)
            self.assertEqual(len(result['errors']), 1)
            self.assertEqual(len(result['warnings']), 1)
            self.assertEqual(path.read_text(), original)

    def test_stale_route_is_rejected_but_retirement_note_is_allowed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rules = root / 'rules'
            rules.mkdir()
            p = rules / 'ios.mdc'
            p.write_text('Use the `xcodebuildmcp`\nskill for builds.')
            self.assertEqual(len(audit.retired_skill_references(root, [rules])), 1)
            p.write_text('The retired `xcodebuildmcp` skill is not installed.')
            self.assertFalse(audit.retired_skill_references(root, [rules]))

    def test_hidden_archive_and_nested_dependency_skills_are_not_counted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in ('live', '.trash/old', 'live/node_modules/nested'):
                p = root / relative
                p.mkdir(parents=True, exist_ok=True)
                (p / 'SKILL.md').write_text('---\nname: sample\ndescription: Use when needed.\n---\n')
            result = audit.audit(root, root / 'overlays')
            self.assertEqual(result['skills'], 1)
            self.assertFalse(result['errors'])

    def test_bare_tools_in_third_party_skill_are_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'skills'
            for name, tools in (('vendor', 'allowed-tools:\n  - Read\n  - Bash\n'), ('scoped', 'allowed-tools: Read, Bash(git status:*)\n'), ('mine', 'allowed-tools: [Write]\n')):
                (root / name).mkdir(parents=True)
                (root / name / 'SKILL.md').write_text(f'---\nname: {name}\ndescription: Use when testing.\n{tools}---\n')
            lock = Path(directory) / 'lock.json'
            lock.write_text('{"skills": {"vendor": {"source": "someone/x"}, "scoped": {"source": "someone/y"}, "mine": {"source": "cococool13/agent-skills"}}}')
            problems = audit.bare_tool_grants(root, lock)
            self.assertEqual(len(problems), 1)
            self.assertIn('vendor', problems[0])
            self.assertIn('Bash', problems[0])

    def test_agents_md_size_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'AGENTS.md'
            path.write_text('x' * 9499)
            self.assertEqual(audit.agents_md_size(path), [])
            path.write_text('x' * 9500)
            self.assertEqual(len(audit.agents_md_size(path)), 1)

    def test_listing_budget_counts_each_name_once(self):
        with tempfile.TemporaryDirectory() as directory:
            roots = [Path(directory) / 'a', Path(directory) / 'b']
            for root in roots:
                (root / 'one').mkdir(parents=True)
                (root / 'one' / 'SKILL.md').write_text('---\nname: one\ndescription: ' + 'd' * 93 + '\n---\n')
            self.assertEqual(audit.listing_chars(roots), 100)
            self.assertEqual(audit.listing_budget(roots, 0.02, 1250)[2], [])
            self.assertEqual(len(audit.listing_budget(roots, 0.02, 1000)[2]), 1)


if __name__ == '__main__':
    unittest.main()
