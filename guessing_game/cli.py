"""Start a game from the terminal: ./guess "cats" --group chimgee

Prints only whether the messages were sent. It must never print, log, or
otherwise reveal any character — the person running this is a player.
"""

from __future__ import annotations

import argparse
import sys

from . import characters, game
from .config import (
    HISTORY_PATH,
    ConfigError,
    available_groups,
    load_config,
    load_group,
)
from .delivery import EmailNotifier


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="guess", description="Send every player the other players' characters."
    )
    parser.add_argument("category", help='e.g. "cats", "sitcom dads", "greek myths"')
    parser.add_argument(
        "--group",
        help="Which group plays. Defaults to the only group if you have just one.",
    )
    args = parser.parse_args(argv)

    try:
        name = args.group
        if not name:
            groups = available_groups()
            if len(groups) != 1:
                raise ConfigError(
                    "Pass --group to say who is playing. Groups found: "
                    + (", ".join(groups) or "none yet")
                )
            name = groups[0]

        config = load_config()
        group = load_group(name)
        game.play(args.category, group, config, EmailNotifier(config), HISTORY_PATH)
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

    print(f"Sent. Category: {args.category} — group: {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
