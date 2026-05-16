from langchain_openai import ChatOpenAI
from langchain_core.prompts import FewShotPromptTemplate, PromptTemplate

from config import API_KEY, PROMPT, MODEL, EXAMPLE

class LLMSummarizer:
    def __init__(self):
        self.llm = ChatOpenAI(model=MODEL, temperature=0, api_key=API_KEY["OPENAI"])


    def generate_prompt(self, prompt_name: str, data: str = None) -> str:
        prompt = ''
        for key, value in PROMPT[prompt_name].items():
            prompt += f"### {key}\n"
            for item in value:
                prompt += item + "\n"
            prompt += "\n"
        return prompt


    def generate_example(self, example_name: str) -> dict:
        example = EXAMPLE[example_name]
        return example


    def generate_matches_report(self, matches_data: str) -> str:
        if not matches_data:
            return None
        system_prompt = self.generate_prompt("system_prompt")
        
        # Few-shot 예제 정의
        examples = self.generate_example("matches_report")
        
        # 예제 포맷터 생성
        example_prompt = PromptTemplate(
            input_variables=["input", "output"],
            template="Input:\n{input}\n\nOutput:\n{output}\n"
        )
        
        # matches_report 프롬프트에서 Input Data 부분 제외하고 prefix 생성
        matches_prompt_template = self.generate_prompt("matches_report")
        
        # FewShotPromptTemplate 생성
        few_shot_prompt = FewShotPromptTemplate(
            examples=examples,
            example_prompt=example_prompt,
            prefix=matches_prompt_template,
            suffix="Input:\n{input}\n\nOutput:\n",
            input_variables=["input"]
        )
        
        # 최종 프롬프트 생성
        prompt = few_shot_prompt.format(input=matches_data)

        return self.llm.invoke(system_prompt + prompt)


    def generate_transfers_and_news_report(self, transfers_data: str, news_rss_data: str) -> str:
        if not transfers_data and not news_rss_data:
            return None
        system_prompt = self.generate_prompt("system_prompt")

        example = self.generate_example("transfers_and_news_report")

        example_prompt = PromptTemplate(
            input_variables=["input", "output"],
            template="Input:\n{input}\n\nOutput:\n{output}\n"
        )

        prompt_template = self.generate_prompt("transfers_and_news_report")

        few_shot_prompt = FewShotPromptTemplate(
            examples=example,
            example_prompt=example_prompt,
            prefix=prompt_template,
            suffix="Input:\n{input}\n\nOutput:\n",
            input_variables=["input"]
        )

        combined_blocks = []
        combined_blocks.append("### Official Transfers")
        combined_blocks.append(transfers_data if transfers_data else "(none this week)")
        combined_blocks.append("")
        combined_blocks.append("### News & Rumors")
        combined_blocks.append(news_rss_data if news_rss_data else "(none this week)")
        combined_data = "\n".join(combined_blocks)

        prompt = few_shot_prompt.format(input=combined_data)
        return self.llm.invoke(system_prompt + prompt)

    def generate_newsletter(self, matches_data: str, transfers_data: str, news_rss_data: str) -> str:
        matches_report = self.generate_matches_report(matches_data)
        transfers_and_news_report = self.generate_transfers_and_news_report(transfers_data, news_rss_data)

        sections = []
        if matches_report:
            sections.append(matches_report.content.strip())
        if transfers_and_news_report:
            sections.append(transfers_and_news_report.content.strip())

        if not sections:
            # Both data sources were empty this week. Wrap the fallback in a section
            # so it does not render as an orphan line above the masthead.
            return "## 🌙 이번 주 휴식\n\n이번 주는 경기와 이적·뉴스 소식이 모두 조용했습니다. 다음 주에 다시 만나요."

        return "\n\n".join(sections)
        

llmSummarizer = LLMSummarizer()