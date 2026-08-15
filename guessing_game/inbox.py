"""Reading trigger emails out of the inbox over IMAP.

This never modifies the mailbox. It reads a recent window of mail and leaves
every flag alone — the caller remembers which message ids it has handled.

Using the unread flag for that would be wrong twice over: opening your own
trigger email in Gmail would hide it from the poller, and unrelated mail would
get marked read just for being looked at.
"""

from __future__ import annotations

import email
import imaplib
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.header import decode_header, make_header
from email.message import Message
from email.utils import getaddresses

from .config import Config
from .delivery import OWN_MAIL_HEADER

# How far back each poll looks. Anything older is assumed dead.
LOOKBACK_DAYS = 2


@dataclass(frozen=True)
class Envelope:
    uid: str
    message_id: str
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


def recent(client, days: int = LOOKBACK_DAYS) -> list[Envelope]:
    since = (datetime.now() - timedelta(days=days)).strftime("%d-%b-%Y")
    status, data = client.search(None, f"(SINCE {since})")
    if status != "OK" or not data or not data[0]:
        return []

    envelopes = []
    for uid in data[0].split():
        # PEEK so that reading the mailbox never marks anything read.
        status, payload = client.fetch(uid, "(BODY.PEEK[])")
        if status != "OK" or not payload or not isinstance(payload[0], tuple):
            continue

        message = email.message_from_bytes(payload[0][1])
        senders = _addresses(message, "From")
        envelopes.append(
            Envelope(
                uid=uid.decode(),
                message_id=_text(message.get("Message-ID")) or f"uid:{uid.decode()}",
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
