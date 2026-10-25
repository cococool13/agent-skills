"""Context audit failure cases, without touching a live library."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('context_audit', Path(__file__).with_name('audit-context.py'))
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class ContextAuditTests(unittest.TestCase):
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
