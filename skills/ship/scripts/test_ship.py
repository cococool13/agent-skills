"""Behavioral checks using disposable local Git repositories and a mocked scanner."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import ship

CLEAN = {'ok': True, 'summary': 'test clean'}


class GitFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.git('init', '-b', 'main')
        self.git('config', 'user.name', 'Ship Test')
        self.git('config', 'user.email', 'ship@example.invalid')
        self.git('config', 'commit.gpgsign', 'false')
        self.git('config', 'core.hooksPath', str(self.root / 'no-hooks'))
        self.git('config', 'core.excludesFile', str(self.root / 'no-ignore'))
        (self.repo / 'a.txt').write_text('one\n')
        self.git('add', 'a.txt')
        self.git('commit', '-m', 'initial')

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.repo), *args], check=True,
                              capture_output=True, text=True).stdout.strip()

    def remote(self):
        remote = self.root / 'remote.git'
        subprocess.run(['git', 'init', '--bare', '-b', 'main', str(remote)], check=True, capture_output=True)
        self.git('remote', 'add', 'origin', str(remote))
        self.git('push', '-u', 'origin', 'main')
        return remote

    def remote_head(self, remote):
        return subprocess.run(['git', '--git-dir', str(remote), 'rev-parse', 'main'],
                              check=True, capture_output=True, text=True).stdout.strip()

    def main(self, *argv, scan=CLEAN):
        with patch.object(ship, 'current_repo', return_value=self.repo), \
             patch.object(ship, 'scan', return_value=scan) as scanner, \
             patch('sys.argv', ['ship.py', *argv]), contextlib.redirect_stdout(io.StringIO()) as output:
            code = ship.main()
        return code, json.loads(output.getvalue()), scanner

    def test_plan_does_not_scan_or_change_the_tree(self):
        (self.repo / 'a.txt').write_text('two\n')
        code, payload, scanner = self.main()
        self.assertEqual(code, 2)
        scanner.assert_not_called()
        self.assertEqual(self.git('status', '--porcelain'), 'M a.txt')
        self.assertEqual(payload['pending'][0], {'op': 'commit', 'files': ['a.txt']})

    def test_buckets(self):
        for name in ['.env.local', 'keys/id_rsa', '.dev.vars', 'debug.log', '_archive/old.txt', 'app.ts', '.env.example']:
            (self.repo / name).parent.mkdir(parents=True, exist_ok=True)
            (self.repo / name).write_text('x')
        (self.repo / 'big.bin').write_bytes(b'x' * (ship.MAX_UNTRACKED + 1))
        buckets = ship.inspect(self.repo)['buckets']
        self.assertEqual(sorted(buckets['secret']), ['.dev.vars', '.env.example', '.env.local', 'keys/id_rsa'])
        self.assertEqual(sorted(buckets['noise']), ['big.bin', 'debug.log'])
        self.assertEqual(buckets['archive'], ['_archive/old.txt'])
        self.assertEqual(buckets['commit'], ['app.ts'])

    def test_unusual_names_and_rename_commit(self):
        remote = self.remote()
        for name in ['two words.txt', 'line\nbreak.txt', 'quote".txt', 'café.txt']:
            (self.repo / name).write_text('text')
        self.git('mv', 'a.txt', 'renamed file.txt')
        code, payload, _ = self.main('--apply', '-m', 'chore: rename')
        self.assertEqual(code, 0, payload)
        self.assertEqual(self.git('status', '--porcelain'), '')
        self.assertEqual(self.remote_head(remote), self.git('rev-parse', 'HEAD'))

    def test_apply_commits_only_named_paths_with_message_and_author(self):
        remote = self.remote()
        (self.repo / 'a.txt').write_text('two\n')
        (self.repo / 'other.txt').write_text('unrelated work')
        code, payload, _ = self.main('--apply', '-m', 'fix: update a', '-m', 'Co-Authored-By: X <x@example.invalid>', 'a.txt')
        self.assertEqual(code, 0, payload)
        self.assertEqual(self.git('show', '--name-only', '--format=', 'HEAD'), 'a.txt')
        self.assertEqual(self.git('log', '-1', '--format=%B'), 'fix: update a\n\nCo-Authored-By: X <x@example.invalid>')
        self.assertEqual(self.git('log', '-1', '--format=%ae'), 'ship@example.invalid')
        self.assertEqual(self.git('status', '--porcelain'), '?? other.txt')
        self.assertEqual(self.remote_head(remote), self.git('rev-parse', 'HEAD'))
        self.assertEqual([d['op'] for d in payload['done']], ['commit', 'push'])

    def test_apply_requires_message(self):
        (self.repo / 'a.txt').write_text('two\n')
        code, payload, scanner = self.main('--apply')
        self.assertEqual(code, 1)
        self.assertIn('commit message required: -m', payload['blockers'])
        scanner.assert_not_called()

    def test_named_secret_or_unchanged_path_blocks(self):
        (self.repo / '.env').write_text('x')
        code, payload, _ = self.main('--apply', '-m', 'x', '.env', 'missing.txt')
        self.assertEqual(code, 1)
        self.assertTrue(any('secret-looking' in b for b in payload['blockers']))
        self.assertTrue(any('not changed: missing.txt' in b for b in payload['blockers']))
        self.assertEqual(self.git('rev-list', '--count', 'HEAD'), '1')

    def test_unrelated_staged_file_blocks_commit(self):
        (self.repo / 'unrelated.txt').write_text('other work')
        self.git('add', 'unrelated.txt')
        (self.repo / 'a.txt').write_text('two\n')
        before = self.git('rev-parse', 'HEAD')
        code, payload, _ = self.main('--apply', '-m', 'fix: a', 'a.txt')
        self.assertEqual(code, 1)
        self.assertTrue(any('staged paths outside' in b for b in payload['blockers']))
        self.assertEqual(self.git('rev-parse', 'HEAD'), before)
        self.assertEqual(self.git('diff', '--cached', '--name-only'), 'unrelated.txt')

    def test_failed_scan_blocks_commit(self):
        (self.repo / 'a.txt').write_text('two\n')
        code, payload, _ = self.main('--apply', '-m', 'x', scan={'ok': False, 'summary': 'test blocked'})
        self.assertEqual(code, 1)
        self.assertIn('test blocked', payload['blockers'])
        self.assertEqual(self.git('rev-list', '--count', 'HEAD'), '1')

    def test_failed_fetch_blocks_scan_and_apply(self):
        (self.repo / 'a.txt').write_text('two\n')
        self.git('remote', 'add', 'origin', str(self.root / 'missing.git'))
        code, payload, scanner = self.main('--apply', '-m', 'x')
        self.assertEqual(code, 1)
        scanner.assert_not_called()
        self.assertEqual(self.git('rev-list', '--count', 'HEAD'), '1')

    def test_plan_fetches_and_reports_behind(self):
        remote = self.remote()
        clone = self.root / 'clone'
        subprocess.run(['git', 'clone', '-q', str(remote), str(clone)], check=True)
        for args in (['config', 'user.email', 'o@example.invalid'], ['config', 'user.name', 'O'],
                     ['commit', '-q', '--allow-empty', '-m', 'upstream'], ['push', '-q']):
            subprocess.run(['git', '-C', str(clone), *args], check=True)
        code, payload, _ = self.main()
        self.assertEqual(code, 1)
        self.assertEqual(payload['repo']['behind'], 1)

    def test_push_only_when_ahead(self):
        remote = self.remote()
        self.git('commit', '--allow-empty', '-m', 'local')
        code, payload, _ = self.main('--apply')
        self.assertEqual(code, 0, payload)
        self.assertEqual(self.remote_head(remote), self.git('rev-parse', 'HEAD'))

    def test_nothing_to_do(self):
        self.remote()
        code, payload, scanner = self.main('--apply')
        self.assertEqual((code, payload['pending'], payload['blockers']), (0, [], []))
        scanner.assert_not_called()

    def test_local_only_repo_commits_without_push(self):
        (self.repo / 'a.txt').write_text('two\n')
        code, payload, _ = self.main('--apply', '-m', 'x')
        self.assertEqual(code, 0, payload)
        self.assertEqual([d['op'] for d in payload['done']], ['commit'])

    def test_not_a_repo(self):
        payload = ship.ship(None, False, [], [])
        self.assertEqual(payload['blockers'], ['not in a Git repository'])


class ScanTests(unittest.TestCase):
    def test_missing_scanner_blocks(self):
        with patch.object(ship, 'PREFLIGHT', Path('/does-not-exist/scan.sh')):
            self.assertFalse(ship.scan(Path('/unused'))['ok'])

    def test_scanner_output_is_not_exposed(self):
        with patch.object(Path, 'is_file', return_value=True), \
             patch.object(ship.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, 'sensitive diagnostic', '')):
            self.assertNotIn('sensitive diagnostic', str(ship.scan(Path('/unused'))))


if __name__ == '__main__':
    unittest.main()
