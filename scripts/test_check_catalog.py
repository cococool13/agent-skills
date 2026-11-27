import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_catalog as cc  # noqa: E402

REPO = Path(__file__).resolve().parent.parent

GOOD = """---
name: demo
description: "Use when testing."
when: "Testing the catalog check"
category: code
level: beginner
setup: "5 min; an API key"
---
# Demo
"""

TP_GOOD = """# comment
skills:
  - name: "alpha"
    purpose: "Does alpha."
    author: "someone"
    source: "https://github.com/someone/alpha"
  - name: "beta"
    purpose: "Does beta."
    source: "unknown"
"""


class SkillFields(unittest.TestCase):
    def test_good_skill_passes(self):
        self.assertEqual(cc.check_skill("demo", GOOD), [])

    def test_each_missing_field_fails(self):
        for key in cc.FIELDS:
            text = "\n".join(l for l in GOOD.splitlines() if not l.startswith(f"{key}:")) + "\n"
            problems = cc.check_skill("demo", text)
            self.assertIn(f"demo: missing `{key}`", problems)

    def test_category_outside_set_fails(self):
        problems = cc.check_skill("demo", GOOD.replace("category: code", "category: marketing"))
        self.assertTrue(any("category `marketing`" in p for p in problems))

    def test_bad_level_fails(self):
        problems = cc.check_skill("demo", GOOD.replace("level: beginner", "level: expert"))
        self.assertTrue(any("level `expert`" in p for p in problems))

    def test_bad_setup_fails(self):
        for bad in ('"about 5 minutes"', '"0 min"', '"none;"', '"5 mins"'):
            problems = cc.check_skill("demo", GOOD.replace('"5 min; an API key"', bad))
            self.assertTrue(any("setup" in p for p in problems), bad)

    def test_setup_none_passes(self):
        self.assertEqual(cc.check_skill("demo", GOOD.replace('"5 min; an API key"', "none")), [])

    def test_when_with_period_or_too_long_fails(self):
        self.assertTrue(cc.check_skill("demo", GOOD.replace("Testing the catalog check", "Testing.")))
        self.assertTrue(cc.check_skill("demo", GOOD.replace("Testing the catalog check", "x" * 91)))

    def test_missing_frontmatter_fails(self):
        self.assertEqual(cc.check_skill("demo", "# no frontmatter\n"), ["demo: missing frontmatter"])

    def test_skill_folder_without_fields_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "bare"
            d.mkdir()
            (d / "SKILL.md").write_text('---\nname: bare\ndescription: "Use when."\n---\n')
            self.assertEqual(len(cc.check_skills(Path(tmp))), 4)


class ThirdParty(unittest.TestCase):
    def test_good_file_passes(self):
        self.assertEqual(cc.check_third_party(TP_GOOD, set()), [])
        self.assertEqual(len(cc.parse_third_party(TP_GOOD)), 2)

    def test_missing_required_key_fails(self):
        text = TP_GOOD.replace('    source: "unknown"\n', "")
        self.assertIn("third-party.yaml: beta: missing `source`", cc.check_third_party(text, set()))

    def test_unknown_key_fails(self):
        text = TP_GOOD + '    license: "MIT"\n'
        self.assertIn("third-party.yaml: beta: unknown key `license`", cc.check_third_party(text, set()))

    def test_non_https_source_fails(self):
        text = TP_GOOD.replace('"unknown"', '"github.com/x/y"')
        self.assertTrue(any("https URL" in p for p in cc.check_third_party(text, set())))

    def test_duplicate_and_own_skill_fail(self):
        text = TP_GOOD.replace('"beta"', '"alpha"')
        self.assertTrue(any("duplicate name" in p for p in cc.check_third_party(text, set())))
        self.assertTrue(any("in this repo" in p for p in cc.check_third_party(TP_GOOD, {"alpha"})))

    def test_personal_data_fails(self):
        text = TP_GOOD.replace("Does beta.", "Reads ~/Projects/x")
        self.assertTrue(any("personal" in p for p in cc.check_third_party(text, set())))

    def test_malformed_shape_fails(self):
        self.assertTrue(cc.check_third_party("- name: x\n", set()))
        self.assertTrue(cc.check_third_party("skills:\n  name: x\n", set()))
        self.assertTrue(cc.check_third_party("skills:\n", set()))


class Repo(unittest.TestCase):
    def test_repo_catalog_is_valid(self):
        problems = cc.check_skills(REPO / "skills")
        own = {p.name for p in (REPO / "skills").iterdir() if p.is_dir()}
        problems += cc.check_third_party((REPO / "catalog" / "third-party.yaml").read_text(), own)
        self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()
