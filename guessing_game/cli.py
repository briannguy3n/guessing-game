"""Start a game: ./guess "cats" --group chimgee

Prints only whether the messages were sent. It must never print, log, or
otherwise reveal either character — the person running this is a player.
"""

from __future__ import annotations

import argparse
import sys

from . import characters, history
from .config import (
    HISTORY_PATH,
    Config,
    ConfigError,
    Group,
    Player,
    available_groups,
    load_config,
    load_group,
)
from .delivery import EmailNotifier, Notifier

# Bigger rosters need a different rule about who is told what, so they are
# turned away rather than half-handled.
PLAYERS_PER_GAME = 2


def _body(recipient: Player, partner: Player, category: str, pick: characters.Pick) -> str:
    return (
        f"Category: {category}\n\n"
        f"{partner.name}'s character is:\n\n"
        f"    {pick.name}\n\n"
        f"Hint, if {partner.name} gets stuck: {pick.hint}\n\n"
        f"You don't know your own character — {partner.name} does. "
        f"Ask each other yes/no questions until someone gets it.\n\n"
        f"Don't reply to this email with anything {partner.name} might read.\n"
    )


def run(category: str, group: Group, config: Config, notifier: Notifier) -> None:
    avoid = history.past_characters(HISTORY_PATH, category)
    picks = characters.generate(category, config.model, avoid)

    a, b = group.players
    pick_a, pick_b = picks  # pick_a is a's character, so b is told about it

    subject = f"Guessing game: {category}"
    notifier.send(a.address, subject, _body(a, b, category, pick_b))
    notifier.send(b.address, subject, _body(b, a, category, pick_a))

    history.record(HISTORY_PATH, category, [p.name for p in picks])


def _chosen_group(name: str | None) -> Group:
    if not name:
        groups = available_groups()
        if len(groups) != 1:
            raise ConfigError(
                "Pass --group to say who is playing. Groups found: "
                + (", ".join(groups) or "none yet")
            )
        name = groups[0]

    group = load_group(name)
    if len(group.players) != PLAYERS_PER_GAME:
        raise ConfigError(
            f"Group '{group.name}' has {len(group.players)} players. "
            f"Only {PLAYERS_PER_GAME} are supported so far."
        )
    return group


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="guess", description="Send each player the other's character for a category."
    )
    parser.add_argument("category", help='e.g. "cats", "sitcom dads", "greek myths"')
    parser.add_argument(
        "--group",
        help="Which group plays. Defaults to the only group if you have just one.",
    )
    args = parser.parse_args(argv)

    try:
        config = load_config()
        group = _chosen_group(args.group)
        run(args.category, group, config, EmailNotifier(config))
    except ConfigError as error:
        print(f"Setup problem: {error}", file=sys.stderr)
        return 1
    except characters.GenerationError as error:
        print(str(error), file=sys.stderr)
        return 1
    except Exception:
        # Deliberately terse: a traceback here could surface a character name.
        print("Something went wrong sending the game. Nothing was recorded.", file=sys.stderr)
        return 1

    print(f"Sent. Category: {args.category} — group: {group.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
