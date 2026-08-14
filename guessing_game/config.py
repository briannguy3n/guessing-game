"""Settings.

Shared settings (SMTP, model) live in .env. Each group of players gets its own
.env.<group> file holding just that group's roster, so adding a group never
means touching another group's config.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values, load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
HISTORY_PATH = REPO_ROOT / ".history.jsonl"

# Group names become part of an email address (you+chimgee@...), so keep them
# to characters that survive a round trip through a mail header.
GROUP_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")

MIN_PLAYERS = 2


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Player:
    name: str
    address: str


@dataclass(frozen=True)
class Group:
    name: str
    players: list[Player]


@dataclass(frozen=True)
class Config:
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    imap_host: str
    from_address: str
    model: str
    daily_round_limit: int


def _require(key: str) -> str:
    value = os.environ.get(key, "").strip()
    if not value:
        raise ConfigError(f"{key} is not set. Copy .env.example to .env and fill it in.")
    return value


def load_config() -> Config:
    load_dotenv(REPO_ROOT / ".env")

    smtp_user = _require("SMTP_USER")
    return Config(
        smtp_host=os.environ.get("SMTP_HOST", "smtp.gmail.com"),
        smtp_port=int(os.environ.get("SMTP_PORT", "587")),
        smtp_user=smtp_user,
        smtp_password=_require("SMTP_PASSWORD"),
        imap_host=os.environ.get("IMAP_HOST", "imap.gmail.com"),
        from_address=os.environ.get("FROM_ADDRESS", smtp_user),
        model=os.environ.get("MODEL", "claude-opus-5"),
        daily_round_limit=int(os.environ.get("DAILY_ROUND_LIMIT", "10")),
    )


def group_path(name: str) -> Path:
    return REPO_ROOT / f".env.{name}"


def available_groups() -> list[str]:
    names = [
        path.name[len(".env.") :]
        for path in REPO_ROOT.glob(".env.*")
        if not path.name.endswith(".example")
    ]
    return sorted(n for n in names if GROUP_NAME_PATTERN.match(n))


def load_group(name: str) -> Group:
    """Read one group's roster. Players are numbered from 1 and read until a gap."""
    normalized = name.strip().lower()
    if not GROUP_NAME_PATTERN.match(normalized):
        raise ConfigError(
            f"'{name}' is not a usable group name. Use lowercase letters, digits, - and _."
        )
    if normalized == "example":
        raise ConfigError("'example' is the template file name, not a group.")

    path = group_path(normalized)
    if not path.exists():
        known = ", ".join(available_groups()) or "none yet"
        raise ConfigError(f"No group '{normalized}' — expected {path.name}. Groups found: {known}")

    values = dotenv_values(path)
    players: list[Player] = []
    index = 1
    while True:
        player_name = (values.get(f"PLAYER_{index}_NAME") or "").strip()
        address = (values.get(f"PLAYER_{index}_EMAIL") or "").strip()
        if not player_name and not address:
            break
        if not player_name or not address:
            raise ConfigError(
                f"{path.name}: PLAYER_{index} needs both PLAYER_{index}_NAME and "
                f"PLAYER_{index}_EMAIL."
            )
        players.append(Player(player_name, address))
        index += 1

    if len(players) < MIN_PLAYERS:
        raise ConfigError(
            f"{path.name} has {len(players)} player(s). A round needs at least {MIN_PLAYERS}."
        )

    addresses = [p.address.lower() for p in players]
    duplicates = {a for a in addresses if addresses.count(a) > 1}
    if duplicates:
        raise ConfigError(
            f"{path.name}: the same email is used by more than one player "
            f"({', '.join(sorted(duplicates))}). Each player needs their own address."
        )

    return Group(normalized, players)
