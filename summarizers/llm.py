from langchain_openai import ChatOpenAI
from langchain_core.prompts import FewShotPromptTemplate, PromptTemplate

from config import API_KEY, PROMPT, MODEL

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
        example = PROMPT[example_name]
        return example


    def generate_matches_report(self, matches_data: str) -> str:
        if not matches_data:
            return None
        system_prompt = self.generate_prompt("system_prompt")
        
        # Few-shot 예제 정의
        examples = [
            self.generate_example("matches_report_example1"),
            self.generate_example("matches_report_example2"),
        ]
        
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


    def generate_transfers_report(self, transfers_data: str) -> str:
        if not transfers_data:
            return None
        system_prompt = self.generate_prompt("system_prompt")
        prompt = self.generate_prompt("transfers_report", transfers_data)
        return self.llm.invoke(system_prompt + prompt)


    def generate_football_term_decoder(self, news_data: str) -> str:
        if not news_data or news_data == "":
            return None
        system_prompt = self.generate_prompt("system_prompt")
        prompt = self.generate_prompt("football_term_decoder", news_data)
        return self.llm.invoke(system_prompt + prompt)


    def generate_newsletter(self, matches_data: str, transfers_data: str) -> str:
        matches_report = self.generate_matches_report(matches_data)
        transfers_report = self.generate_transfers_report(transfers_data)
        football_term_decoder = self.generate_football_term_decoder(matches_data if matches_data else "" + transfers_data if transfers_data else "")

        matches_report_content = matches_report.content if matches_report else "한 주간 진행된 경기가 없었네요."
        transfers_report_content = transfers_report.content if transfers_report else "한 주간 아무런 이적 소식이 없었네요."
        football_term_decoder_content = football_term_decoder.content if football_term_decoder else "한 주간 아무런 소식이 없었네요."

        return "\n".join([matches_report_content, transfers_report_content, football_term_decoder_content])
        

llmSummarizer = LLMSummarizer()