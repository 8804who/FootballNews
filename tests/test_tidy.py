"""Clean-up of the model's Korean (summarizers/tidy.py, summarizers/korean.py),
the prompt rendering, and the style counter."""

import sys
import unittest
from pathlib import Path

import yaml
from markdown_it import MarkdownIt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evaluate import style
from summarizers.korean import fix_particles
from summarizers.llm import LLMSummarizer
from summarizers.tidy import replace_dashes, tidy, title_breaks

ROOT = Path(__file__).resolve().parent.parent


class DashTest(unittest.TestCase):
    def test_long_dashes_become_commas(self):
        text, n = replace_dashes("두 클럽이 맞붙습니다 — 결과가 궁금합니다.")
        self.assertEqual((text, n), ("두 클럽이 맞붙습니다, 결과가 궁금합니다.", 1))

    def test_score_hyphens_and_en_dashes_are_scores(self):
        text, n = replace_dashes("| Arsenal vs Lille | 3 - 0 | 2–1로 이겼습니다 |")
        self.assertEqual((text, n), ("| Arsenal vs Lille | 3 - 0 | 2-1로 이겼습니다 |", 0))


class TitleBreakTest(unittest.TestCase):
    def html(self, text):
        return MarkdownIt("commonmark").enable("table").render(text)

    def test_title_and_body_render_on_separate_lines(self):
        for item in ("- **Sample 영입전** (보도) — 두 클럽이 맞붙었습니다. [N1]",
                     "- **Sample 영입전** (보도)\n두 클럽이 맞붙었습니다. [N1]",
                     "- **Sample 영입전** (보도)\n\n  두 클럽이 맞붙었습니다. [N1]"):
            html = self.html(title_breaks(item))
            self.assertIn("(보도)<br />", html, item)
            self.assertEqual(html.count("<li>"), 1, item)

    def test_other_lines_are_left_alone(self):
        text = "- **제목** (보도)\n- **다음 제목** (가십)  \n  본문 [N2]"
        self.assertTrue(title_breaks(text).startswith("- **제목** (보도)\n- **다음 제목**"))


class ParticleTest(unittest.TestCase):
    def test_particles_follow_the_korean_reading(self):
        self.assertEqual(fix_particles("Newcastle와 비겼습니다")[0], "Newcastle과 비겼습니다")
        self.assertEqual(fix_particles("Arsenal으로 이적")[0], "Arsenal로 이적")      # ㄹ takes 로
        self.assertEqual(fix_particles("Hoffenheim로 이적")[0], "Hoffenheim으로 이적")
        self.assertEqual(fix_particles("Man City을 꺾고")[0], "Man City를 꺾고")
        self.assertEqual(fix_particles("Bayern München와의 경기")[0], "Bayern München과의 경기")

    def test_compound_endings_and_unknown_clubs_are_left_alone(self):
        for text in ("Arsenal이라는 팀", "Sample Town와 비김", "Liverpool을 꺾고"):
            self.assertEqual(fix_particles(text), (text, 0))

    def test_tidy_counts_what_it_changed(self):
        _, counts = tidy("- **제목** (보도) — Newcastle와 비겼습니다 — 아쉽습니다. [N1]")
        self.assertEqual(counts, {"dashes": 1, "particles": 1})


class PromptTest(unittest.TestCase):
    def test_prompt_and_examples_have_no_long_dash_or_arrow(self):
        # The prompt teaches by example: a dash in it reappears in the output.
        for name in ("prompt.yml", "example.yml"):
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertNotRegex(text, "[—―→]", name)

    def test_text_entries_reach_the_model_as_text(self):
        # Until Nov 2026 a text entry was looped over like a list, and the
        # system rules reached the model one character per line.
        summarizer = LLMSummarizer.__new__(LLMSummarizer)
        summarizer.prompt = yaml.safe_load((ROOT / "prompt.yml").read_text(encoding="utf-8"))
        rendered = summarizer.generate_prompt("system_prompt")
        self.assertIn("Write 합쇼체", rendered)
        self.assertLess(rendered.count("\n") * 20, len(rendered))


class StyleTest(unittest.TestCase):
    def test_banned_held_out_and_monotone_endings(self):
        text = ("## 🏆 이번 주 헤드라인\n**Saka의 결승골**\n\n## ⭐ 이번 주 베스트 경기\n"
                "골망을 흔들었습니다 — 분위기를 바꿨습니다. 한편 인상적인 경기였습니다. 막아냈습니다. 지켜냈습니다. 끝냈습니다.\n"
                "\n## 📍 현재 순위\n\n**1위 · 8경기 승점 24**\n분위기를 분위기를\n")
        result = style.evaluate(text)
        self.assertEqual(result["dashes"], 1)
        self.assertEqual(result["banned"], 2)       # the dash and one 분위기를; the code block is ignored
        self.assertEqual(result["held_out"], 2)     # 한편, 인상적
        self.assertEqual(result["headline_chars"], 9)
        self.assertGreaterEqual(result["monotone_runs"], 1)


if __name__ == "__main__":
    unittest.main()
