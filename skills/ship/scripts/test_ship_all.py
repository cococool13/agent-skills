"""Repo-wide acceptance tests: real local Git, isolated checkouts, fake providers."""
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import ship
from ship_all import inventory, repository_release
from ship_release import artifact_digests, cloudflare, finish, watch_ci
from ship_state import Blocked, Journal, load_profile, locked, state_dir
from test_ship import GitFixture, CLEAN


class RepositoryReleaseTests(GitFixture):
    def profile(self, code='pass', extra=''):
        (self.repo / 'ship.toml').write_text(
            'version = 1\n[[checks]]\nargv = ' + json.dumps([sys.executable, '-c', code])
            + '\n[deploy]\nmode = "none"\n' + extra)

    def release(self, **kwargs):
        with patch.object(ship, 'scan', return_value=CLEAN):
            return repository_release(self.repo, **kwargs)

    def worktree(self, name):
        path = self.root / name
        self.git('worktree', 'add', '-b', name, str(path))
        return path

    def test_all_dirty_worktrees_and_unchecked_branch_reach_main(self):
        remote = self.remote()
        first, second = self.worktree('first'), self.worktree('second')
        (first / 'one.txt').write_text('one')
        (second / 'two.txt').write_text('two')
        self.git('branch', 'unchecked')
        self.profile("from pathlib import Path; assert all(Path(p).exists() for p in ['one.txt','two.txt'])")
        (self.repo / 'a.txt').write_text('updated\n')
        result = self.release(apply=True)
        self.assertEqual(result['blockers'], [], result)
        self.assertTrue(result['verified'])
        self.assertEqual(self.remote_head(remote), self.git('rev-parse', 'main'))
        for path in (self.repo, first, second):
            self.assertEqual(subprocess.check_output(['git', '-C', str(path), 'status', '--porcelain'], text=True), '')
            self.assertEqual(subprocess.check_output(['git', '-C', str(path), 'rev-parse', 'HEAD'], text=True).strip(), result['sha'])
        self.assertTrue((first / 'two.txt').exists())
        self.assertTrue((second / 'one.txt').exists())
        self.assertEqual(result['journal']['phase'], 'complete')
        self.assertTrue(Path(result['journal']['validation_checkout']).exists())

    def test_plan_is_read_only_and_no_profile_needs_agent_setup(self):
        self.remote()
        other = self.worktree('feature')
        (other / 'new.txt').write_text('new')
        head = self.git('rev-parse', 'HEAD')
        result = self.release()
        self.assertEqual(result['blockers'], [], result)
        self.assertTrue(result['needs_profile'])
        self.assertEqual(self.git('rev-parse', 'HEAD'), head)
        self.assertFalse((state_dir(self.repo) / 'latest.json').exists())
        self.assertTrue((other / 'new.txt').exists())

    def test_merge_conflict_preserves_commits_and_does_not_push(self):
        remote = self.remote()
        before = self.remote_head(remote)
        other = self.worktree('conflict')
        (other / 'a.txt').write_text('theirs\n')
        (self.repo / 'a.txt').write_text('ours\n')
        self.profile()
        result = self.release(apply=True)
        self.assertTrue(any('merge conflict' in b for b in result['blockers']), result)
        self.assertEqual(self.remote_head(remote), before)
        self.assertFalse((self.repo / '.git' / 'MERGE_HEAD').exists())
        self.assertEqual((other / 'a.txt').read_text(), 'theirs\n')
        self.assertEqual(self.git('log', '-1', '--format=%s', 'conflict'), 'chore: consolidate repository work')

    def test_secrets_excluded_without_being_opened(self):
        self.remote()
        self.profile()
        (self.repo / '.env').write_text('fixture')
        (self.repo / 'auth.json').write_text('fixture')
        result = self.release(apply=True)
        self.assertEqual(result['blockers'], [], result)
        self.assertNotIn('.env', self.git('ls-tree', '--name-only', 'HEAD').splitlines())
        self.assertNotIn('auth.json', self.git('ls-tree', '--name-only', 'HEAD').splitlines())
        self.assertTrue(result['journal']['excluded'])

    def test_credential_related_source_code_is_included(self):
        self.remote()
        self.profile()
        (self.repo / 'KeychainStore.swift').write_text('struct KeychainStore {}')
        (self.repo / 'test_credentials.py').write_text('assert True')
        (self.repo / '.env.py').write_text('fixture')
        result = self.release(apply=True)
        self.assertEqual(result['blockers'], [], result)
        paths = self.git('ls-tree', '--name-only', 'HEAD').splitlines()
        self.assertIn('KeychainStore.swift', paths)
        self.assertIn('test_credentials.py', paths)
        self.assertNotIn('.env.py', paths)

    def test_check_runs_after_real_commit_hook_modifies_code(self):
        remote = self.remote()
        before = self.remote_head(remote)
        hooks = self.root / 'hooks'
        hooks.mkdir()
        hook = hooks / 'pre-commit'
        hook.write_text('#!/bin/sh\nprintf bad > hook-output.txt\ngit add hook-output.txt\n')
        hook.chmod(0o755)
        self.git('config', 'core.hooksPath', str(hooks))
        self.profile("from pathlib import Path; assert Path('hook-output.txt').read_text() == 'good'")
        result = self.release(apply=True)
        self.assertTrue(any('check failed' in b for b in result['blockers']), result)
        self.assertEqual(self.remote_head(remote), before)

    def test_detached_dirty_worktree_is_preserved_and_integrated(self):
        self.remote()
        other = self.root / 'detached'
        self.git('worktree', 'add', '--detach', str(other))
        (other / 'detached.txt').write_text('new')
        self.profile()
        result = self.release(apply=True)
        self.assertEqual(result['blockers'], [], result)
        self.assertTrue((self.repo / 'detached.txt').exists())
        self.assertIn('ship/recovered-', self.git('branch', '--list'))

    def test_unfinished_release_requires_resume_not_replay(self):
        self.remote()
        self.profile('raise SystemExit(1)')
        first = self.release(apply=True)
        self.assertTrue(first['blockers'])
        second = self.release(apply=True)
        self.assertTrue(any('--resume' in b for b in second['blockers']), second)

    def test_resume_push_timeout_reconciles_without_second_push(self):
        remote = self.remote()
        self.profile()
        original = ship.run
        count = []
        def timeout_after_push(repo, *args, **kwargs):
            result = original(repo, *args, **kwargs)
            if args[0] == 'push':
                count.append(args)
                raise subprocess.TimeoutExpired('push', 180)
            return result
        with patch.object(ship, 'run', side_effect=timeout_after_push):
            first = self.release(apply=True)
        self.assertEqual(first['blockers'], [], first)
        second = self.release(resume=True, apply=True)
        self.assertEqual(second['blockers'], [], second)
        self.assertEqual(len(count), 1)
        self.assertEqual(self.remote_head(remote), first['sha'])

    def test_lock_is_shared_across_worktrees(self):
        other = self.worktree('locked')
        with locked(self.repo):
            with self.assertRaises(Blocked):
                with locked(other):
                    self.fail('second lock acquired')

    def test_internal_validation_worktrees_are_not_recollected(self):
        self.remote()
        self.profile()
        first = self.release(apply=True)
        self.assertEqual(first['blockers'], [], first)
        validation = first['journal']['validation_checkout']
        result = self.release()
        self.assertNotIn(validation, [r['path'] for r in result['inventory']['worktrees']])

    def test_profile_rejects_escape_and_credential_filename(self):
        self.profile()
        text = (self.repo / 'ship.toml').read_text().replace('[deploy]', 'cwd = "../outside"\n[deploy]')
        (self.repo / 'ship.toml').write_text(text)
        with self.assertRaises(Blocked):
            load_profile(self.repo)
        with self.assertRaises(Blocked):
            load_profile(self.repo, str(self.repo / '.env'))

    def test_local_failed_checks_can_be_fixed_and_resumed(self):
        self.remote()
        self.profile('raise SystemExit(1)')
        first = self.release(apply=True)
        self.assertTrue(first['blockers'])
        self.profile('pass')
        second = self.release(resume=True, apply=True)
        self.assertEqual(second['blockers'], [], second)
        self.assertTrue(second['verified'])

    def test_private_profile_is_discovered_automatically(self):
        directory = state_dir(self.repo)
        directory.mkdir()
        (directory / 'profile.toml').write_text('[[checks]]\nargv=["true"]\n[deploy]\nmode="none"\n')
        self.assertEqual(load_profile(self.repo)['checks'][0]['argv'], ['true'])

    def test_work_arriving_during_publication_gets_a_new_release(self):
        self.remote()
        other = self.worktree('ongoing')
        self.profile()
        def publish(checkout, profile, journal):
            (other / 'late.txt').write_text('late work')
            journal.save(phase='released')
        with patch('ship_all.finish', side_effect=publish):
            first = self.release(apply=True)
        self.assertEqual(first['blockers'], [], first)
        self.assertTrue(first['followup_required'])
        history = state_dir(self.repo) / 'runs' / (first['journal']['run_id'] + '.json')
        self.assertTrue(history.exists())
        second = self.release(apply=True)
        self.assertEqual(second['blockers'], [], second)
        self.assertNotIn('followup_required', second)
        self.assertTrue((self.repo / 'late.txt').exists())
        self.assertNotEqual(first['sha'], second['sha'])
        self.assertEqual(json.loads(history.read_text())['validated_sha'], first['sha'])

    def test_unchanged_completed_release_does_not_publish_again(self):
        self.remote()
        self.profile()
        first = self.release(apply=True)
        self.assertEqual(first['blockers'], [], first)
        with patch('ship_all.finish', side_effect=AssertionError('must not republish')):
            second = self.release(apply=True)
        self.assertEqual(second['blockers'], [], second)
        self.assertTrue(second['already_complete'])
        self.assertEqual(first['journal']['run_id'], second['journal']['run_id'])

    def test_protected_main_uses_one_pr_then_validates_merged_commit(self):
        remote = self.remote()
        self.profile()
        profile = self.repo / 'ship.toml'
        profile.write_text(profile.read_text().replace('version = 1', 'version = 1\nintegration = "pr"'))
        state = {'created': False, 'merged': False}
        calls = []
        def query(argv, cwd):
            if not state['created']:
                return []
            row = {'number': 1, 'headRefOid': state['candidate'], 'state': 'MERGED' if state['merged'] else 'OPEN',
                   'url': 'https://example.invalid/pull/1', 'mergeCommit': {'oid': state.get('merge_sha', '')}}
            return [row] if argv[2] == 'list' else row
        def command(argv, cwd, timeout=60, account=''):
            calls.append(argv)
            if argv[2] == 'create':
                state.update(created=True, candidate=self.git('rev-parse', 'HEAD'), branch=argv[argv.index('--head')+1])
            elif argv[2] == 'merge':
                clone = self.root / 'pr-merge'
                subprocess.run(['git', 'clone', '-q', str(remote), str(clone)], check=True)
                for args in (['config', 'user.name', 'PR Fixture'], ['config', 'user.email', 'pr@example.invalid'],
                             ['merge', '--no-ff', '--no-edit', 'origin/'+state['branch']], ['push', 'origin', 'main']):
                    subprocess.run(['git', '-C', str(clone), *args], check=True, capture_output=True)
                state.update(merged=True, merge_sha=self.remote_head(remote))
            return subprocess.CompletedProcess(argv, 0)
        with patch('ship_pr.read_json', side_effect=query), patch('ship_pr.capture', side_effect=command):
            result = self.release(apply=True)
        self.assertEqual(result['blockers'], [], result)
        self.assertEqual(result['sha'], state['merge_sha'])
        self.assertNotEqual(result['sha'], state['candidate'])
        self.assertEqual(result['journal']['validated_sha'], state['merge_sha'])
        self.assertEqual(len(calls), 2)
        self.assertEqual(self.remote_head(remote), result['sha'])


class ProviderTests(GitFixture):
    def journal(self):
        j = Journal(self.repo)
        j.save(sha=self.git('rev-parse', 'HEAD'), main='main', run_id='fixture', operations={})
        return j

    def test_ci_matches_exact_sha_and_checks_every_workflow(self):
        journal = self.journal()
        calls = []
        def query(argv, cwd):
            calls.append(argv)
            return [{'databaseId': len(calls), 'attempt': 1, 'headSha': journal.data['sha'],
                     'status': 'completed', 'conclusion': 'success'}]
        with patch('ship_release.read_json', side_effect=query):
            results = watch_ci(self.repo, {'workflows': ['test.yml', 'deploy.yml'], 'timeout': 1}, journal)
        self.assertEqual(len(results), 2)
        self.assertTrue(all(journal.data['sha'] in argv for argv in calls))

    def test_ci_failure_does_not_deploy_manually(self):
        journal = self.journal()
        rows = [{'databaseId': 1, 'headSha': journal.data['sha'], 'status': 'completed', 'conclusion': 'failure'}]
        with patch('ship_release.read_json', return_value=rows), self.assertRaises(Blocked):
            watch_ci(self.repo, {'workflows': ['deploy.yml'], 'timeout': 1}, journal)

    def test_uncertain_publish_is_never_retried(self):
        journal = self.journal()
        journal.intent('publish-0')
        profile = {'deploy': {'mode': 'none'}, 'publish': [{'argv': ['fake-publish'], 'cwd': '.', 'timeout': 1}]}
        with patch('ship_release.capture') as process, self.assertRaises(Blocked):
            finish(self.repo, profile, journal)
        process.assert_not_called()

    def test_uncertain_command_deploy_can_be_confirmed_read_only(self):
        journal = self.journal()
        journal.intent('deploy')
        config = {'mode': 'command', 'argv': ['deploy'], 'verify': ['verify', '{sha}']}
        with patch('ship_release.read_json', return_value={'sha': journal.data['sha'], 'deployed': True}), \
                patch('ship_release.capture') as process:
            finish(self.repo, {'deploy': config}, journal)
        process.assert_not_called()
        self.assertTrue(journal.data['deploy_verified'])

    def test_uncertain_publish_can_be_confirmed_without_republishing(self):
        journal = self.journal()
        journal.intent('publish-0')
        profile = {'deploy': {'mode': 'none'}, 'publish': [
            {'argv': ['publish'], 'verify': ['verify'], 'cwd': '.', 'timeout': 1}]}
        with patch('ship_release.read_json', return_value={'sha': journal.data['sha'], 'published': True}), \
                patch('ship_release.capture') as process:
            finish(self.repo, profile, journal)
        process.assert_not_called()
        self.assertTrue(journal.data['operations']['publish-0']['verified'])

    def test_cloudflare_upload_probe_promote_exact_version(self):
        journal = self.journal()
        journal.save(artifacts={})
        calls = []
        config = {'mode': 'cloudflare', 'name': 'fixture', 'environment': 'production',
                  'account': 'fixture-account', 'identity_url': 'https://example.invalid/release',
                  'probe': ['probe', '{sha}', '{version}'], 'wrangler': ['wrangler']}
        promoted = []
        def query(argv, cwd, account=''):
            if argv[0] == 'probe':
                self.assertIn('new-version', argv)
                return {'sha': journal.data['sha'], 'version': 'new-version', 'verified': True}
            if argv[1:3] == ['versions', 'list']:
                return [{'id': 'new-version', 'annotations': {'workers/tag': 'fixture'}}]
            return [{'id': 'deployment', 'created_on': '2026-10-26', 'versions': [
                {'version_id': 'new-version' if promoted else 'old-version', 'percentage': 100}]}]
        def command(argv, cwd, timeout=60, account=''):
            calls.append(argv)
            if argv[1:3] == ['versions', 'deploy']:
                promoted.append(True)
                self.assertIn('new-version@100%', argv)
            return subprocess.CompletedProcess(argv, 0)
        with patch('ship_release.read_json', side_effect=query), patch('ship_release.capture', side_effect=command), \
                patch('ship_release.http_check', return_value={'passed': True}):
            cloudflare(self.repo, config, {}, journal)
            cloudflare(self.repo, config, {}, journal)
        self.assertEqual(len(calls), 2)
        self.assertEqual(journal.data['version_id'], 'new-version')
        self.assertTrue(journal.data['version_probe']['verified'])
        self.assertEqual(journal.data['previous_deployment']['versions'][0]['version_id'], 'old-version')

    def test_bad_uploaded_version_probe_blocks_promotion(self):
        journal = self.journal()
        journal.save(artifacts={}, version_id='new-version')
        journal.done('upload')
        journal.save(previous_deployment={'id': 'old'})
        config = {'mode': 'cloudflare', 'name': 'fixture', 'environment': 'production',
                  'account': 'fixture-account', 'identity_url': 'https://example.invalid/release',
                  'probe': ['probe'], 'wrangler': ['wrangler']}
        with patch('ship_release.read_json', return_value={'sha': 'wrong', 'verified': False}), \
                patch('ship_release.capture') as process, self.assertRaises(Blocked):
            cloudflare(self.repo, config, {}, journal)
        process.assert_not_called()

    def test_artifact_changes_are_detected(self):
        (self.repo / 'dist').mkdir()
        file = self.repo / 'dist' / 'app.js'
        file.write_text('first')
        first = artifact_digests(self.repo, ['dist'])
        file.write_text('second')
        self.assertNotEqual(first, artifact_digests(self.repo, ['dist']))


if __name__ == '__main__':
    unittest.main()
