"""Discover check candidates and run reviewed commands without a shell."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import time


def discover(repo: Path) -> list[str]:
    """Candidates only: project instructions decide which checks are required."""
    try:
        package = json.loads((repo / 'package.json').read_text())
        scripts = package.get('scripts', {})
        if not isinstance(scripts, dict):
            return []
    except (OSError, ValueError, AttributeError):
        return []
    manager = next((pm for lock, pm in (
        ('pnpm-lock.yaml', 'pnpm'), ('bun.lock', 'bun'), ('bun.lockb', 'bun'),
        ('yarn.lock', 'yarn'),
    ) if (repo / lock).exists()), 'npm')
    # Pick one spelling per check to avoid running aliases twice.
    groups = [('typecheck', 'type-check', 'check:types'), ('lint',),
              ('format:check', 'check:format'), ('test:ci', 'test'), ('build',)]
    return [f'{manager} run {name}' for group in groups
            if (name := next((n for n in group if n in scripts), ''))]


def execute(repo: Path, commands: list[str], timeout: int) -> tuple[list[dict], str]:
    results = []
    for command in dict.fromkeys(commands):
        started = time.monotonic()
        item = {'command': command}
        try:
            lexer = shlex.shlex(command, posix=True, punctuation_chars=';&|<>()')
            lexer.whitespace_split = True
            lexer.commenters = ''
            argv = list(lexer)
            if not argv or any(a and all(c in ';&|<>()' for c in a) for a in argv):
                raise ValueError('empty check or shell syntax')
            # Output can include sensitive application diagnostics. Return verdicts only.
            with subprocess.Popen(argv, cwd=repo, stdin=subprocess.DEVNULL,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                  start_new_session=True) as process:
                try:
                    code = process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    # Package managers spawn children; stop the whole check group.
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait()
                    raise
            item.update(status='passed' if code == 0 else 'failed', exit_code=code)
        except subprocess.TimeoutExpired:
            item['status'] = 'timed_out'
        except (OSError, ValueError):
            item['status'] = 'could_not_run'
        item['seconds'] = round(time.monotonic() - started, 2)
        results.append(item)
        if item['status'] != 'passed':
            return results, 'check failed; run the reported command directly for diagnostics'
    return results, ''
