"""Turning one incoming email into one game.

The trigger address is plus-addressed: mail to you+chimgee@gmail.com starts a
game for the group named in .env.chimgee. The subject line is the category.

Everything here is written to fail closed. Mail that does not clearly come
from a player of a real group is dropped without a reply — bouncing would
confirm to a stranger that the address is live.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from .config import GROUP_NAME_PATTERN, Config, ConfigError, Group, load_group
from .inbox import Envelope

REPLY_PREFIX = re.compile(r"^\s*(re|fwd|fw|aw|automatic reply)\s*:", re.IGNORECASE)
AUTO_REPLY_HINT = re.compile(r"out of office|auto[- ]?reply|vacation", re.IGNORECASE)
DOT_INSENSITIVE_DOMAINS = {"gmail.com", "googlemail.com"}

MAX_CATEGORY_LENGTH = 80


@dataclass(frozen=True)
class Request:
    group: Group
    category: str
    requester: str


@dataclass(frozen=True)
class Rejected:
    reason: str
    # Only replies to a known player; a stranger gets silence.
    notify: str = ""


def _split(address: str) -> tuple[str, str]:
    local, _, domain = address.partition("@")
    return local.lower(), domain.lower()


def _normalize(address: str) -> str:
    """Compare addresses the way the mail provider does."""
    local, domain = _split(address)
    local = local.split("+", 1)[0]
    if domain in DOT_INSENSITIVE_DOMAINS:
        local = local.replace(".", "")
    return f"{local}@{domain}"


def group_tag(recipients: list[str], listen_address: str) -> str:
    """The +tag on whichever recipient is our listening address."""
    base = _normalize(listen_address)
    for recipient in recipients:
        if _normalize(recipient) != base:
            continue
        local, _ = _split(recipient)
        _, _, tag = local.partition("+")
        if tag:
            return tag
    return ""


def _category(envelope: Envelope) -> str:
    category = envelope.subject.strip()
    if not category:
        for line in envelope.body.splitlines():
            if line.strip():
                category = line.strip()
                break
    return category[:MAX_CATEGORY_LENGTH].strip()


def _looks_automated(envelope: Envelope) -> bool:
    if envelope.in_reply_to or envelope.references:
        return True
    if envelope.auto_submitted and envelope.auto_submitted.lower() != "no":
        return True
    if envelope.precedence.lower() in {"bulk", "junk", "list", "auto_reply"}:
        return True
    return bool(REPLY_PREFIX.match(envelope.subject) or AUTO_REPLY_HINT.search(envelope.subject))


def classify(envelope: Envelope, config: Config) -> Request | Rejected:
    """Decide what, if anything, this email should trigger."""
    if not envelope.sender:
        return Rejected("no sender")

    # Our own outgoing mail must never start another game. Test the header we
    # stamp, not the sender — players commonly trigger a game from the same
    # account the game sends from, and that has to keep working.
    if envelope.own_mail:
        return Rejected("one of our own emails")

    if _looks_automated(envelope):
        return Rejected("looks like a reply or auto-response")

    tag = group_tag(envelope.recipients, config.smtp_user)
    if not tag:
        return Rejected("not addressed to a +group address")
    if not GROUP_NAME_PATTERN.match(tag):
        return Rejected(f"unusable group tag '{tag}'")

    try:
        group = load_group(tag)
    except ConfigError:
        return Rejected(f"no group '{tag}'")

    roster = {_normalize(p.address) for p in group.players}
    if _normalize(envelope.sender) not in roster:
        return Rejected(f"sender is not in group '{tag}'")

    category = _category(envelope)
    if not category:
        return Rejected("no category in subject or body", notify=envelope.sender)

    return Request(group=group, category=category, requester=envelope.sender)


class Handled:
    """Message ids already dealt with, so a poll never repeats itself.

    This replaces the mailbox read flag. Nothing we do changes the user's mail.
    """

    def __init__(self, path: Path, keep_days: int) -> None:
        self._path = path
        self._keep_days = keep_days
        self._seen = self._load()

    def _load(self) -> dict:
        if not self._path.exists():
            return {}
        try:
            data = json.loads(self._path.read_text())
        except (ValueError, OSError):
            return {}
        return data if isinstance(data, dict) else {}

    def __contains__(self, message_id: str) -> bool:
        return message_id in self._seen

    def add(self, message_id: str) -> None:
        self._seen[message_id] = date.today().isoformat()

    def save(self) -> None:
        cutoff = (date.today() - timedelta(days=self._keep_days)).isoformat()
        # Ids older than the poll window can never come back round again.
        self._seen = {k: v for k, v in self._seen.items() if v >= cutoff}
        self._path.write_text(json.dumps(self._seen))


class DailyLimit:
    """Caps games per group per day so a stuck sender cannot burn API credit."""

    def __init__(self, path: Path, limit: int) -> None:
        self._path = path
        self._limit = limit

    def _load(self) -> dict:
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text())
        except (ValueError, OSError):
            return {}

    def _key(self, group: str) -> str:
        return f"{group}:{date.today().isoformat()}"

    def exceeded(self, group: str) -> bool:
        return self._load().get(self._key(group), 0) >= self._limit

    def record(self, group: str) -> None:
        counts = self._load()
        key = self._key(group)
        counts[key] = counts.get(key, 0) + 1
        # Only today's tallies matter; drop the rest so the file cannot grow forever.
        today = date.today().isoformat()
        counts = {k: v for k, v in counts.items() if k.endswith(today)}
        self._path.write_text(json.dumps(counts))
