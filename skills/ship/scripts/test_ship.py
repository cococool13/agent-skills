"""Behavioral checks using disposable local Git repositories and mocked scanner."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import apply
import gitleaks_check
import lib
import ship


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
        (self.repo / 'a.txt').write_text('one\n')
        self.git('add', 'a.txt')
        self.git('commit', '-m', 'initial')

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.repo), *args], check=True,
                              capture_output=True, text=True).stdout.strip()

    def remote(self):
        remote = self.root / 'remote.git'
        subprocess.run(['git', 'init', '--bare', str(remote)], check=True, capture_output=True)
        self.git('remote', 'add', 'origin', str(remote))
        self.git('push', '-u', 'origin', 'main')
        return remote

    def test_plan_is_local_and_does_not_scan_or_write_config(self):
        with patch.object(ship, 'current_repo', return_value=self.repo), \
             patch.object(ship, 'run_preflight') as scan, \
             patch.object(ship, 'git_run', wraps=lib.git_run) as run:
            payload = ship.build(skip_fetch=False, plan_only=True)
        scan.assert_not_called()
        self.assertFalse(any('fetch' in call.args for call in run.call_args_list))
        self.assertEqual(self.git('status', '--porcelain'), '')
        self.assertFalse((self.repo / '.gitleaks.toml').exists())
        self.assertIsNone(payload['gitleaks']['ok'])

    def test_unusual_names_and_rename(self):
        for name in ['two words.txt', 'line\nbreak.txt', 'quote".txt', 'café.txt']:
            (self.repo / name).write_text('text')
        self.git('mv', 'a.txt', 'renamed file.txt')
        rows = lib.parse_status(self.repo)
        rename = next(row for row in rows if row['path'] == 'renamed file.txt')
        self.assertEqual(rename['source'], 'a.txt')
        actions = ship.actions_for(ship.inspect(self.repo))
        commit = next(a for a in actions if a['op'] == 'commit')
        self.assertEqual(apply.apply_one(commit)['status'], 'ok')
        self.assertEqual(self.git('status', '--porcelain'), '')

    def test_unrelated_staged_file_blocks_commit(self):
        (self.repo / 'unrelated.txt').write_text('other work')
        self.git('add', 'unrelated.txt')
        (self.repo / 'a.txt').write_text('two\n')
        before = self.git('rev-parse', 'HEAD')
        _, _, err = apply.stage_commit(self.repo, ['a.txt'], 'chore: update text')
        self.assertTrue(err)
        self.assertEqual(self.git('rev-parse', 'HEAD'), before)
        self.assertEqual(self.git('diff', '--cached', '--name-only'), 'unrelated.txt')

    def test_failed_scan_gates_main(self):
        (self.repo / 'a.txt').write_text('two\n')
        with patch.object(ship, 'current_repo', return_value=self.repo), \
             patch.object(ship, 'run_preflight', return_value={'ok': False, 'summary': 'test blocked'}), \
             patch.object(apply, 'apply_one') as mutate, \
             patch('sys.argv', ['ship.py', '--apply', '--json']), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(ship.main(), 1)
        mutate.assert_not_called()
        self.assertIn('test blocked', json.loads(output.getvalue())['blockers'])

    def test_failed_fetch_gates_scan_and_apply(self):
        (self.repo / 'a.txt').write_text('two\n')
        self.git('remote', 'add', 'origin', str(self.root / 'missing.git'))
        with patch.object(ship, 'current_repo', return_value=self.repo), \
             patch.object(ship, 'run_preflight') as scan, \
             patch.object(apply, 'apply_one') as mutate, \
             patch('sys.argv', ['ship.py', '--apply']), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(ship.main(), 1)
        scan.assert_not_called()
        mutate.assert_not_called()

    def test_successful_local_push_preserves_author(self):
        remote = self.remote()
        (self.repo / 'a.txt').write_text('two\n')
        with patch.object(ship, 'current_repo', return_value=self.repo), \
             patch.object(ship, 'run_preflight', return_value={'ok': True, 'summary': 'test clean'}), \
             patch('sys.argv', ['ship.py', '--apply']), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(ship.main(), 0)
        remote_head = subprocess.run(['git', '--git-dir', str(remote), 'rev-parse', 'main'],
                                     check=True, capture_output=True, text=True).stdout.strip()
        self.assertEqual(self.git('rev-parse', 'HEAD'), remote_head)
        self.assertEqual(self.git('log', '-1', '--format=%ae'), 'ship@example.invalid')
        self.assertEqual(self.git('status', '--porcelain'), '')

    def test_leftover_branch_is_not_integrated(self):
        self.git('checkout', '-b', 'leftover')
        (self.repo / 'leftover.txt').write_text('unrelated')
        self.git('add', '.')
        self.git('commit', '-m', 'leftover')
        self.git('checkout', 'main')
        actions = ship.actions_for(ship.inspect(self.repo))
        self.assertFalse(any(a['op'] in {'merge', 'branch-d', 'stash-drop'} for a in actions))
        self.assertFalse((self.repo / 'leftover.txt').exists())

    def test_behind_requires_validation_before_apply(self):
        self.remote()
        self.git('reset', '--soft', 'HEAD')
        (self.repo / 'a.txt').write_text('two\n')
        self.git('commit', '-am', 'new upstream')
        self.git('push')
        self.git('reset', '--hard', 'HEAD~1')
        info = ship.inspect(self.repo)
        self.assertEqual(info['behind'], 1)
        self.assertTrue(info['blockers'])


class ApplyTests(unittest.TestCase):
    def test_failure_stops_following_actions(self):
        actions = [{'op': op, 'repo': '/unused'} for op in ['commit', 'push']]
        with patch.object(apply, 'apply_one', side_effect=lambda a: dict(a, status='failed')) as run:
            out = apply.apply_actions(actions, 'apply')
        self.assertEqual(run.call_count, 1)
        self.assertEqual(out[1]['status'], 'blocked')

    def test_all_actions_are_retained(self):
        actions = [{'op': 'push', 'repo': '/unused', 'branch': branch} for branch in ['one', 'two']]
        with patch.object(apply, 'apply_one', side_effect=lambda a: dict(a, status='ok')):
            self.assertEqual(len(apply.apply_actions(actions, 'apply')), 2)

    def test_missing_scanner_blocks(self):
        with patch.object(gitleaks_check, 'PREFLIGHT', Path('/does-not-exist/scan.sh')):
            self.assertFalse(gitleaks_check.run_preflight(Path('/unused'))['ok'])

    def test_scanner_output_is_not_exposed(self):
        with patch.object(Path, 'is_file', return_value=True), \
             patch.object(gitleaks_check.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, 'sensitive diagnostic', '')):
            self.assertNotIn('sensitive diagnostic', str(gitleaks_check.run_preflight(Path('/unused'))))


if __name__ == '__main__':
    unittest.main()
