"""Reading trigger emails out of the inbox over IMAP.

Gmail's own unread flag is the record of what has already been handled, so
there is no local state to keep in sync. A message is marked read only after
its round has been dealt with.
"""

from __future__ import annotations

import email
import imaplib
from contextlib import contextmanager
from dataclasses import dataclass
from email.header import decode_header, make_header
from email.message import Message
from email.utils import getaddresses

from .config import Config
from .delivery import OWN_MAIL_HEADER

# Gmail rejects an unqualified fetch of a huge mailbox; we only ever want new mail.
UNSEEN = "(UNSEEN)"


@dataclass(frozen=True)
class Envelope:
    uid: str
    sender: str
    recipients: list[str]
    subject: str
    in_reply_to: str
    references: str
    auto_submitted: str
    precedence: str
    own_mail: str
    body: str


def _text(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value))).strip()
    except Exception:
        return value.strip()


def _addresses(message: Message, *fields: str) -> list[str]:
    raw = []
    for field in fields:
        raw.extend(message.get_all(field, []))
    return [address.lower() for _, address in getaddresses(raw) if address]


def _plain_body(message: Message) -> str:
    """First text/plain part, ignoring attachments. Empty string if there is none."""
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() != "text/plain":
                continue
            if "attachment" in (part.get("Content-Disposition") or ""):
                continue
            payload = part.get_payload(decode=True)
            if payload:
                return payload.decode(part.get_content_charset() or "utf-8", "replace")
        return ""

    payload = message.get_payload(decode=True)
    if not payload:
        return ""
    return payload.decode(message.get_content_charset() or "utf-8", "replace")


@contextmanager
def connect(config: Config):
    client = imaplib.IMAP4_SSL(config.imap_host)
    try:
        client.login(config.smtp_user, config.smtp_password)
        client.select("INBOX")
        yield client
    finally:
        try:
            client.close()
        except Exception:
            pass
        try:
            client.logout()
        except Exception:
            pass


def unread(client) -> list[Envelope]:
    status, data = client.search(None, UNSEEN)
    if status != "OK" or not data or not data[0]:
        return []

    envelopes = []
    for uid in data[0].split():
        # BODY.PEEK leaves the message unread, so a crash mid-round does not
        # silently swallow the trigger — it gets retried on the next poll.
        status, payload = client.fetch(uid, "(BODY.PEEK[])")
        if status != "OK" or not payload or not isinstance(payload[0], tuple):
            continue

        message = email.message_from_bytes(payload[0][1])
        senders = _addresses(message, "From")
        envelopes.append(
            Envelope(
                uid=uid.decode(),
                sender=senders[0] if senders else "",
                recipients=_addresses(message, "To", "Cc", "Delivered-To", "X-Original-To"),
                subject=_text(message.get("Subject")),
                in_reply_to=_text(message.get("In-Reply-To")),
                references=_text(message.get("References")),
                auto_submitted=_text(message.get("Auto-Submitted")),
                precedence=_text(message.get("Precedence")),
                own_mail=_text(message.get(OWN_MAIL_HEADER)),
                body=_plain_body(message),
            )
        )
    return envelopes


def mark_read(client, uid: str) -> None:
    client.store(uid, "+FLAGS", "\\Seen")
