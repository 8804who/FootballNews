from abc import ABC, abstractmethod

class EmailSender:
    def __init__(self):
        pass

    @abstractmethod
    def send_email(self, to: str, subject: str, body: str):
        pass