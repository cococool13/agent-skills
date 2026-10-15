"""Exercise real guard executables with fixtures; never read actual secrets."""
import json
import subprocess
import unittest
from pathlib import Path

HOOKS = Path(__file__).parent / 'hooks'


class SharedHookTests(unittest.TestCase):
    def run_hook(self, name, data):
        result = subprocess.run(
            [str(HOOKS / name)], input=json.dumps(data),
            text=True, capture_output=True, check=True,
        )
        return json.loads(result.stdout)

    def decision(self, output):
        return output.get('hookSpecificOutput', {}).get('permissionDecision', output.get('permission', 'allow'))

    def shell(self, command, host='codex'):
        data = {'hook_event_name': 'PreToolUse', 'tool_input': {'command': command}}
        if host == 'codex':
            data['model'] = 'fixture'
        elif host == 'cursor':
            data = {'command': command, 'model': 'fixture', 'cursor_version': 'fixture', 'hook_event_name': 'beforeShellExecution'}
        return self.run_hook('guard-shell.py', data)

    def test_literal_output_does_not_block_examples(self):
        for command in ('echo "wrangler deploy"', 'printf "%s" "cat .env"'):
            with self.subTest(command=command):
                self.assertEqual(self.shell(command), {})

    def test_substitutions_and_compound_commands_remain_guarded(self):
        for command in ('echo "$(cat .env)"', 'echo `cat .env`', 'echo safe; cat .env', 'echo safe && wrangler deploy'):
            with self.subTest(command=command):
                self.assertEqual(self.decision(self.shell(command)), 'deny')

    def test_safe_commands_preserve_native_permissions(self):
        self.assertEqual(self.shell('git status'), {})
        self.assertEqual(self.shell('git status', 'claude'), {})
        self.assertEqual(self.shell('git status', 'cursor'), {'permission': 'allow'})

    def test_risky_commands_use_each_hosts_contract(self):
        for command in ('wrangler deploy', 'git reset --hard'):
            self.assertEqual(self.decision(self.shell(command)), 'deny')
            claude = self.shell(command, 'claude')
            self.assertEqual(self.decision(claude), 'ask')
            self.assertEqual(set(claude), {'hookSpecificOutput'})
            cursor = self.shell(command, 'cursor')
            self.assertEqual(self.decision(cursor), 'ask')
            self.assertNotIn('decision', cursor)
            self.assertNotIn('hookSpecificOutput', cursor)

    def test_shell_guards_supported_secret_files(self):
        for path in ('.env', '.ENV.PRODUCTION', '.env.example.production', '.env.examples', 'secret.key', 'secret.pfx', 'auth.json', 'mcp_credentials.json', '.netrc'):
            with self.subTest(path=path):
                self.assertEqual(self.decision(self.shell('cat ' + path)), 'deny')
        self.assertEqual(self.decision(self.shell('cat .env.example')), 'allow')

    def test_read_case_and_schema(self):
        for path in ('.ENV', 'AUTH.JSON', 'secret.key', 'secret.pfx'):
            for host in ('codex', 'claude', 'cursor'):
                with self.subTest(path=path, host=host):
                    data = {'hook_event_name': 'PreToolUse', 'tool_input': {'file_path': path}}
                    if host == 'codex':
                        data['model'] = 'fixture'
                    elif host == 'cursor':
                        data = {'file_path': path, 'model': 'fixture', 'cursor_version': 'fixture', 'hook_event_name': 'beforeReadFile'}
                    output = self.run_hook('deny-env-read.py', data)
                    self.assertEqual(self.decision(output), 'deny')
                    self.assertNotIn('decision', output)
                    self.assertEqual('permission' in output, host == 'cursor')

    def test_read_examples_and_regular_files_remain_allowed(self):
        for path in ('.env.example', '.env.sample', '.env.template', 'src/app.py'):
            output = self.run_hook('deny-env-read.py', {'hook_event_name': 'PreToolUse', 'model': 'fixture', 'tool_input': {'file_path': path}})
            self.assertEqual(output, {})


if __name__ == '__main__':
    unittest.main()
