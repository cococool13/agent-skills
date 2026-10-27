"""Exact-SHA CI tracking, version promotion, and read-only release evidence."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request

from ship_state import Blocked, Journal, contained


def capture(argv: list[str], cwd: Path, timeout=60, account='') -> subprocess.CompletedProcess:
    env = {**os.environ, 'GIT_TERMINAL_PROMPT': '0'}
    if account:
        env['CLOUDFLARE_ACCOUNT_ID'] = account
    try:
        return subprocess.run(argv, cwd=cwd, stdin=subprocess.DEVNULL, capture_output=True,
                              text=True, timeout=timeout, env=env)
    except (OSError, subprocess.TimeoutExpired):
        raise Blocked('command interrupted; inspect the journal and provider state before retrying')


def read_json(argv: list[str], cwd: Path, account=''):
    result = capture(argv, cwd, account=account)
    if result.returncode:
        raise Blocked('read-only provider query failed; credentials and raw diagnostics were not printed')
    try:
        return json.loads(result.stdout)
    except ValueError:
        raise Blocked('provider query did not return valid JSON')


def substitute(argv: list[str], journal: Journal) -> list[str]:
    values = {'{sha}': journal.data['sha'], '{run_id}': journal.data['run_id'],
              '{version}': journal.data.get('version_id', '')}
    for key, value in values.items():
        argv = [a.replace(key, value) for a in argv]
    return argv


def run_checks(checkout: Path, rows: list[dict], journal=None, phase='checks') -> list[dict]:
    # Reuse the timeout/process-group behavior without passing through a shell.
    import shlex
    from ship_checks import execute
    results = []
    for number, row in enumerate(rows):
        cwd = contained(checkout, row['cwd'])
        evidence, error = execute(cwd, [shlex.join(row['argv'])], row['timeout'])
        results.extend(evidence)
        if journal:
            journal.save(**{phase: results})
        if error:
            raise Blocked(f'release check failed at {phase}[{number}]; inspect its argv directly, then resume local validation')
    return results


def artifact_digests(checkout: Path, names: list[str]) -> dict:
    checkout = checkout.resolve()
    digests = {}
    for name in names:
        if (checkout / name).is_symlink():
            raise Blocked('artifact symlinks are not allowed')
        root = contained(checkout, name)
        if not root.exists():
            raise Blocked(f'required artifact is missing: {name}')
        digest = hashlib.sha256()
        paths = sorted(root.rglob('*')) if root.is_dir() else [root]
        for path in paths:
            if path.is_symlink():
                raise Blocked('artifact symlinks are not allowed')
            if path.is_file():
                # Never inspect credential files even if a build copied one.
                from ship import bucket
                relative = str(path.relative_to(checkout))
                if bucket(relative, False, checkout) == 'secret':
                    raise Blocked('artifact contains a protected filename; remove it from build inputs')
                digest.update(relative.encode())
                digest.update(b'\0')
                with path.open('rb') as handle:
                    digest.update(hashlib.file_digest(handle, 'sha256').digest())
        digests[name] = digest.hexdigest()
    return digests


def http_check(url: str, sha: str, version: str = '', contains='', status=200, identity=False) -> dict:
    if not url.startswith(('https://', 'http://localhost:', 'http://127.0.0.1:')):
        raise Blocked('live checks require HTTPS or a local fixture URL')
    try:
        with urllib.request.urlopen(url, timeout=20) as response:
            body = response.read(1024 * 1024).decode('utf-8', errors='replace')
            if response.status != status:
                raise Blocked('live check returned an unexpected status')
        if identity:
            data = json.loads(body)
            if not isinstance(data, dict) or data.get('sha') != sha or (version and data.get('version') != version):
                raise Blocked('live release identity does not match the validated version')
        elif contains.replace('{sha}', sha).replace('{version}', version) not in body:
            raise Blocked('live check did not find the expected behavior marker')
    except (OSError, ValueError):
        raise Blocked('live release verification failed; inspect read-only provider state')
    return {'url': url, 'status': status, 'identity': identity, 'passed': True}


def watch_ci(repo: Path, config: dict, journal: Journal) -> list[dict]:
    deadline = time.monotonic() + config.get('timeout', 1800)
    results = []
    for workflow in config['workflows']:
        while True:
            argv = ['gh', 'run', 'list', '--commit', journal.data['sha'], '--workflow', workflow,
                    '--branch', config.get('branch', journal.data['main']),
                    '--event', config.get('event', 'push'), '--limit', '100',
                    '--json', 'databaseId,headSha,status,conclusion,attempt,url,workflowName']
            runs = read_json(argv, repo)
            if not isinstance(runs, list):
                raise Blocked('CI returned an unexpected run list')
            if any(not isinstance(r, dict) or not all(k in r for k in ('databaseId', 'headSha', 'status')) for r in runs):
                raise Blocked('CI run identity or status is malformed')
            matching = [r for r in runs if r.get('headSha') == journal.data['sha']]
            if matching:
                selected = max(matching, key=lambda r: (r['databaseId'], r.get('attempt', 1)))
                journal.save(ci={**journal.data.get('ci', {}), workflow: selected})
                if selected['status'] == 'completed':
                    if selected['conclusion'] != 'success':
                        raise Blocked('required CI workflow did not succeed; do not start a duplicate manual deploy')
                    results.append(selected)
                    break
                if selected['status'] in ('waiting', 'action_required'):
                    raise Blocked('CI requires an owner action; no duplicate deployment started')
            if time.monotonic() >= deadline:
                raise Blocked('CI run missing or unfinished at deadline; resume read-only monitoring later')
            time.sleep(min(5, max(0, deadline - time.monotonic())))
    return results


def external(name: str, argv: list[str], cwd: Path, journal: Journal, timeout=1800, account=''):
    if not journal.intent(name):
        return
    result = capture(substitute(argv, journal), cwd, timeout, account)
    if result.returncode:
        raise Blocked(f'{name} did not confirm success; its outcome is uncertain, do not retry')
    journal.done(name)


def cloudflare(checkout: Path, config: dict, profile: dict, journal: Journal):
    cwd = contained(checkout, config.get('cwd', '.'))
    base = config.get('wrangler', ['npx', '--no-install', 'wrangler'])
    flags = ['--name', config['name'], '--env', config['environment'], '--config', config.get('config', 'wrangler.jsonc')]
    account = config['account']
    def versions():
        rows = read_json([*base, 'versions', 'list', *flags, '--json'], cwd, account)
        if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
            raise Blocked('unexpected Cloudflare version list')
        return [r for r in rows if r.get('annotations', {}).get('workers/tag') == journal.data['run_id']]
    def active():
        rows = read_json([*base, 'deployments', 'list', *flags, '--json'], cwd, account)
        if not isinstance(rows, list) or not rows or any(not isinstance(r, dict) for r in rows):
            raise Blocked('cannot confirm the active Cloudflare deployment')
        return max(rows, key=lambda r: r.get('created_on', ''))
    if not journal.data.get('previous_deployment'):
        previous = active()
        journal.save(previous_deployment={'id': previous.get('id'), 'versions': previous.get('versions', [])})
    operations = journal.data.get('operations', {})
    if operations.get('upload', {}).get('status') == 'uncertain':
        matches = versions()
        if len(matches) != 1:
            raise Blocked('upload outcome remains uncertain; no upload repeated')
        journal.save(version_id=matches[0]['id'])
        journal.done('upload', version=matches[0]['id'])
    elif operations.get('upload', {}).get('status') != 'done':
        external('upload', [*base, 'versions', 'upload', *flags, '--no-bundle',
                           '--tag', '{run_id}', '--message', '{sha}'], cwd, journal,
                 config.get('timeout', 1800), account)
        matches = versions()
        if len(matches) != 1:
            raise Blocked('uploaded version identity is not uniquely confirmed')
        journal.save(version_id=matches[0]['id'])
    if not journal.data.get('version_id'):
        matches = versions()
        if len(matches) != 1:
            raise Blocked('cannot reconcile uploaded version identity')
        journal.save(version_id=matches[0]['id'])
    if artifact_digests(checkout, profile.get('artifacts', [])) != journal.data['artifacts']:
        raise Blocked('artifacts changed during upload; do not promote unvalidated output')
    version = journal.data['version_id']
    probe = read_json(substitute(config['probe'], journal), cwd)
    if not isinstance(probe, dict) or probe.get('sha') != journal.data['sha'] or probe.get('version') != version or probe.get('verified') is not True:
        raise Blocked('uploaded-version smoke probe did not verify the validated commit and version; no promotion started')
    journal.save(version_probe={'sha': probe['sha'], 'version': version, 'verified': True})
    current = active()
    journal.save(active_deployment={'id': current.get('id'), 'versions': current.get('versions', [])})
    matches = any(v.get('version_id') == version and v.get('percentage') == 100 for v in current.get('versions', []))
    if matches:
        journal.done('promote', version=version, deployment=current.get('id'))
    else:
        external('promote', [*base, 'versions', 'deploy', version + '@100%', *flags, '--yes'],
                 cwd, journal, config.get('timeout', 1800), account)
        current = active()
        if not any(v.get('version_id') == version and v.get('percentage') == 100 for v in current.get('versions', [])):
            raise Blocked('Cloudflare active version does not match the promoted version')
        journal.save(active_deployment={'id': current.get('id'), 'versions': current.get('versions', [])})
    # Identity probes are read-only. They do not replace a user-flow browser check.
    journal.save(live_identity=http_check(config['identity_url'], journal.data['sha'], version, identity=True))


def finish(checkout: Path, profile: dict, journal: Journal):
    config = profile['deploy']
    mode = config['mode']
    if mode == 'ci':
        journal.save(ci_results=watch_ci(checkout, config, journal))
    elif mode == 'cloudflare':
        cloudflare(checkout, config, profile, journal)
    elif mode == 'command':
        cwd = contained(checkout, config.get('cwd', '.'))
        state = journal.data.get('operations', {}).get('deploy', {})
        if state.get('status') == 'uncertain':
            evidence = read_json(substitute(config['verify'], journal), cwd)
            if not isinstance(evidence, dict) or evidence.get('sha') != journal.data['sha'] or evidence.get('deployed') is not True:
                raise Blocked('deploy outcome remains uncertain; no command repeated')
            journal.done('deploy', sha=evidence['sha'])
        else:
            external('deploy', config['argv'], cwd, journal, config.get('timeout', 1800))
        evidence = read_json(substitute(config['verify'], journal), cwd)
        if not isinstance(evidence, dict) or evidence.get('sha') != journal.data['sha'] or evidence.get('deployed') is not True:
            raise Blocked('deployment did not verify the expected commit')
        journal.save(deploy_verified=True)
    results = [http_check(row['url'], journal.data['sha'], journal.data.get('version_id', ''),
                          row.get('contains', ''), row.get('status', 200)) for row in profile.get('smoke', [])]
    for number, row in enumerate(profile.get('publish', [])):
        name = f'publish-{number}'
        cwd = contained(checkout, row['cwd'])
        uncertain = journal.data.get('operations', {}).get(name, {}).get('status') == 'uncertain'
        if uncertain and row.get('verify'):
            evidence = read_json(substitute(row['verify'], journal), cwd)
            if not isinstance(evidence, dict) or evidence.get('sha') != journal.data['sha'] or evidence.get('published') is not True:
                raise Blocked('publish outcome remains uncertain; no publication repeated')
            journal.done(name, sha=evidence['sha'], verified=True)
        else:
            external(name, row['argv'], cwd, journal, row['timeout'])
        if row.get('verify'):
            evidence = read_json(substitute(row['verify'], journal), cwd)
            if not isinstance(evidence, dict) or evidence.get('sha') != journal.data['sha'] or evidence.get('published') is not True:
                raise Blocked('published artifact identity did not verify')
    journal.save(smoke_results=results, deploy_mode=mode, phase='released',
                 browser_verification='required' if mode != 'none' else 'not_applicable')


def verify_completed(checkout: Path, profile: dict, journal: Journal):
    """An unchanged completed release is checked read-only, never republished."""
    config = profile['deploy']
    if config['mode'] == 'cloudflare':
        http_check(config['identity_url'], journal.data['sha'], journal.data['version_id'], identity=True)
    elif config['mode'] == 'command':
        evidence = read_json(substitute(config['verify'], journal), contained(checkout, config.get('cwd', '.')))
        if not isinstance(evidence, dict) or evidence.get('sha') != journal.data['sha'] or evidence.get('deployed') is not True:
            raise Blocked('completed deployment no longer matches; investigate before starting a corrective release')
    elif config['mode'] == 'ci':
        watch_ci(checkout, config, journal)
    for row in profile.get('publish', []):
        if row.get('verify'):
            evidence = read_json(substitute(row['verify'], journal), contained(checkout, row['cwd']))
            if not isinstance(evidence, dict) or evidence.get('sha') != journal.data['sha'] or evidence.get('published') is not True:
                raise Blocked('completed publication no longer verifies; no publish repeated')
    for row in profile.get('smoke', []):
        http_check(row['url'], journal.data['sha'], journal.data.get('version_id', ''), row.get('contains', ''), row.get('status', 200))
