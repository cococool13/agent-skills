"""Consolidate this repository, validate an immutable commit, and release it once."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time
import uuid

import ship as core
from ship_checks import discover
from ship_release import artifact_digests, finish, run_checks, verify_completed
from ship_state import Blocked, Journal, load_profile, locked, state_dir


def require(repo: Path, *args: str):
    result = core.run(repo, *args, timeout=300)
    if result.returncode:
        raise Blocked(f'git {args[0]} did not complete; inspect local Git state (raw hook output withheld)')
    return result.stdout.strip()


def inventory(repo: Path, remote: str, main: str) -> dict:
    trees = []
    for row in core.list_worktrees(repo):
        if row.get('bare'):
            continue
        path = Path(row['path'])
        if path.is_relative_to(state_dir(repo)) and path.name.startswith('validate-'):
            continue
        if not path.is_dir():
            raise Blocked('registered worktree is unavailable; restore its path before consolidation')
        if state_dir(path) != state_dir(repo):
            raise Blocked('worktree does not belong to the active repository')
        info = core.inspect(path, main)
        if any('unfinished' in b or 'unmerged' in b for b in info['blockers']):
            raise Blocked(f'unfinished Git operation in worktree {path}')
        trees.append({'path': str(path), 'branch': info['branch'], 'head': info['head'],
                      'commit': info['buckets']['commit'], 'staged': info['staged'],
                      'excluded': {k: v for k, v in info['buckets'].items() if k != 'commit' and v},
                      'state': core.status(path)})
    prefixes = ['refs/heads/'] + ([f'refs/remotes/{remote}/'] if remote else [])
    refs = []
    for prefix in prefixes:
        for line in require(repo, 'for-each-ref', '--format=%(refname) %(objectname)', prefix).splitlines():
            ref, sha = line.split(' ', 1)
            if ref.endswith('/HEAD'):
                continue
            refs.append({'ref': ref, 'sha': sha})
    return {'worktrees': trees, 'sources': refs, 'main': main, 'remote': remote}


def main_checkout(repo: Path, main: str, remote: str, trees: list[dict], journal: Journal) -> Path:
    for tree in trees:
        if tree['branch'] == main:
            return Path(tree['path'])
    path = state_dir(repo) / ('main-' + journal.data['run_id'])
    if core.ok(repo, 'show-ref', '--verify', '--quiet', f'refs/heads/{main}'):
        require(repo, 'worktree', 'add', str(path), main)
    else:
        base = f'{remote}/{main}' if remote and core.ok(repo, 'rev-parse', '--verify', f'{remote}/{main}') else 'HEAD'
        require(repo, 'worktree', 'add', '-b', main, str(path), base)
    return path


def snapshot(tree: dict, remote: str, note: str, journal: Journal):
    path = Path(tree['path'])
    if core.out(path, 'rev-parse', 'HEAD') != tree['head'] or core.status(path) != tree['state']:
        raise Blocked('worktree changed after inventory; re-inventory before committing')
    if set(tree['staged']) - set(tree['commit']):
        raise Blocked('an excluded path is staged; preserve it and remove it from the release index')
    if tree['commit']:
        # Reuse the tested index rollback and scan behavior; no push occurs here.
        payload = {}
        info = {'staged': tree['staged'], 'remote': remote}
        error = core.step(path, {'op': 'commit', 'files': tree['commit']}, info,
                          [note or 'chore: consolidate repository work'], payload)
        if error:
            raise Blocked(error)
        if not tree['branch']:
            name = 'ship/recovered-' + journal.data['run_id'] + '-' + hashlib.sha256(str(path).encode()).hexdigest()[:6]
            require(path, 'switch', '-c', name)
    if any(core.bucket(p, row['xy'] == '??', path) == 'commit'
           for row in core.status(path) for p in row['paths']):
        raise Blocked('worktree changed during its commit; collect the remaining work before integration')


def merge_sources(main_path: Path, sources: list[dict], journal: Journal):
    for source in sources:
        sha = source['sha']
        if core.ok(main_path, 'merge-base', '--is-ancestor', sha, 'HEAD'):
            continue
        journal.save(phase='integrating', merging=source)
        result = core.run(main_path, 'merge', '--no-edit', sha, timeout=300)
        if result.returncode:
            core.run(main_path, 'merge', '--abort')
            raise Blocked('merge conflict; agent must resolve the recorded source on main, then resume')
        journal.save(integrated=[*journal.data.get('integrated', []), source])


def validate(main_path: Path, profile: dict, journal: Journal) -> Path:
    sha = core.out(main_path, 'rev-parse', 'HEAD')
    tree = core.out(main_path, 'rev-parse', 'HEAD^{tree}')
    checkout = state_dir(main_path) / ('validate-' + journal.data['run_id'] + '-' + sha[:12])
    if journal.data.get('validated_sha') == sha and journal.data.get('validation_checkout') == str(checkout):
        if checkout.exists() and not core.out(checkout, 'status', '--porcelain', '--untracked-files=no'):
            if artifact_digests(checkout, profile.get('artifacts', [])) == journal.data.get('artifacts'):
                return checkout
    if checkout.exists():
        # Never overwrite a prior failed validation checkout.
        checkout = checkout.with_name(checkout.name + '-' + uuid.uuid4().hex[:6])
    require(main_path, 'worktree', 'add', '--detach', str(checkout), sha)
    # This worktree is retained as evidence, and must not be included next time.
    journal.save(phase='validating', sha=sha, tree=tree, validation_checkout=str(checkout))
    prepare = run_checks(checkout, profile.get('prepare', []), journal, 'prepare')
    checks = run_checks(checkout, profile['checks'], journal, 'checks')
    if core.out(checkout, 'rev-parse', 'HEAD') != sha or core.out(checkout, 'status', '--porcelain', '--untracked-files=no'):
        raise Blocked('validation changed committed inputs; agent must fix generators on main and validate again')
    if core.out(main_path, 'rev-parse', 'HEAD') != sha:
        raise Blocked('main changed during validation; validate the new combined commit')
    digests = artifact_digests(checkout, profile.get('artifacts', []))
    for name in profile.get('artifacts', []):
        executable = shutil.which('gitleaks')
        if not executable:
            raise Blocked('gitleaks is required to scan release artifacts')
        result = subprocess.run([executable, 'dir', str(checkout / name), '--redact', '--no-banner'],
                                capture_output=True, timeout=180)
        if result.returncode:
            raise Blocked('artifact scan rejected the output; raw scanner output withheld')
    journal.save(validated_sha=sha, checks=checks, prepare=prepare, artifacts=digests,
                 validation_checkout=str(checkout), phase='validated')
    return checkout


def push(main_path: Path, remote: str, main: str, journal: Journal):
    sha = journal.data['validated_sha']
    evidence = core.verify_remote(main_path, remote, main)
    if evidence.get('remote_sha') == sha:
        journal.save(remote_check=evidence)
        journal.done('push', sha=sha)
        return
    previous = journal.data.get('operations', {}).get('push', {})
    if previous.get('status') in ('uncertain', 'done'):
        evidence = core.verify_remote(main_path, remote, main)
        if evidence.get('remote_sha') != sha:
            raise Blocked('prior push cannot be confirmed; no push repeated')
        journal.done('push', sha=sha)
        return
    scan = core.scan(main_path, remote)
    if not scan['ok']:
        raise Blocked(scan['summary'])
    if core.out(main_path, 'rev-parse', 'HEAD') != sha:
        raise Blocked('main moved after validation; no unvalidated commit pushed')
    journal.intent('push')
    try:
        response = core.run(main_path, 'push', remote, f'{sha}:refs/heads/{main}', timeout=180, env=core.NET_ENV)
    except (OSError, subprocess.TimeoutExpired):
        response = None
    evidence = core.verify_remote(main_path, remote, main)
    journal.save(remote_check=evidence)
    if evidence.get('remote_sha') != sha:
        raise Blocked('push outcome not confirmed; inspect remote_check, never automatically retry')
    journal.done('push', sha=sha)
    if response is None or response.returncode:
        journal.save(push_transport='interrupted_but_remote_confirmed')


def sync_trees(main_path: Path, main: str, journal: Journal):
    sha = journal.data['validated_sha']
    for tree in journal.data['inventory']['worktrees']:
        path = Path(tree['path'])
        if path == main_path or not tree['branch']:
            continue
        info = core.inspect(path, main)
        if info['buckets']['commit'] or info['staged']:
            raise Blocked('new work arrived in a source worktree; do not discard it to make the repository clean')
        if not core.ok(path, 'merge-base', '--is-ancestor', 'HEAD', sha):
            raise Blocked('source branch gained commits after integration; collect them before completing')
        require(path, 'merge', '--ff-only', sha)
        if core.inspect(path, main)['buckets']['commit']:
            raise Blocked('new work arrived in a source worktree after fast-forward; preserve it for a follow-up release')


def repository_release(repo: Path | None, apply=False, resume=False, status_only=False,
                       filename='', note='', new_release=False) -> dict:
    result = {'mode': 'repository', 'blockers': [], 'warnings': []}
    if repo is None:
        return {**result, 'blockers': ['not in a Git repository']}
    journal = Journal(repo)
    try:
        if status_only:
            return {**result, 'journal': journal.read(), 'journal_path': str(journal.path)}
        profile = load_profile(repo, filename)
        main = profile.get('main', 'main')
        remote = profile.get('remote') or core.destination(repo, core.out(repo, 'branch', '--show-current'))[0]
        if not remote or remote == '.':
            raise Blocked('no unambiguous remote; agent must resolve the repository release destination')
        result.update(profile=profile, check_candidates=discover(repo), deploy_hints=core.deploy_hints(repo))
        if not apply:
            result['inventory'] = inventory(repo, remote, main)
            result['needs_profile'] = not bool(profile)
            return result
        if not profile:
            raise Blocked('agent must derive a reviewed release profile from project docs; no user check-in is needed')
        if not profile['checks']:
            raise Blocked('release profile needs the required project checks; agent must derive them autonomously')
        with locked(repo):
            old = journal.read()
            if resume:
                if not old:
                    raise Blocked('no release journal exists to resume')
                if (main, remote) != (old['main'], old['remote']):
                    raise Blocked('release destination changed; preserve the saved run and restore its intended destination')
                if old['profile_digest'] != profile['digest'] and old.get('operations'):
                    raise Blocked('release profile changed; reconcile the existing release before starting a new one')
                if old['profile_digest'] != profile['digest']:
                    journal.save(profile_digest=profile['digest'], validated_sha='', artifacts={})
                main_path = Path(old['main_path']) if old.get('main_path') else repo
                if old.get('phase') == 'complete':
                    if core.verify_remote(main_path, remote, main).get('remote_sha') != old['validated_sha']:
                        raise Blocked('completed release was superseded; start a new --all release rather than replaying it')
                    verify_completed(Path(old['validation_checkout']), profile, journal)
                    return {**result, 'verified': True, 'sha': old['validated_sha'], 'journal': old,
                            'journal_path': str(journal.path)}
            else:
                if old and old.get('phase') != 'complete':
                    raise Blocked('unfinished release exists; use --resume instead of duplicating it')
                if core.run(repo, 'fetch', '--quiet', remote, timeout=60, env=core.NET_ENV).returncode:
                    raise Blocked('fetch failed; remote state unknown')
                initial = inventory(repo, remote, main)
                if (not new_release and old.get('phase') == 'complete' and old.get('profile_digest') == profile['digest']
                        and not any(t['commit'] or t['staged'] for t in initial['worktrees'])
                        and all(t['head'] == old['validated_sha'] for t in initial['worktrees'])
                        and all(core.ok(repo, 'merge-base', '--is-ancestor', s['sha'], old['validated_sha']) for s in initial['sources'])
                        and core.verify_remote(repo, remote, main).get('remote_sha') == old['validated_sha']):
                    checkout = Path(old['validation_checkout'])
                    if not checkout.exists():
                        raise Blocked('completed release evidence is unavailable; investigate before a new release')
                    if core.out(checkout, 'rev-parse', 'HEAD') != old['validated_sha'] or core.out(checkout, 'status', '--porcelain', '--untracked-files=no') or artifact_digests(checkout, profile.get('artifacts', [])) != old['artifacts']:
                        raise Blocked('completed validation evidence changed; inspect it before a corrective release')
                    verify_completed(checkout, profile, journal)
                    journal.save(followup_required='')
                    return {**result, 'verified': True, 'already_complete': True, 'sha': old['validated_sha'],
                            'journal': journal.data, 'journal_path': str(journal.path)}
                journal.data = {}
                journal.save(run_id='ship-' + uuid.uuid4().hex[:16], phase='collecting',
                             profile_digest=profile['digest'], main=main, remote=remote,
                             inventory=initial, operations={}, started_at=time.time(),
                             summary=(core.clean_messages([note]) or ['Merge repository work'])[0].splitlines()[0])
                for tree in initial['worktrees']:
                    snapshot(tree, remote, note, journal)
                gathered = inventory(repo, remote, main)
                main_path = main_checkout(repo, main, remote, gathered['worktrees'], journal)
                journal.save(main_path=str(main_path), sources=gathered['sources'], inventory=gathered)
            if not journal.data.get('main_path'):
                # A local snapshot failure is recoverable without repeating external work.
                gathered = inventory(repo, remote, main)
                for tree in gathered['worktrees']:
                    snapshot(tree, remote, note, journal)
                main_path = main_checkout(repo, main, remote, gathered['worktrees'], journal)
                journal.save(main_path=str(main_path), sources=inventory(repo, remote, main)['sources'], inventory=gathered)
            external_started = bool(journal.data.get('operations'))
            if core.out(main_path, 'branch', '--show-current') != main:
                raise Blocked('recorded main worktree is now on another branch; restore its branch before resuming')
            if not external_started:
                if resume:
                    gathered = inventory(repo, remote, main)
                    for tree in gathered['worktrees']:
                        snapshot(tree, remote, note, journal)
                    gathered = inventory(repo, remote, main)
                    sources = {s['sha']: s for s in [*journal.data['sources'], *gathered['sources']]}
                    journal.save(sources=list(sources.values()), inventory=gathered)
                merge_sources(main_path, journal.data['sources'], journal)
                if core.inspect(main_path, main)['buckets']['commit']:
                    current = inventory(main_path, remote, main)
                    snapshot(next(t for t in current['worktrees'] if Path(t['path']) == main_path), remote, note, journal)
                checkout = validate(main_path, profile, journal)
                for tree in journal.data['inventory']['worktrees']:
                    path = Path(tree['path'])
                    if path == main_path:
                        continue
                    if core.out(path, 'rev-parse', 'HEAD') != tree['head'] or core.inspect(path, main)['buckets']['commit']:
                        raise Blocked('source worktree changed during validation; resume to collect the new work before pushing')
                current = inventory(repo, remote, main)
                if any(not core.ok(main_path, 'merge-base', '--is-ancestor', source['sha'], journal.data['validated_sha'])
                       for source in current['sources']):
                    raise Blocked('a branch gained work during validation; resume to collect it before pushing')
                if profile.get('integration') == 'pr':
                    from ship_pr import integrate
                    integrate(main_path, remote, main, journal, profile['deploy'].get('timeout', 1800))
                    checkout = validate(main_path, profile, journal)
                push(main_path, remote, main, journal)
            else:
                if profile.get('integration') == 'pr' and journal.data.get('operations', {}).get('push', {}).get('status') != 'done':
                    from ship_pr import integrate
                    integrate(main_path, remote, main, journal, profile['deploy'].get('timeout', 1800))
                    checkout = validate(main_path, profile, journal)
                if core.out(main_path, 'rev-parse', 'HEAD') != journal.data['validated_sha']:
                    raise Blocked('main moved after external release began; reconcile before continuing')
                checkout = Path(journal.data['validation_checkout'])
                if not checkout.exists() or artifact_digests(checkout, profile.get('artifacts', [])) != journal.data['artifacts']:
                    raise Blocked('validated artifacts are unavailable or changed; do not rebuild and replay an uncertain release')
                if core.out(checkout, 'rev-parse', 'HEAD') != journal.data['validated_sha'] or core.out(checkout, 'status', '--porcelain', '--untracked-files=no'):
                    raise Blocked('validation checkout changed after external release began; do not deploy different inputs')
                push(main_path, remote, main, journal)
            journal.save(phase='releasing')
            finish(checkout, profile, journal)
            followup = ''
            try:
                sync_trees(main_path, main, journal)
            except Blocked as exc:
                if str(exc).startswith(('new work arrived', 'source branch gained')):
                    followup = str(exc)
                else:
                    raise
            if core.out(main_path, 'rev-parse', 'HEAD') != journal.data['validated_sha'] or core.inspect(main_path, main)['buckets']['commit']:
                followup = 'main gained work during release'
            # Every captured tip must remain reachable from the final main commit.
            if not all(core.ok(main_path, 'merge-base', '--is-ancestor', s['sha'], journal.data['validated_sha'])
                       for s in journal.data['sources']):
                raise Blocked('a source tip is not included in main')
            current = inventory(repo, remote, main)
            if any(not core.ok(main_path, 'merge-base', '--is-ancestor', s['sha'], journal.data['validated_sha'])
                   for s in current['sources']):
                followup = 'a branch gained work during publication'
            journal.save(phase='complete', completed_at=time.time(),
                         excluded=[{'path': t['path'], 'files': t['excluded']} for t in journal.data['inventory']['worktrees'] if t['excluded']])
            if followup:
                journal.save(followup_required=followup)
                result.update(followup_required=True, pending=['collect_new_work'],
                              warnings=[followup + '; start a new --all release without repeating the completed operations'])
            result.update(verified=True, sha=journal.data['validated_sha'])
    except (Blocked, OSError, ValueError, subprocess.TimeoutExpired) as exc:
        message = str(exc) if isinstance(exc, Blocked) else f'{type(exc).__name__}; inspect Git and journal state before retrying'
        result['blockers'].append(message)
        if journal.data:
            # The release context may have released its lock while unwinding.
            # Never overwrite another process's newer journal in that interval.
            try:
                with locked(repo):
                    latest = Journal(repo)
                    latest.read()
                    if latest.data.get('run_id') == journal.data.get('run_id'):
                        latest.save(blocker=message)
                        journal.data = latest.data
            except (Blocked, OSError, ValueError):
                pass
    result.update(journal=journal.data, journal_path=str(journal.path))
    return result
