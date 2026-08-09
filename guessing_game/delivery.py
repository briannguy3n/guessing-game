"""Getting a message to a player.

Every delivery method is a `Notifier`. Email is the only one implemented; a
Twilio SMS notifier would slot in behind the same `send` signature.
"""

from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import Protocol

from .config import Config


class Notifier(Protocol):
    def send(self, to: str, subject: str, body: str) -> None: ...


class EmailNotifier:
    def __init__(self, config: Config) -> None:
        self._config = config

    def send(self, to: str, subject: str, body: str) -> None:
        message = EmailMessage()
        message["From"] = self._config.from_address
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)

        with smtplib.SMTP(self._config.smtp_host, self._config.smtp_port) as server:
            server.starttls()
            server.login(self._config.smtp_user, self._config.smtp_password)
            server.send_message(message)
