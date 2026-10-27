"""Behavioral checks using disposable local Git repositories and a mocked scanner."""
import contextlib
import io
import json
from pathlib import Path
import shutil
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import ship

CLEAN = {'ok': True, 'summary': 'test clean'}


class GitFixture(unittest.TestCase):
    """Disposable repo with an isolated Git config."""

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
        recent = patch.object(ship, 'RECENT_SECONDS', 0)
        recent.start()
        self.addCleanup(recent.stop)
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

    def upstream_commit(self, remote, name='up.txt', text='upstream\n'):
        clone = self.root / 'clone'
        if not clone.exists():
            subprocess.run(['git', 'clone', '-q', str(remote), str(clone)], check=True)
            for args in (['config', 'user.email', 'o@example.invalid'], ['config', 'user.name', 'O']):
                subprocess.run(['git', '-C', str(clone), *args], check=True)
        (clone / name).write_text(text)
        for args in (['add', name], ['commit', '-q', '-m', f'upstream {name}'], ['push', '-q']):
            subprocess.run(['git', '-C', str(clone), *args], check=True, capture_output=True)

    def remote_head(self, remote, branch='main'):
        return subprocess.run(['git', '--git-dir', str(remote), 'rev-parse', branch],
                              check=True, capture_output=True, text=True).stdout.strip()

    def main(self, *argv, scan=CLEAN):
        with patch.object(ship, 'current_repo', return_value=self.repo), \
             patch.object(ship, 'scan', return_value=scan) as scanner, \
             patch('sys.argv', ['ship.py', *argv]), contextlib.redirect_stdout(io.StringIO()) as output:
            code = ship.main()
        return code, json.loads(output.getvalue()), scanner


class ShipTests(GitFixture):
    def test_ai_coauthors_removed_and_human_credit_preserved(self):
        self.remote()
        (self.repo / 'a.txt').write_text('two\n')
        body = ('Fix saving.\n\nCo-Authored-By: Claude Code <noreply@anthropic.com>\n'
                'Co-authored-by: OpenAI Codex <codex@openai.com>\n'
                'Co-Authored-By: Claude Martin <claude.martin@example.invalid>\n'
                'Signed-off-by: Human <human@example.invalid>')
        code, payload, _ = self.main('--apply', '-m', 'fix: save edits', '-m', body)
        self.assertEqual(code, 0, payload)
        message = self.git('log', '-1', '--format=%B')
        self.assertNotIn('Claude Code', message)
        self.assertNotIn('OpenAI Codex', message)
        self.assertIn('Claude Martin', message)
        self.assertIn('Signed-off-by: Human', message)
        self.assertEqual(ship.clean_messages(['Co-Authored-By: Claude']), [])

    def test_hook_added_ai_credit_blocks_push(self):
        remote = self.remote()
        before = self.remote_head(remote)
        hooks = self.root / 'hooks'
        hooks.mkdir()
        hook = hooks / 'commit-msg'
        hook.write_text('#!/bin/sh\nprintf "\\nCo-Authored-By: Codex <codex@openai.com>\\n" >> "$1"\n')
        hook.chmod(0o755)
        self.git('config', 'core.hooksPath', str(hooks))
        (self.repo / 'a.txt').write_text('two\n')
        code, payload, _ = self.main('--apply', '-m', 'fix: a')
        self.assertEqual(code, 1, payload)
        self.assertTrue(any('hook added AI' in b for b in payload['blockers']))
        self.assertEqual(self.remote_head(remote), before)

    def check_command(self, code):
        return shlex.join([sys.executable, '-c', code])

    def test_check_discovery_prefers_ci_and_deduplicates_aliases(self):
        (self.repo / 'package.json').write_text(json.dumps({'scripts': {
            'test': 'watch', 'test:ci': 'once', 'typecheck': 'a', 'type-check': 'b',
            'lint': 'l', 'build': 'b', 'deploy': 'do not run',
        }}))
        (self.repo / 'pnpm-lock.yaml').touch()
        code, payload, _ = self.main('--skip-fetch')
        self.assertEqual(payload['check_candidates'], [
            'pnpm run typecheck', 'pnpm run lint', 'pnpm run test:ci', 'pnpm run build'])

    def test_check_failure_stops_before_scan_commit_or_push(self):
        remote = self.remote()
        (self.repo / 'a.txt').write_text('two\n')
        before = self.git('rev-parse', 'HEAD')
        command = self.check_command('raise SystemExit(3)')
        code, payload, scanner = self.main('--apply', '-m', 'fix: a', '--check', command)
        self.assertEqual(code, 1, payload)
        self.assertEqual(payload['checks'][0]['exit_code'], 3)
        scanner.assert_not_called()
        self.assertEqual(self.git('rev-parse', 'HEAD'), before)
        self.assertEqual(self.remote_head(remote), before)
        self.assertEqual(self.git('diff', '--cached', '--name-only'), '')

    def test_discovered_checks_require_explicit_selection_before_apply(self):
        (self.repo / 'package.json').write_text('{"scripts":{"test":"do not run"}}')
        before = self.git('rev-parse', 'HEAD')
        code, payload, scanner = self.main('--apply', '-m', 'x')
        self.assertEqual(code, 1, payload)
        self.assertIn('--check', payload['blockers'][0])
        scanner.assert_not_called()
        self.assertEqual(self.git('rev-parse', 'HEAD'), before)

    def test_check_cannot_change_head_and_then_push(self):
        remote = self.remote()
        before = self.remote_head(remote)
        (self.repo / 'a.txt').write_text('two\n')
        command = shlex.join(['git', 'commit', '--allow-empty', '-m', 'unexpected'])
        code, payload, scanner = self.main('--apply', '-m', 'fix: a', '--check', command)
        self.assertEqual(code, 1, payload)
        self.assertTrue(any('HEAD or branch changed' in b for b in payload['blockers']))
        scanner.assert_not_called()
        self.assertEqual(self.remote_head(remote), before)

    def test_push_only_check_cannot_rewrite_tracked_files(self):
        remote = self.remote()
        before = self.remote_head(remote)
        self.git('commit', '--allow-empty', '-m', 'local')
        command = self.check_command("from pathlib import Path; Path('a.txt').write_text('changed')")
        code, payload, scanner = self.main('--apply', '--check', command)
        self.assertEqual(code, 1, payload)
        self.assertTrue(any('checks changed tracked files' in b for b in payload['blockers']))
        scanner.assert_not_called()
        self.assertEqual(self.remote_head(remote), before)

    def test_checks_cannot_silently_change_push_destination(self):
        self.remote()
        (self.repo / 'a.txt').write_text('two\n')
        command = shlex.join(['git', 'config', 'branch.main.merge', 'refs/heads/other'])
        code, payload, scanner = self.main('--apply', '-m', 'x', '--check', command)
        self.assertEqual(code, 1, payload)
        self.assertTrue(any('destination changed' in b for b in payload['blockers']))
        scanner.assert_not_called()

    def test_check_shell_syntax_is_rejected_without_execution(self):
        command = self.check_command("from pathlib import Path; Path('should-not-exist').touch()") + '; echo okay'
        code, payload, scanner = self.main('--check-only', '--check', command)
        self.assertEqual(code, 1, payload)
        self.assertEqual(payload['checks'][0]['status'], 'could_not_run')
        self.assertFalse((self.repo / 'should-not-exist').exists())
        scanner.assert_not_called()

    def test_excluded_paths_cannot_be_named_for_commit(self):
        for name in ('debug.log', '_archive/old.txt'):
            path = self.repo / name
            path.parent.mkdir(exist_ok=True)
            path.write_text('x')
            code, payload, scanner = self.main('--apply', '-m', 'x', name)
            self.assertEqual(code, 1, payload)
            self.assertTrue(any('excluded paths' in b for b in payload['blockers']))
            scanner.assert_not_called()

    def test_default_plan_skips_worktree_inspection(self):
        with patch.object(ship, 'worktree_plan', side_effect=AssertionError('unnecessary work')):
            self.main('--skip-fetch')

    def test_apply_cannot_skip_remote_refresh(self):
        (self.repo / 'a.txt').write_text('two\n')
        code, payload, scanner = self.main('--apply', '--skip-fetch', '-m', 'x')
        self.assertEqual(code, 1, payload)
        self.assertIn('fresh remote state', payload['blockers'][0])
        scanner.assert_not_called()
        self.assertEqual(self.git('rev-list', '--count', 'HEAD'), '1')

    def test_checks_run_once_and_generated_files_are_replanned(self):
        self.remote()
        (self.repo / 'a.txt').write_text('two\n')
        command = self.check_command("from pathlib import Path; p=Path('generated.txt'); p.write_text(p.read_text()+'x' if p.exists() else 'x')")
        code, payload, scanner = self.main('--apply', '-m', 'fix: a', '--check', command, '--check', command)
        self.assertEqual(code, 0, payload)
        self.assertEqual(len(payload['checks']), 1)
        self.assertEqual((self.repo / 'generated.txt').read_text(), 'x')
        self.assertIn('generated.txt', self.git('show', '--name-only', '--format=', 'HEAD'))
        self.assertEqual(scanner.call_count, 2)

    def test_check_only_never_commits_or_pushes(self):
        remote = self.remote()
        before = self.git('rev-parse', 'HEAD')
        (self.repo / 'a.txt').write_text('two\n')
        code, payload, scanner = self.main('--check-only', '--check', self.check_command('pass'))
        self.assertEqual((code, payload['mode']), (0, 'check'), payload)
        scanner.assert_not_called()
        self.assertEqual(self.git('rev-parse', 'HEAD'), before)
        self.assertEqual(self.remote_head(remote), before)

    def test_timed_out_check_blocks_apply(self):
        (self.repo / 'a.txt').write_text('two\n')
        command = self.check_command('import time; time.sleep(30)')
        code, payload, scanner = self.main('--apply', '-m', 'x', '--check', command, '--check-timeout', '1')
        self.assertEqual(code, 1, payload)
        self.assertEqual(payload['checks'][0]['status'], 'timed_out')
        scanner.assert_not_called()

    def test_failed_scan_restores_partially_staged_content(self):
        (self.repo / 'a.txt').write_text('staged\n')
        self.git('add', 'a.txt')
        (self.repo / 'a.txt').write_text('unstaged\n')
        before = self.git('diff', '--cached')
        code, payload, _ = self.main('--apply', '-m', 'x', scan={'ok': False, 'summary': 'blocked'})
        self.assertEqual(code, 1, payload)
        self.assertEqual(self.git('diff', '--cached'), before)
        self.assertEqual((self.repo / 'a.txt').read_text(), 'unstaged\n')

    def test_second_scan_can_block_hook_modified_commit(self):
        remote = self.remote()
        before = self.remote_head(remote)
        (self.repo / 'a.txt').write_text('two\n')
        with patch.object(ship, 'scan', side_effect=[CLEAN, {'ok': False, 'summary': 'post-commit leak'}]):
            payload = ship.ship(self.repo, True, ['fix: a'], [])
        self.assertIn('post-commit leak', payload['blockers'])
        self.assertEqual(self.remote_head(remote), before)
        self.assertEqual([d['op'] for d in payload['done']], ['commit'])

    def test_verify_only_matches_remote_without_fetching(self):
        self.remote()
        original = ship.run
        def read_only(repo, *args, **kwargs):
            self.assertNotIn(args[0], ('fetch', 'push', 'commit', 'add'))
            return original(repo, *args, **kwargs)
        with patch.object(ship, 'run', side_effect=read_only):
            code, payload, scanner = self.main('--verify-only')
        self.assertEqual(code, 0, payload)
        self.assertTrue(payload['verified'])
        scanner.assert_not_called()
        self.git('commit', '--allow-empty', '-m', 'local')
        code, payload, _ = self.main('--verify-only')
        self.assertEqual((code, payload['status']), (1, 'differs'), payload)

    def test_push_timeout_reports_progress_and_reads_remote_once(self):
        remote = self.remote()
        (self.repo / 'a.txt').write_text('two\n')
        original = ship.run
        pushes = []
        def timeout_after_push(repo, *args, **kwargs):
            result = original(repo, *args, **kwargs)
            if args[0] == 'push':
                pushes.append(args)
                raise subprocess.TimeoutExpired('git push', 180)
            return result
        with patch.object(ship, 'run', side_effect=timeout_after_push):
            code, payload, _ = self.main('--apply', '-m', 'fix: a')
        self.assertEqual(code, 1, payload)
        self.assertEqual(len(pushes), 1)
        self.assertEqual(payload['push_outcome'], 'uncertain')
        self.assertTrue(payload['remote_check']['verified'])
        self.assertEqual([d['op'] for d in payload['done']], ['commit'])
        self.assertEqual(self.remote_head(remote), self.git('rev-parse', 'HEAD'))

    def test_plan_does_not_scan_or_change_the_tree(self):
        (self.repo / 'a.txt').write_text('two\n')
        code, payload, scanner = self.main()
        self.assertEqual(code, 2)
        scanner.assert_not_called()
        self.assertEqual(self.git('status', '--porcelain'), 'M a.txt')
        self.assertEqual(payload['pending'][0], {'op': 'commit', 'files': ['a.txt']})

    def test_buckets(self):
        names = [
            '.env.local', '.env.production', '.envrc', 'keys/id_rsa', '.dev.vars', 'debug.log',
            '_archive/old.txt', 'app.ts', '.env.example', '.env.sample', 'app/.env.local.example',
            'app/.env.production.local.example',
            'node_modules/pkg/index.js', '.next/cache/x',
        ]
        for name in names:
            (self.repo / name).parent.mkdir(parents=True, exist_ok=True)
            (self.repo / name).write_text('x')
        (self.repo / 'big.bin').write_bytes(b'x' * (ship.MAX_UNTRACKED + 1))
        buckets = ship.inspect(self.repo)['buckets']
        self.assertEqual(sorted(buckets['secret']), ['.dev.vars', '.env.local', '.env.production', '.envrc', 'keys/id_rsa'])
        self.assertEqual(sorted(buckets['noise']), ['.next/cache/x', 'big.bin', 'debug.log', 'node_modules/pkg/index.js'])
        self.assertEqual(buckets['archive'], ['_archive/old.txt'])
        self.assertEqual(sorted(buckets['commit']), [
            '.env.example', '.env.sample', 'app.ts', 'app/.env.local.example', 'app/.env.production.local.example',
        ])

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
        code, payload, scanner = self.main('--apply', 'a.txt')
        self.assertEqual(code, 1)
        self.assertIn('commit message required: -m', payload['blockers'])
        scanner.assert_not_called()

    def test_apply_without_message_or_paths_only_pushes(self):
        remote = self.remote()
        self.git('commit', '--allow-empty', '-m', 'local')
        (self.repo / 'a.txt').write_text('two\n')
        code, payload, _ = self.main('--apply')
        self.assertEqual(code, 0, payload)
        self.assertEqual([d['op'] for d in payload['done']], ['push'])
        self.assertEqual(payload['left'], ['a.txt'])
        self.assertTrue(any('not committed' in w for w in payload['warnings']))
        self.assertEqual(self.remote_head(remote), self.git('rev-parse', 'HEAD'))

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
        self.assertEqual(self.git('diff', '--cached', '--name-only'), '')

    def test_plan_only_and_skip_fetch_do_not_change_the_tree(self):
        (self.repo / 'a.txt').write_text('two\n')
        self.git('remote', 'add', 'origin', str(self.root / 'missing.git'))
        code, payload, scanner = self.main('--plan-only', '--skip-fetch', '--json', '-m', 'x')
        self.assertEqual(code, 2, payload)
        self.assertFalse(any('fetch' in b for b in payload['blockers']))
        scanner.assert_not_called()
        self.assertEqual(self.git('rev-list', '--count', 'HEAD'), '1')
        self.assertEqual(self.git('status', '--porcelain'), 'M a.txt')

    def test_plan_only_with_apply_stops(self):
        (self.repo / 'a.txt').write_text('two\n')
        code, payload, scanner = self.main('--plan-only', '--apply', '-m', 'x')
        self.assertEqual(code, 1, payload)
        self.assertIn('contradict', payload['blockers'][0])
        scanner.assert_not_called()
        self.assertEqual(self.git('rev-list', '--count', 'HEAD'), '1')

    def test_failed_fetch_blocks_scan_and_apply(self):
        (self.repo / 'a.txt').write_text('two\n')
        self.git('remote', 'add', 'origin', str(self.root / 'missing.git'))
        code, payload, scanner = self.main('--apply', '-m', 'x')
        self.assertEqual(code, 1)
        scanner.assert_not_called()
        self.assertEqual(self.git('rev-list', '--count', 'HEAD'), '1')

    def test_plan_fetches_and_plans_integration(self):
        remote = self.remote()
        self.upstream_commit(remote)
        (self.repo / 'a.txt').write_text('two\n')
        code, payload, _ = self.main()
        self.assertEqual(code, 2, payload)
        self.assertEqual(payload['repo']['behind'], 1)
        self.assertEqual([op['op'] for op in payload['pending']], ['commit', 'integrate', 'push'])

    def test_behind_rebases_then_asks_for_revalidation(self):
        remote = self.remote()
        self.upstream_commit(remote)
        (self.repo / 'a.txt').write_text('two\n')
        (self.repo / 'other.txt').write_text('unrelated work')
        code, payload, _ = self.main('--apply', '-m', 'fix: a', 'a.txt')
        self.assertEqual(code, 2, payload)
        self.assertIn('revalidate', payload)
        self.assertEqual([d['op'] for d in payload['done']], ['commit', 'integrate'])
        self.assertTrue((self.repo / 'up.txt').exists())
        self.assertEqual(self.git('status', '--porcelain'), '?? other.txt')
        self.assertNotEqual(self.remote_head(remote), self.git('rev-parse', 'HEAD'))
        code, payload, _ = self.main('--apply')
        self.assertEqual(code, 0, payload)
        self.assertTrue(payload['verified'])
        self.assertEqual(self.remote_head(remote), self.git('rev-parse', 'HEAD'))
        self.assertEqual(self.git('log', '-1', '--format=%s'), 'fix: a')

    def test_rebase_keeps_dirty_tracked_edits(self):
        remote = self.remote()
        (self.repo / 'b.txt').write_text('base\n')
        self.git('add', 'b.txt')
        self.git('commit', '-m', 'b')
        self.git('push', '-q')
        self.upstream_commit(remote)
        (self.repo / 'a.txt').write_text('two\n')
        (self.repo / 'b.txt').write_text('unrelated edit\n')
        code, payload, _ = self.main('--apply', '-m', 'fix: a', 'a.txt')
        self.assertEqual(code, 2, payload)
        self.assertEqual(self.git('status', '--porcelain'), 'M b.txt')
        self.assertEqual(self.git('stash', 'list'), '')

    def test_rebase_conflict_aborts_and_blocks(self):
        remote = self.remote()
        self.upstream_commit(remote, 'a.txt', 'theirs\n')
        (self.repo / 'a.txt').write_text('ours\n')
        code, payload, _ = self.main('--apply', '-m', 'fix: a')
        self.assertEqual(code, 1, payload)
        self.assertTrue(any('conflicts' in b for b in payload['blockers']))
        self.assertEqual(self.git('status', '--porcelain'), '')
        self.assertEqual(self.git('log', '-1', '--format=%s'), 'fix: a')
        self.assertFalse((self.repo / '.git' / 'rebase-merge').exists())

    def test_to_ships_a_session_branch_onto_main(self):
        remote = self.remote()
        self.upstream_commit(remote)
        self.git('switch', '-q', '-c', 'cc/session')
        (self.repo / 'a.txt').write_text('two\n')
        code, payload, _ = self.main('--apply', '--to', 'main', '-m', 'fix: a')
        self.assertEqual(code, 2, payload)
        code, payload, _ = self.main('--apply', '--to', 'main')
        self.assertEqual(code, 0, payload)
        self.assertEqual(self.remote_head(remote), self.git('rev-parse', 'HEAD'))
        self.assertEqual(self.git('branch', '--show-current'), 'cc/session')

    def test_untracked_remote_branch_needs_to(self):
        self.remote()
        self.git('branch', '--unset-upstream')
        code, payload, _ = self.main()
        self.assertEqual(code, 1, payload)
        self.assertTrue(any('--to main' in b for b in payload['blockers']))

    def test_deploy_hints(self):
        (self.repo / '.github' / 'workflows').mkdir(parents=True)
        (self.repo / '.github' / 'workflows' / 'deploy.yml').write_text('run: npx wrangler deploy\n')
        (self.repo / '.github' / 'workflows' / 'lint.yml').write_text('run: npm test\n')
        (self.repo / 'package.json').write_text('{"scripts": {"deploy": "x", "build": "y", "release:ios": "z"}}')
        (self.repo / 'pnpm-lock.yaml').write_text('')
        (self.repo / 'site').mkdir()
        (self.repo / 'site' / 'wrangler.jsonc').write_text('{}')
        self.assertEqual(ship.deploy_hints(self.repo), {
            'ci': ['.github/workflows/deploy.yml'],
            'scripts': ['pnpm run deploy', 'pnpm run release:ios'],
            'wrangler': ['site/wrangler.jsonc'],
        })

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

    def test_example_env_commits_and_real_env_stays_out(self):
        self.remote()
        (self.repo / '.env.example').write_text('TOKEN=\n')
        (self.repo / '.env').write_text('TOKEN=real\n')
        code, payload, _ = self.main('--apply', '-m', 'chore: example env')
        self.assertEqual(code, 0, payload)
        self.assertEqual(self.git('show', '--name-only', '--format=', 'HEAD'), '.env.example')
        self.assertIn('.env', self.git('status', '--porcelain'))

    def test_plan_lists_unpushed_commits(self):
        self.remote()
        self.git('commit', '--allow-empty', '-m', 'feat: local only')
        code, payload, _ = self.main()
        self.assertEqual(code, 2, payload)
        sha = self.git('rev-parse', '--short', 'HEAD')
        self.assertEqual(payload['repo']['unpushed'], [f'{sha} feat: local only'])
        self.assertEqual(payload['repo']['ahead'], 1)

    def test_missing_upstream_warns(self):
        remote = self.root / 'remote.git'
        subprocess.run(['git', 'init', '--bare', '-b', 'main', str(remote)], check=True, capture_output=True)
        self.git('remote', 'add', 'origin', str(remote))
        code, payload, _ = self.main()
        self.assertEqual(code, 2, payload)
        self.assertIn('origin/main does not exist; push publishes it', payload['warnings'])
        self.assertEqual(len(payload['repo']['unpushed']), 1)
        self.assertTrue(payload['pending'][-1]['set_upstream'])

    def test_oversize_file_blocks_before_commit(self):
        (self.repo / 'huge.bin').write_bytes(b'x' * 20)
        with patch.object(ship, 'BLOCK_BYTES', 10), patch.object(ship, 'WARN_BYTES', 5):
            code, payload, scanner = self.main('--apply', '-m', 'x')
        self.assertEqual(code, 1)
        self.assertTrue(any('GitHub rejects' in item for item in payload['blockers']))
        scanner.assert_not_called()
        self.assertEqual(self.git('rev-list', '--count', 'HEAD'), '1')

    def test_size_warning_still_commits(self):
        (self.repo / 'wide.bin').write_bytes(b'x' * 8)
        with patch.object(ship, 'BLOCK_BYTES', 10), patch.object(ship, 'WARN_BYTES', 5):
            code, payload, _ = self.main('--apply', '-m', 'chore: wide file')
        self.assertEqual(code, 0, payload)
        self.assertTrue(any('GitHub warns' in item for item in payload['warnings']))
        self.assertEqual(self.git('show', '--name-only', '--format=', 'HEAD'), 'wide.bin')

    def test_lfs_attribute_without_clean_filter_blocks_raw_file(self):
        (self.repo / '.gitattributes').write_text('*.mp4 filter=lfs\n')
        (self.repo / 'film.mp4').write_bytes(b'x' * 30)
        original = ship.out

        def no_clean_filter(repo, *args):
            if args == ('config', '--get', 'filter.lfs.clean'):
                return ''
            return original(repo, *args)

        with patch.object(ship, 'out', side_effect=no_clean_filter), \
             patch.object(ship, 'BLOCK_BYTES', 20), patch.object(ship, 'WARN_BYTES', 18):
            code, payload, scanner = self.main('--apply', '-m', 'x')
        self.assertEqual(code, 1)
        self.assertTrue(any('film.mp4' in item and 'GitHub rejects' in item for item in payload['blockers']))
        scanner.assert_not_called()

    def test_lfs_pointer_text_skips_size_without_clean_filter(self):
        (self.repo / '.gitattributes').write_text('*.mp4 filter=lfs\n')
        (self.repo / 'film.mp4').write_bytes(ship.LFS_POINTER + b'\nsize 99\n' + b'x' * 20)
        original = ship.out

        def no_clean_filter(repo, *args):
            if args == ('config', '--get', 'filter.lfs.clean'):
                return ''
            return original(repo, *args)

        with patch.object(ship, 'out', side_effect=no_clean_filter), \
             patch.object(ship, 'BLOCK_BYTES', 20), patch.object(ship, 'WARN_BYTES', 18):
            code, payload, _ = self.main()
        self.assertNotIn('film.mp4', '\n'.join(payload['blockers'] + payload['warnings']))
        self.assertEqual(code, 2)

    def test_lfs_clean_filter_skips_working_tree_size(self):
        self.git('config', 'filter.lfs.clean', 'git-lfs clean -- %f')
        (self.repo / '.gitattributes').write_text('*.mp4 filter=lfs\n')
        (self.repo / 'film.mp4').write_bytes(b'x' * 30)
        with patch.object(ship, 'BLOCK_BYTES', 20), patch.object(ship, 'WARN_BYTES', 18):
            code, payload, _ = self.main()
        self.assertNotIn('GitHub rejects', '\n'.join(payload['blockers']))
        self.assertNotIn('GitHub warns', '\n'.join(payload['warnings']))
        self.assertIn('film.mp4', payload['repo']['buckets']['commit'])
        self.assertEqual(code, 2)

    def test_plan_keeps_an_old_worktree(self):
        other = self.root / 'old-tree'
        self.git('worktree', 'add', '-b', 'old', str(other))
        code, payload, _ = self.main('--cleanup-report')
        self.assertEqual(code, 0, payload)
        self.assertTrue(other.exists())
        self.assertNotIn('cleanup', [op['op'] for op in payload['pending']])
        self.assertEqual(payload['cleanup'][0]['action'], 'remove')

    def test_apply_preserves_old_worktree_and_merged_branch(self):
        other = self.root / 'old-tree'
        self.git('worktree', 'add', '-b', 'old', str(other))
        code, payload, scanner = self.main('--apply')
        self.assertEqual(code, 0, payload)
        scanner.assert_not_called()
        self.assertTrue(other.exists())
        self.assertNotIn('cleanup_result', payload)
        self.assertIn('old', self.git('branch', '--list', 'old'))

    def test_dirty_or_unique_worktree_stays(self):
        dirty = self.root / 'dirty-tree'
        unique = self.root / 'unique-tree'
        self.git('worktree', 'add', '-b', 'dirty-branch', str(dirty))
        self.git('worktree', 'add', '-b', 'unique-branch', str(unique))
        (dirty / 'a.txt').write_text('local edit\n')
        subprocess.run(['git', '-C', str(unique), 'commit', '--allow-empty', '-m', 'only here'], check=True)
        code, payload, _ = self.main('--apply', '--cleanup-report')
        self.assertEqual(code, 0, payload)
        self.assertTrue(dirty.exists())
        self.assertTrue(unique.exists())
        reasons = {Path(item['path']).name: item['reason'] for item in payload['cleanup']}
        self.assertEqual(reasons['dirty-tree'], 'dirty')
        self.assertEqual(reasons['unique-tree'], 'unique-commits')

    def test_main_worktree_stays_when_shipping_from_a_linked_tree(self):
        linked = self.root / 'linked'
        self.git('worktree', 'add', '-b', 'feature', str(linked))
        with patch.object(ship, 'scan', return_value=CLEAN):
            payload = ship.ship(linked, True, [], [])
        self.assertFalse(payload['blockers'], payload)
        self.assertTrue((self.repo / '.git').is_dir())
        self.assertTrue(linked.exists())
        self.assertTrue((self.repo / 'a.txt').exists())

    def test_failed_push_does_not_remove_a_worktree(self):
        remote = self.remote()
        hook = remote / 'hooks' / 'pre-receive'
        hook.write_text('#!/bin/sh\nexit 1\n')
        hook.chmod(0o755)
        other = self.root / 'old-tree'
        self.git('worktree', 'add', '-b', 'old', str(other))
        (self.repo / 'a.txt').write_text('two\n')
        code, payload, _ = self.main('--apply', '-m', 'x')
        self.assertEqual(code, 1, payload)
        self.assertTrue(other.exists())
        self.assertTrue(any('push failed' in item for item in payload['blockers']))

    def test_recent_worktree_stays(self):
        other = self.root / 'live-session'
        self.git('worktree', 'add', '-b', 'live', str(other))
        with patch.object(ship, 'RECENT_SECONDS', 3600):
            code, payload, _ = self.main('--apply', '--cleanup-report')
        self.assertEqual(code, 0, payload)
        self.assertTrue(other.exists())
        self.assertEqual(payload['cleanup'][0]['reason'], 'recent')

    def test_missing_worktree_is_reported_without_pruning(self):
        other = self.root / 'old-tree'
        self.git('worktree', 'add', '-b', 'old', str(other))
        shutil.rmtree(other)
        code, payload, _ = self.main('--apply')
        self.assertEqual(code, 0, payload)
        self.assertIn('old-tree', self.git('worktree', 'list'))
        self.assertNotIn('cleanup_result', payload)

    def test_leftover_directory_stays_until_separately_authorized(self):
        leftover = self.repo / '.worktrees' / 'stale'
        leftover.mkdir(parents=True)
        (leftover / 'note.txt').write_text('old\n')
        trash = self.root / 'trash'
        code, payload, _ = self.main('--apply')
        self.assertEqual(code, 0, payload)
        self.assertTrue(leftover.exists())
        self.assertEqual((leftover / 'note.txt').read_text(), 'old\n')
        self.assertFalse(trash.exists())
        self.assertNotIn('cleanup_result', payload)


class ScanTests(unittest.TestCase):
    def test_missing_scanner_blocks(self):
        with patch.object(ship.shutil, 'which', return_value=None):
            self.assertFalse(ship.scan(Path('/unused'), 'origin')['ok'])

    def test_scanner_output_is_not_exposed(self):
        with patch.object(ship.shutil, 'which', return_value='/bin/gitleaks'), \
             patch.object(ship.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, 'sensitive diagnostic', '')):
            self.assertNotIn('sensitive diagnostic', str(ship.scan(Path('/unused'), 'origin')))


@unittest.skipUnless(shutil.which('gitleaks'), 'gitleaks not installed')
class RealScanTests(GitFixture):
    """The scan covers what the push sends, not history the remote already has."""
    TOKEN = 'ghp_' + 'Zq7Rk2Lm9Xw4Tb8Nc1Vd6Hf3Jg5Ps0Ya2Ue7Wi'

    def main(self, *argv):
        with patch.object(ship, 'current_repo', return_value=self.repo), \
             patch('sys.argv', ['ship.py', *argv]), contextlib.redirect_stdout(io.StringIO()) as output:
            code = ship.main()
        return code, json.loads(output.getvalue())

    def test_staged_leak_blocks_and_unstages(self):
        self.remote()
        (self.repo / 'config.txt').write_text(f'token = "{self.TOKEN}"\n')
        code, payload = self.main('--apply', '-m', 'x')
        self.assertEqual(code, 1, payload)
        self.assertNotIn(self.TOKEN, json.dumps(payload))
        self.assertEqual(self.git('diff', '--cached', '--name-only'), '')
        self.assertEqual(self.git('rev-list', '--count', 'HEAD'), '1')

    def test_real_commit_hook_added_leak_cannot_reach_remote(self):
        remote = self.remote()
        before = self.remote_head(remote)
        hooks = self.root / 'hooks'
        hooks.mkdir()
        hook = hooks / 'pre-commit'
        hook.write_text('#!/bin/sh\nprintf \'%s\\n\' \'token = "' + self.TOKEN
                        + '"\' > hook-added.txt\ngit add hook-added.txt\n')
        hook.chmod(0o755)
        self.git('config', 'core.hooksPath', str(hooks))
        (self.repo / 'a.txt').write_text('two\n')
        code, payload = self.main('--apply', '-m', 'fix: a')
        self.assertEqual(code, 1, payload)
        self.assertEqual([d['op'] for d in payload['done']], ['commit'])
        self.assertIn('hook-added.txt', self.git('show', '--name-only', '--format=', 'HEAD'))
        self.assertEqual(self.remote_head(remote), before)
        self.assertNotIn(self.TOKEN, json.dumps(payload))

    def test_pushed_history_and_ignored_files_do_not_block(self):
        remote = self.remote()
        (self.repo / 'old.txt').write_text(f'token = "{self.TOKEN}"\n')
        self.git('add', 'old.txt')
        self.git('commit', '-m', 'old leak already on the remote')
        self.git('push', '-q')
        (self.repo / '.gitignore').write_text('local/\n')
        (self.repo / 'local').mkdir()
        (self.repo / 'local' / 'notes.txt').write_text(f'token = "{self.TOKEN}"\n')
        (self.repo / 'a.txt').write_text('two\n')
        code, payload = self.main('--apply', '-m', 'fix: a', 'a.txt')
        self.assertEqual(code, 0, payload)
        self.assertEqual(self.remote_head(remote), self.git('rev-parse', 'HEAD'))


if __name__ == '__main__':
    unittest.main()
