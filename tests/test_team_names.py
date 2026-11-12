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

    def test_european_clubs_resolve_from_fotmob_and_headline_spellings(self):
        self.assertEqual(canonical("PSG"), "Paris Saint-Germain")
        self.assertEqual(canonical("Paris Saint-Germain"), "Paris Saint-Germain")
        self.assertEqual(canonical("Bayern München"), "Bayern Munich")
        self.assertEqual(canonical("Atlético Madrid"), "Atletico Madrid")
        self.assertEqual(canonical("Atleti"), "Atletico Madrid")
        self.assertEqual(canonical("Barça"), "Barcelona")
        self.assertEqual(canonical("레알 마드리드"), "Real Madrid")

    def test_other_clubs_are_not_ours(self):
        self.assertIsNone(canonical("Leeds United"))
        self.assertIsNone(canonical(""))
        # "FC" is ignored when matching, so PSG must never have a bare "Paris" alias.
        self.assertIsNone(canonical("Paris FC"))
        self.assertIsNone(canonical("Real Betis"))
        self.assertIsNone(canonical("Borussia Dortmund"))


class NormalizeTest(unittest.TestCase):
    def test_accents_spaces_and_fc_are_ignored(self):
        self.assertEqual(normalize("Bayern München"), "bayernmunchen")
        self.assertEqual(normalize("Atlético Madrid"), normalize("Atletico Madrid"))

    def test_distinctive_words_skip_generic_ones(self):
        self.assertEqual(distinctive_words("Nottm Forest"), {"nottm", "forest"})
        self.assertEqual(distinctive_words("Leeds United"), {"leeds"})


if __name__ == "__main__":
    unittest.main()
