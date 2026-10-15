"""Check bounded Ego health failures without opening a real browser."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('ego_health', Path(__file__).with_name('ego-health-check.py'))
health = importlib.util.module_from_spec(spec)
spec.loader.exec_module(health)


class EgoHealthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        cli = self.home / '.local/bin/ego-browser'
        cli.parent.mkdir(parents=True)
        cli.write_text('#!/bin/sh\n')
        cli.chmod(0o755)
        self.home_patch = patch.object(health.Path, 'home', return_value=self.home)
        self.home_patch.start()
        self.addCleanup(self.home_patch.stop)

    def test_timeout_does_not_retry_or_restart_browser(self):
        with patch.object(health.subprocess, 'run', side_effect=subprocess.TimeoutExpired('ego-browser', 25)) as run:
            self.assertEqual(health.main(), 1)
        run.assert_called_once()
        self.assertEqual(run.call_args.kwargs['timeout'], 25)
        self.assertNotIn('restart', run.call_args.args[0])

    def test_runtime_failure_is_returned_without_retry(self):
        with patch.object(health.subprocess, 'run', return_value=subprocess.CompletedProcess([], 4)) as run:
            self.assertEqual(health.main(), 4)
        run.assert_called_once()

    def test_success_without_screenshot_fails_validation(self):
        with patch.object(health.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)):
            self.assertEqual(health.main(), 1)

    def test_missing_cli_does_not_start_browser(self):
        (self.home / '.local/bin/ego-browser').unlink()
        with patch.object(health.subprocess, 'run') as run:
            self.assertEqual(health.main(), 1)
        run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
