"""One pass over the inbox: python -m guessing_game.listen

Runs a single poll and exits, which suits a cron or scheduled CI job better
than a long-lived daemon. Log output names groups, senders and categories —
never a character.
"""

from __future__ import annotations

import sys

from . import characters, inbox, rounds
from .config import HISTORY_PATH, REPO_ROOT, ConfigError, load_config
from .delivery import EmailNotifier
from .router import DailyLimit, Rejected, classify

COUNTS_PATH = REPO_ROOT / ".round-counts.json"


def _confirm(notifier: EmailNotifier, to: str, category: str) -> None:
    """Acknowledge a round. The requester is a player, so this says nothing useful."""
    notifier.send(
        to,
        f"Round started: {category}",
        f"Everyone has been emailed their round for '{category}'.\n\n"
        f"Yours is not in this message and never will be — that is the game.\n",
    )


def _decline(notifier: EmailNotifier, to: str, reason: str) -> None:
    notifier.send(to, "Round not started", f"{reason}\n")


def process_once() -> int:
    config = load_config()
    notifier = EmailNotifier(config)
    limit = DailyLimit(COUNTS_PATH, config.daily_round_limit)
    handled = 0

    with inbox.connect(config) as client:
        for envelope in inbox.unread(client):
            outcome = classify(envelope, config)

            if isinstance(outcome, Rejected):
                print(f"skipped ({outcome.reason})")
                if outcome.notify:
                    _decline(
                        notifier,
                        outcome.notify,
                        "Put the category in the subject line, then send again.",
                    )
                inbox.mark_read(client, envelope.uid)
                continue

            if limit.exceeded(outcome.group.name):
                print(f"skipped (daily limit reached for {outcome.group.name})")
                _decline(
                    notifier,
                    outcome.requester,
                    "That group has hit its round limit for today. Try again tomorrow.",
                )
                inbox.mark_read(client, envelope.uid)
                continue

            try:
                rounds.play(
                    outcome.category, outcome.group, config, notifier, HISTORY_PATH
                )
            except characters.GenerationError as error:
                print(f"generation failed for {outcome.group.name}")
                _decline(notifier, outcome.requester, str(error))
                inbox.mark_read(client, envelope.uid)
                continue
            except Exception:
                # Never surface the detail: a traceback can carry a character name.
                print(f"round failed for {outcome.group.name}")
                _decline(
                    notifier,
                    outcome.requester,
                    "Something went wrong starting that round. Nothing was sent.",
                )
                inbox.mark_read(client, envelope.uid)
                continue

            limit.record(outcome.group.name)
            inbox.mark_read(client, envelope.uid)
            _confirm(notifier, outcome.requester, outcome.category)
            handled += 1
            print(f"sent round for {outcome.group.name}: {outcome.category}")

    return handled


def main() -> int:
    try:
        handled = process_once()
    except ConfigError as error:
        print(f"Setup problem: {error}", file=sys.stderr)
        return 1
    except Exception as error:
        print(f"Could not check the inbox: {type(error).__name__}", file=sys.stderr)
        return 1

    print(f"Done. Rounds started: {handled}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
