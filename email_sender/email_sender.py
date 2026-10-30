from abc import ABC, abstractmethod

class EmailSender(ABC):
    @abstractmethod
    def send_email(self, to: str, subject: str, body: str, footer: str = None, headers: dict = None):
        """Send `body` (markdown). `footer` (markdown) is shown small below it;
        `headers` are extra MIME headers, e.g. List-Unsubscribe."""
