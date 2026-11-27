#!/usr/bin/env python3
"""Run a unittest discover set across processes.

usage: unittest-par.py <start-dir> <pattern> [<pattern>...]

Each test gets its own temp fixtures, so tests are dealt round-robin to one
`python3 -m unittest` process per CPU (capped at the test count). Exit status
is non-zero if any process fails; failing output is printed in full.
"""
import os
import subprocess
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor


def ids(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from ids(test)
        else:
            yield test.id()


def main():
    start, patterns = os.path.abspath(sys.argv[1]), sys.argv[2:]
    sys.path.insert(0, start)
    loader = unittest.TestLoader()
    tests = [t for p in patterns for t in ids(loader.discover(start, pattern=p, top_level_dir=start))]
    broken = [t for t in tests if t.startswith("unittest.loader._FailedTest")]
    if broken or not tests:
        print("unittest-par: discovery failed:", broken or "no tests", file=sys.stderr)
        return 1
    jobs = min(os.cpu_count() or 4, len(tests))
    buckets = [tests[i::jobs] for i in range(jobs)]

    def run(bucket):
        return subprocess.run([sys.executable, "-m", "unittest", "-q", *bucket],
                              cwd=start, capture_output=True, text=True)

    with ThreadPoolExecutor(jobs) as pool:
        results = list(pool.map(run, buckets))
    failed = [r for r in results if r.returncode != 0]
    for r in failed:
        sys.stderr.write(r.stdout + r.stderr)
    print(f"unittest-par: {len(tests)} tests in {jobs} processes, {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
