from langchain_openai import ChatOpenAI
from config import API_KEY, PROMPT, MODEL

class LLMSummarizer:
    def __init__(self):
        self.llm = ChatOpenAI(model=MODEL, temperature=0, api_key=API_KEY["OPENAI"])


    def generate_prompt(self, prompt_name: dict, data: str = None) -> str:
        prompt = ''
        for key, value in PROMPT[prompt_name].items():
            prompt += f"### {key}\n"
            for item in value:
                prompt += item + "\n"
            if key == "Input Data":
                prompt += data + "\n"
            prompt += "\n"
        return prompt


    def generate_matches_report(self, matches_data: str) -> str:
        if not matches_data:
            return None
        system_prompt = self.generate_prompt("system_prompt")
        prompt = self.generate_prompt("matches_report", matches_data)
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