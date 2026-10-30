import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from team_names import canonical, distinctive_words, normalize


class CanonicalTest(unittest.TestCase):
    def test_aliases_resolve_to_the_configured_name(self):
        self.assertEqual(canonical("Man Utd"), "Manchester United")
        self.assertEqual(canonical("Man United"), "Manchester United")
        self.assertEqual(canonical("Spurs"), "Tottenham Hotspur")
        self.assertEqual(canonical("토트넘"), "Tottenham Hotspur")
        self.assertEqual(canonical("Arsenal FC"), "Arsenal")

    def test_sign_up_answers_typed_differently_still_match(self):
        # The sign-up sheet really stores "TottenhamHotspur".
        self.assertEqual(canonical("TottenhamHotspur"), "Tottenham Hotspur")
        self.assertEqual(canonical(" manchester city "), "Manchester City")

    def test_other_clubs_are_not_ours(self):
        self.assertIsNone(canonical("Leeds United"))
        self.assertIsNone(canonical(""))


class NormalizeTest(unittest.TestCase):
    def test_accents_spaces_and_fc_are_ignored(self):
        self.assertEqual(normalize("Bayern München"), "bayernmunchen")
        self.assertEqual(normalize("Atlético Madrid"), normalize("Atletico Madrid"))

    def test_distinctive_words_skip_generic_ones(self):
        self.assertEqual(distinctive_words("Nottm Forest"), {"nottm", "forest"})
        self.assertEqual(distinctive_words("Leeds United"), {"leeds"})


if __name__ == "__main__":
    unittest.main()
