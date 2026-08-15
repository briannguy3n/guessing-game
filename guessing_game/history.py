"""Past picks, stored so the generator never repeats a character.

Entries are base64-encoded: not security, just so an accidental `cat` of the
file doesn't spoil a game that's still being played.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path


def _encode(payload: dict) -> str:
    return base64.b64encode(json.dumps(payload).encode()).decode()


def _decode(line: str) -> dict:
    return json.loads(base64.b64decode(line).decode())


def past_characters(path: Path, category: str) -> list[str]:
    if not path.exists():
        return []
    wanted = category.strip().lower()
    seen: list[str] = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            entry = _decode(line)
        except (ValueError, json.JSONDecodeError):
            continue
        if entry.get("category", "").lower() == wanted:
            seen.extend(entry.get("characters", []))
    return seen


def record(path: Path, category: str, characters: list[str]) -> None:
    entry = _encode({"category": category, "characters": characters})
    with path.open("a") as handle:
        handle.write(entry + "\n")
