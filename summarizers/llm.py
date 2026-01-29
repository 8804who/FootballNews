from langchain_openai import ChatOpenAI
from config import API_KEY, PROMPT

class LLMSummarizer:
    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-5-mini", temperature=0, api_key=API_KEY["OPENAI"])


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
        system_prompt = self.generate_prompt("system_prompt")
        prompt = self.generate_prompt("matches_report", matches_data)
        return self.llm.invoke(system_prompt + prompt)


    def generate_transfers_report(self, transfers_data: str) -> str:
        system_prompt = self.generate_prompt("system_prompt")
        prompt = self.generate_prompt("transfers_report", transfers_data)
        return self.llm.invoke(system_prompt + prompt)


    def generate_football_term_decoder(self, term: str) -> str:
        system_prompt = self.generate_prompt("system_prompt")
        prompt = self.generate_prompt("football_term_decoder", term)
        return self.llm.invoke(system_prompt + prompt)


    def generate_newsletter(self, matches_data: str, transfers_data: str) -> str:
        matches_report = self.generate_matches_report(matches_data)
        transfers_report = self.generate_transfers_report(transfers_data)
        football_term_decoder = self.generate_football_term_decoder(matches_data + transfers_data)
        return "\n".join([matches_report.content, transfers_report.content, football_term_decoder.content])
        

llmSummarizer = LLMSummarizer()