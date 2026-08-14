"""Playing one round: pick characters, tell each player about everyone else.

Nothing here may print or return a character name. Callers include the CLI,
which is run by a player, and the email router, which replies to one.
"""

from __future__ import annotations

from . import characters, history
from .config import Config, Group, Player
from .delivery import Notifier


def _body(reader: Player, others: list[tuple[Player, characters.Pick]], category: str) -> str:
    lines = [f"Category: {category}", ""]

    if len(others) == 1:
        partner, pick = others[0]
        lines += [
            f"{partner.name}'s character is:",
            "",
            f"    {pick.name}",
            "",
            f"Hint, if {partner.name} gets stuck: {pick.hint}",
            "",
            f"You don't know your own character — {partner.name} does. "
            f"Ask each other yes/no questions until someone gets it.",
        ]
    else:
        lines += ["Everyone else's character is below. Yours is not here — the others have it.", ""]
        for partner, pick in others:
            lines += [
                f"    {partner.name} — {pick.name}",
                f"        hint, if {partner.name} gets stuck: {pick.hint}",
                "",
            ]
        lines += [
            "Ask yes/no questions around the group until someone works out who they are.",
        ]

    lines += [
        "",
        "Don't reply to this email with anything the others might read.",
        "",
    ]
    return "\n".join(lines)


def play(
    category: str,
    group: Group,
    config: Config,
    notifier: Notifier,
    history_path,
) -> None:
    """Assign a character to each player and tell everyone about everyone else."""
    players = group.players
    avoid = history.past_characters(history_path, category)
    picks = characters.generate(category, config.model, avoid, count=len(players))

    assigned = list(zip(players, picks))
    subject = f"Guessing game: {category}"

    for reader in players:
        others = [(player, pick) for player, pick in assigned if player is not reader]
        notifier.send(reader.address, subject, _body(reader, others, category))

    history.record(history_path, category, [p.name for p in picks])
