"""Regression checks for instruction override persistence and conflict safety."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "instruction_overrides", Path(__file__).with_name("apply-instruction-overrides.py")
)
overrides = importlib.util.module_from_spec(spec)
spec.loader.exec_module(overrides)


class OverrideTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "skills"
        self.root.mkdir()
        self.manifest = Path(self.temp.name) / "edits.json"

    def prepare(self, edits):
        self.manifest.write_text(json.dumps({"version": 1, "edits": edits}))

    def test_restore_and_repeat(self):
        path = self.root / "SKILL.md"
        path.write_text("Before\n")
        self.prepare([{"path": "SKILL.md", "hunks": [{"before": "Before\n", "after": "After\n"}]}])
        self.assertEqual(overrides.apply(self.root, self.manifest, check=True), ["SKILL.md"])
        self.assertEqual(path.read_text(), "Before\n")
        overrides.apply(self.root, self.manifest)
        self.assertEqual(path.read_text(), "After\n")
        self.assertEqual(overrides.apply(self.root, self.manifest), [])

    def test_conflict_does_not_partially_write(self):
        first = self.root / "one.md"
        second = self.root / "two.md"
        first.write_text("Before\n")
        second.write_text("Upstream changed\n")
        self.prepare([{"path": name, "hunks": [{"before": "Before\n", "after": "After\n"}]} for name in ["one.md", "two.md"]])
        with self.assertRaises(ValueError):
            overrides.apply(self.root, self.manifest)
        self.assertEqual(first.read_text(), "Before\n")
        self.assertEqual(second.read_text(), "Upstream changed\n")

    def test_rejects_path_escape(self):
        self.prepare([{"path": "../outside.md", "hunks": []}])
        with self.assertRaises(ValueError):
            overrides.apply(self.root, self.manifest)

    def test_rejects_symlink_into_app_bundle(self):
        outside = Path(self.temp.name) / "app.md"
        outside.write_text("Before\n")
        (self.root / "SKILL.md").symlink_to(outside)
        self.prepare([{"path": "SKILL.md", "hunks": [{"before": "Before\n", "after": "After\n"}]}])
        with self.assertRaises(ValueError):
            overrides.apply(self.root, self.manifest)
        self.assertEqual(outside.read_text(), "Before\n")


if __name__ == "__main__":
    unittest.main()
