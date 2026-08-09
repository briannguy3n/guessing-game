"""Settings loaded from .env in the repo root."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
HISTORY_PATH = REPO_ROOT / ".history.jsonl"


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Player:
    name: str
    address: str


@dataclass(frozen=True)
class Config:
    player_a: Player
    player_b: Player
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    from_address: str
    model: str


def _require(key: str) -> str:
    value = os.environ.get(key, "").strip()
    if not value:
        raise ConfigError(f"{key} is not set. Copy .env.example to .env and fill it in.")
    return value


def load_config() -> Config:
    load_dotenv(REPO_ROOT / ".env")

    smtp_user = _require("SMTP_USER")
    return Config(
        player_a=Player(_require("PLAYER_A_NAME"), _require("PLAYER_A_EMAIL")),
        player_b=Player(_require("PLAYER_B_NAME"), _require("PLAYER_B_EMAIL")),
        smtp_host=os.environ.get("SMTP_HOST", "smtp.gmail.com"),
        smtp_port=int(os.environ.get("SMTP_PORT", "587")),
        smtp_user=smtp_user,
        smtp_password=_require("SMTP_PASSWORD"),
        from_address=os.environ.get("FROM_ADDRESS", smtp_user),
        model=os.environ.get("MODEL", "claude-opus-5"),
    )
