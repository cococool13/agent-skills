"""Reviewed release profiles, repository lock, and atomic recovery journal."""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import tomllib


class Blocked(RuntimeError):
    pass


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True)
    if result.returncode:
        raise Blocked('cannot resolve repository metadata')
    return result.stdout.strip()


def state_dir(repo: Path) -> Path:
    common = Path(git(repo, 'rev-parse', '--git-common-dir'))
    common = common if common.is_absolute() else repo / common
    return common.resolve() / 'ship'


@contextmanager
def locked(repo: Path):
    directory = state_dir(repo)
    if directory.is_symlink():
        raise Blocked('ship state directory must not be a symlink')
    directory.mkdir(mode=0o700, exist_ok=True)
    os.chmod(directory, 0o700)
    fd = os.open(directory / 'release.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Blocked('another ship is running for this repository; leave its work intact')
        yield directory
    finally:
        os.close(fd)


def contained(root: Path, value: str) -> Path:
    if not isinstance(value, str) or Path(value).is_absolute():
        raise Blocked('profile paths must be relative to the release checkout')
    target = (root / value).resolve()
    if not target.is_relative_to(root.resolve()):
        raise Blocked('profile path escapes the release checkout')
    return target


def commands(value: object, publishing=False) -> list[dict]:
    if not isinstance(value, list):
        raise Blocked('commands must be arrays of tables')
    result = []
    for row in value:
        allowed = {'argv', 'cwd', 'timeout'} | ({'verify'} if publishing else set())
        if not isinstance(row, dict) or set(row) - allowed:
            raise Blocked('command accepts only argv, cwd, timeout')
        argv, cwd, timeout = row.get('argv'), row.get('cwd', '.'), row.get('timeout', 900)
        if not isinstance(argv, list) or not argv or any(not isinstance(a, str) or '\0' in a for a in argv):
            raise Blocked('command argv must be a nonempty array of strings')
        if any(a in ('--submit', 'review-send') for a in argv):
            raise Blocked('App Review submission requires a separate explicit instruction')
        from ship import SECRET_RE, EXAMPLE_ENV_RE
        if any(SECRET_RE.search(a) and not EXAMPLE_ENV_RE.search(a) for a in argv):
            raise Blocked('release commands must not name protected files or credentials')
        if type(timeout) is not int or not 1 <= timeout <= 86400:
            raise Blocked('command timeout must be 1..86400 seconds')
        contained(Path('/release'), cwd)
        item = dict(argv=argv, cwd=cwd, timeout=timeout)
        if publishing and 'verify' in row:
            commands([{'argv': row['verify']}])
            item['verify'] = row['verify']
        result.append(item)
    return result


def load_profile(repo: Path, filename: str = '') -> dict:
    path = Path(filename).absolute() if filename else repo / 'ship.toml'
    if not filename and not path.exists():
        path = state_dir(repo) / 'profile.toml'
    if path.name not in ('ship.toml', 'profile.toml'):
        raise Blocked('use ship.toml or the Git ship/profile.toml; never load credential or environment files')
    if not path.exists():
        return {}
    if path.is_symlink() or not (path.resolve().is_relative_to(repo.resolve())
                                or path.resolve().is_relative_to(state_dir(repo))):
        raise Blocked('release profile must be a regular file in this repository or its ship state directory')
    try:
        raw = path.read_bytes()
        profile = tomllib.loads(raw.decode())
    except (OSError, ValueError):
        raise Blocked('cannot parse ship.toml')
    if set(profile) - {'version', 'main', 'remote', 'integration', 'checks', 'prepare', 'deploy', 'publish', 'smoke', 'artifacts'}:
        raise Blocked('unknown ship.toml field; see references/profile.md')
    if profile.get('version', 1) != 1:
        raise Blocked('unsupported profile version')
    if profile.get('integration', 'direct') not in ('direct', 'pr'):
        raise Blocked('integration must be direct or pr')
    for key in ('main', 'remote'):
        if key in profile and (not isinstance(profile[key], str) or not profile[key] or profile[key].startswith('-')):
            raise Blocked(f'invalid {key} in profile')
    for key in ('checks', 'prepare'):
        profile[key] = commands(profile.get(key, []))
    profile['publish'] = commands(profile.get('publish', []), publishing=True)
    artifacts = profile.get('artifacts', [])
    if not isinstance(artifacts, list):
        raise Blocked('artifacts must be an array of relative paths')
    for item in artifacts:
        contained(Path('/release'), item)
    deploy = profile.get('deploy', {'mode': 'none'})
    if not isinstance(deploy, dict) or set(deploy) - {
        'mode', 'argv', 'verify', 'cwd', 'timeout', 'workflows', 'branch', 'event',
        'wrangler', 'name', 'environment', 'config', 'account', 'identity_url', 'probe'}:
        raise Blocked('invalid deploy configuration')
    if deploy.get('mode') not in ('none', 'ci', 'command', 'cloudflare'):
        raise Blocked('deploy.mode must be none, ci, command, or cloudflare')
    timeout = deploy.get('timeout', 1800)
    if type(timeout) is not int or not 1 <= timeout <= 86400:
        raise Blocked('invalid deployment timeout')
    if deploy['mode'] == 'ci':
        if not isinstance(deploy.get('workflows'), list) or not deploy['workflows'] or any(
                not isinstance(w, str) or not w for w in deploy['workflows']):
            raise Blocked('CI mode requires exact workflow names or filenames')
        if any(not isinstance(deploy[k], str) or not deploy[k] for k in ('branch', 'event') if k in deploy):
            raise Blocked('CI branch and event must be nonempty strings')
    if deploy['mode'] == 'command':
        commands([{k: v for k, v in deploy.items() if k in ('argv', 'cwd', 'timeout')}])
        if not isinstance(deploy.get('verify'), list) or not deploy['verify']:
            raise Blocked('command deployment needs a read-only JSON verify command')
        commands([{'argv': deploy['verify']}])
    if deploy['mode'] == 'cloudflare':
        if not all(isinstance(deploy.get(k), str) and deploy[k] for k in ('name', 'environment', 'account', 'identity_url')):
            raise Blocked('Cloudflare requires explicit name, environment, account and identity_url')
        commands([{'argv': deploy.get('wrangler', ['npx', '--no-install', 'wrangler'])}])
        commands([{'argv': deploy.get('probe')}])
        contained(Path('/release'), deploy.get('config', 'wrangler.jsonc'))
    contained(Path('/release'), deploy.get('cwd', '.'))
    smoke = profile.get('smoke', [])
    if not isinstance(smoke, list) or any(not isinstance(s, dict) or set(s) - {'url', 'contains', 'status'}
                                         or not isinstance(s.get('url'), str) for s in smoke):
        raise Blocked('smoke must contain url, optional contains and status')
    if any(not isinstance(s.get('contains', ''), str) or type(s.get('status', 200)) is not int
           or not 100 <= s.get('status', 200) <= 599 for s in smoke):
        raise Blocked('smoke contains must be text and status must be an HTTP status number')
    profile.update(deploy=deploy, digest=hashlib.sha256(raw).hexdigest(), path=str(path))
    return profile


class Journal:
    def __init__(self, repo: Path):
        self.path = state_dir(repo) / 'latest.json'
        self.data = {}

    def read(self) -> dict:
        if self.path.is_symlink():
            raise Blocked('journal must not be a symlink')
        if self.path.exists():
            self.data = json.loads(self.path.read_text())
        return self.data

    def save(self, **updates):
        self.data.update(updates)
        directory = self.path.parent
        directory.mkdir(mode=0o700, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix='.journal-', dir=directory)
        try:
            with os.fdopen(fd, 'w') as handle:
                json.dump(self.data, handle, separators=(',', ':'))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(name, self.path)
        finally:
            Path(name).unlink(missing_ok=True)
        run_id = self.data.get('run_id')
        if run_id:
            if not isinstance(run_id, str) or not re.fullmatch(r'[A-Za-z0-9-]{1,80}', run_id):
                raise Blocked('invalid release run identity')
            runs = directory / 'runs'
            if runs.is_symlink():
                raise Blocked('release history directory must not be a symlink')
            runs.mkdir(mode=0o700, exist_ok=True)
            fd, name = tempfile.mkstemp(prefix='.run-', dir=runs)
            try:
                with os.fdopen(fd, 'w') as handle:
                    json.dump(self.data, handle, separators=(',', ':'))
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(name, runs / (run_id + '.json'))
            finally:
                Path(name).unlink(missing_ok=True)

    def intent(self, name: str):
        operations = self.data.setdefault('operations', {})
        previous = operations.get(name, {})
        if previous.get('status') == 'done':
            return False
        if previous.get('status') == 'uncertain':
            raise Blocked(f'{name} has an uncertain outcome; reconcile read-only before continuing')
        operations[name] = {'status': 'uncertain'}
        self.save()
        return True

    def done(self, name: str, **evidence):
        self.data.setdefault('operations', {})[name] = {'status': 'done', **evidence}
        self.save()
