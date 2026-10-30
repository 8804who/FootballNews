"""Real past editions the evaluation must keep judging correctly: defects
that reached subscribers, plus one clean edition that must pass. See
evaluate/golden.py for how a case is captured."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evaluate import gate, utils
from evaluate.evaluate_main import evaluate_newsletter

GOLDEN_DIR = Path(__file__).resolve().parent / "golden"


def replay(case: dict):
    """Write a case's files under a temporary datas/ root, then run the
    evaluator and the pre-send gate on its newsletter."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for rel, text in case["files"].items():
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text(text, encoding="utf-8")
        with patch.object(utils, "DATA_ROOT", root), patch.object(utils, "NEWSLETTER_ROOT", root / "newsletter"):
            token = case["team"].replace(" ", "_")
            newsletter = root / "newsletter" / case["date"] / f"newsletter_{token}.md"
            date = utils.parse_date(case["date"])
            clubs = [token] + [club.replace(" ", "_") for club in case.get("also", [])]
            sources = {club: gate.club_sources(club, date) for club in clubs}
            verdict = gate.check_edition(token, date, newsletter.read_text(encoding="utf-8"), sources)
            return evaluate_newsletter(newsletter), verdict


class GoldenCasesTest(unittest.TestCase):
    def test_every_case(self):
        paths = sorted(GOLDEN_DIR.glob("*.json"))
        self.assertTrue(paths, "no golden cases found")
        for path in paths:
            case = json.loads(path.read_text(encoding="utf-8"))
            with self.subTest(case=case["name"]):
                result, verdict = replay(case)
                expect = case["expect"]
                self.assertTrue(expect, "case has no expectations")
                if "flagged" in expect:
                    self.assertEqual(verdict["flagged"], expect["flagged"], verdict["problems"])
                for fragment in expect.get("problems", []):
                    self.assertTrue(any(fragment in p for p in verdict["problems"]), (fragment, verdict["problems"]))
                for fragment in expect.get("warnings", []):
                    self.assertTrue(any(fragment in w for w in verdict["warnings"]), (fragment, verdict["warnings"]))
                for key, bound in expect.get("metric_min", {}).items():
                    self.assertGreaterEqual(result["components"][key], bound, key)
                for key, bound in expect.get("metric_max", {}).items():
                    self.assertLessEqual(result["components"][key], bound, key)
                for fragment in expect.get("facts_failed", []):
                    self.assertTrue(any(fragment in f for f in result["match_facts"]["failed"]),
                                    (fragment, result["match_facts"]["failed"]))


if __name__ == "__main__":
    unittest.main()
