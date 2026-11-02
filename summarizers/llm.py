import time

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

import newsletter_sections as sections
from config import API_KEY, PROMPT, MODEL, EXAMPLE, REASONING_EFFORT
from summarizers.citations import format_news_input, link_citations
from summarizers.tidy import tidy

# The rules, the few-shot examples and the real input used to be one long
# string, and the model regularly answered an example instead of the real
# input — fictional (and before that, real but wrong) example news went out
# to subscribers. Now each example is a labelled past turn and the real input
# is the final message, so there's no doubt which one to answer.
_EXAMPLE_INTRO = "FORMAT EXAMPLE — fictional clubs, players and headlines. Copy the format, never the content.\n\n"
_INPUT_INTRO = "THIS WEEK'S REAL INPUT. Write the section using only the lines below.\n\n"

QUIET_WEEK = f"{sections.QUIET}\n\n이번 주는 경기도, 이적·뉴스 소식도 조용했습니다. 다음 주에 다시 찾아뵙겠습니다."


def usage_record(section: str, model: str, response, seconds: float) -> dict:
    """Tokens and time of one LLM call, as stored in usage.json."""
    usage = getattr(response, "usage_metadata", None) or {}
    return {
        "section": section,
        "model": model,
        "resolved_model": (getattr(response, "response_metadata", None) or {}).get("model_name"),
        "input_tokens": usage.get("input_tokens", 0),
        "cached_input_tokens": (usage.get("input_token_details") or {}).get("cache_read", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "reasoning_tokens": (usage.get("output_token_details") or {}).get("reasoning", 0),
        "seconds": round(seconds, 2),
    }


class LLMSummarizer:
    def __init__(self, model: str = MODEL, prompt: dict = PROMPT, examples: dict = EXAMPLE,
                 reasoning_effort: str = REASONING_EFFORT):
        # Defaults are setting.yml / prompt.yml / example.yml; evaluate/harness.py
        # passes other ones to compare variants. reasoning_effort matters for
        # newer models (gpt-5.4+), which don't reason unless asked.
        self.model = model
        self.prompt = prompt
        self.examples = examples
        extra = {"reasoning_effort": reasoning_effort} if reasoning_effort else {}
        self.llm = ChatOpenAI(model=model, temperature=0, api_key=API_KEY["OPENAI"], **extra)
        # One usage_record() per LLM call, for usage.json and the cost report.
        self.calls = []
        # The last edition's sections as the model wrote them, before tidy(),
        # and what tidy() changed; generate_newsletter.py keeps both.
        self.raw = {}
        self.tidied = {}


    def generate_prompt(self, prompt_name: str, data: str = None) -> str:
        """One '### Key' part per prompt.yml entry. An entry is a block of
        text or a list of lines. (A text entry used to be looped over like a
        list, so until Nov 2026 the system rules reached the model one
        character per line.)"""
        prompt = ''
        for key, value in self.prompt[prompt_name].items():
            prompt += f"### {key}\n"
            if isinstance(value, str):
                prompt += value.rstrip() + "\n"
            else:
                for item in value:
                    prompt += item + "\n"
            prompt += "\n"
        return prompt


    def generate_example(self, example_name: str) -> dict:
        example = self.examples[example_name]
        return example


    def generate_messages(self, prompt_name: str, data: str) -> list:
        """System rules, each few-shot example as a past user/assistant turn,
        then the real input as the final user turn."""
        messages = [SystemMessage(self.generate_prompt("system_prompt") + self.generate_prompt(prompt_name))]
        for example in self.generate_example(prompt_name):
            messages.append(HumanMessage(_EXAMPLE_INTRO + example["input"]))
            messages.append(AIMessage(example["output"]))
        messages.append(HumanMessage(_INPUT_INTRO + data))
        return messages


    def invoke(self, section: str, messages: list) -> str:
        started = time.perf_counter()
        response = self.llm.invoke(messages)
        self.calls.append(usage_record(section, self.model, response, time.perf_counter() - started))
        return response.content.strip()


    def _tidy(self, section: str, text: str) -> str:
        self.raw[section] = text
        text, counts = tidy(text)
        self.tidied[section] = counts
        return text


    def generate_matches_report(self, matches_data: str) -> str:
        if not matches_data:
            return None
        report = self.invoke("matches_report", self.generate_messages("matches_report", matches_data))
        return self._tidy("matches_report", report)


    def generate_transfers_and_news_report(self, transfers_data: str, news_items: list,
                                           shown_separately: list = ()) -> str:
        if not transfers_data and not news_items:
            return None

        combined_blocks = []
        combined_blocks.append("### Official Transfers")
        combined_blocks.append(transfers_data if transfers_data else "(none this week)")
        combined_blocks.append("")
        combined_blocks.append("### News & Rumors")
        combined_blocks.append(format_news_input(news_items) if news_items else "(none this week)")
        if shown_separately:
            # Names only: the injury list is printed by code elsewhere in the
            # email, and the model must not restate or contradict it.
            combined_blocks.append("")
            combined_blocks.append("### Shown separately in this email (never write an item from this list)")
            combined_blocks.append("결장 예상: " + ", ".join(shown_separately))
        combined_data = "\n".join(combined_blocks)

        messages = self.generate_messages("transfers_and_news_report", combined_data)
        report = self.invoke("transfers_and_news_report", messages)

        # Swap the model's [N#] tags for links to the collected stories.
        report, unknown = link_citations(report, news_items)
        if unknown:
            print(f"  ⚠ dropped source tags that match no headline: {', '.join(unknown)}")
        return self._tidy("transfers_and_news_report", report)

    def generate_newsletter(self, matches_data: str, transfers_data: str, news_items: list,
                            data_blocks: str = "", shown_separately: list = ()) -> str:
        """The edition body. `data_blocks` (summarizers/blocks.py) goes after
        the scoreboard, or first when there was no match; a week where the
        model has nothing to write still gets them, under the quiet-week note."""
        self.raw, self.tidied = {}, {}
        matches_report = self.generate_matches_report(matches_data)
        transfers_and_news_report = self.generate_transfers_and_news_report(
            transfers_data, news_items, shown_separately)

        sections_out = []
        if matches_report:
            sections_out.append(matches_report)
        if data_blocks:
            sections_out.append(data_blocks)
        if transfers_and_news_report:
            sections_out.append(transfers_and_news_report)

        if not (matches_report or transfers_and_news_report):
            # Both data sources were empty this week. Wrap the fallback in a section
            # so it does not render as an orphan line above the masthead.
            sections_out.insert(0, QUIET_WEEK)

        return "\n\n".join(sections_out)


llmSummarizer = LLMSummarizer()
