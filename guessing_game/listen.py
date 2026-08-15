"""One pass over the inbox: python -m guessing_game.listen

Runs a single poll and exits, which suits a cron or scheduled CI job better
than a long-lived daemon. Log output names groups, senders and categories —
never a character.

Reading is strictly read-only: no flags are changed, nothing is marked read,
nothing is moved. What has already been handled is remembered here instead.
"""

from __future__ import annotations

import sys

from . import characters, game, inbox
from .config import HISTORY_PATH, REPO_ROOT, ConfigError, load_config
from .delivery import EmailNotifier
from .inbox import LOOKBACK_DAYS
from .router import DailyLimit, Handled, Rejected, classify

COUNTS_PATH = REPO_ROOT / ".game-counts.json"
HANDLED_PATH = REPO_ROOT / ".handled-mail.json"

# Keep ids a little longer than the poll window so nothing slips back in.
HANDLED_KEEP_DAYS = LOOKBACK_DAYS + 1


def _confirm(notifier: EmailNotifier, to: str, category: str) -> None:
    """Acknowledge a game. The requester is a player, so this says nothing useful."""
    notifier.send(
        to,
        f"Game started: {category}",
        f"Everyone has been emailed for '{category}'.\n\n"
        f"Your own character is not in this message and never will be — "
        f"that is the point.\n",
    )


def _decline(notifier: EmailNotifier, to: str, reason: str) -> None:
    notifier.send(to, "Game not started", f"{reason}\n")


def process_once() -> int:
    config = load_config()
    notifier = EmailNotifier(config)
    limit = DailyLimit(COUNTS_PATH, config.daily_game_limit)
    handled = Handled(HANDLED_PATH, HANDLED_KEEP_DAYS)
    started = 0

    # Mail already sitting in the window when this record is first created was
    # sent before anything was watching. Acting on it would replay old games.
    priming = not HANDLED_PATH.exists()
    if priming:
        print("First run: noting what is already in the inbox without acting on it.")

    try:
        with inbox.connect(config) as client:
            for envelope in inbox.recent(client):
                if envelope.message_id in handled:
                    continue
                if priming:
                    handled.add(envelope.message_id)
                    continue

                outcome = classify(envelope, config)
                handled.add(envelope.message_id)

                if isinstance(outcome, Rejected):
                    # Most of these are ordinary inbox mail, not failed triggers.
                    print(f"ignored ({outcome.reason})")
                    if outcome.notify:
                        _decline(
                            notifier,
                            outcome.notify,
                            "Put the category in the subject line, then send again.",
                        )
                    continue

                if limit.exceeded(outcome.group.name):
                    print(f"skipped (daily limit reached for {outcome.group.name})")
                    _decline(
                        notifier,
                        outcome.requester,
                        "That group has hit its game limit for today. Try again tomorrow.",
                    )
                    continue

                try:
                    game.play(outcome.category, outcome.group, config, notifier, HISTORY_PATH)
                except characters.GenerationError as error:
                    print(f"generation failed for {outcome.group.name}")
                    _decline(notifier, outcome.requester, str(error))
                    continue
                except Exception:
                    # Never surface the detail: a traceback can carry a character name.
                    print(f"game failed for {outcome.group.name}")
                    _decline(
                        notifier,
                        outcome.requester,
                        "Something went wrong starting that game. Nothing was sent.",
                    )
                    continue

                limit.record(outcome.group.name)
                _confirm(notifier, outcome.requester, outcome.category)
                started += 1
                print(f"sent game for {outcome.group.name}: {outcome.category}")
    finally:
        # Save even on a crash, so a half-finished pass cannot replay a game.
        handled.save()

    return started


def main() -> int:
    try:
        started = process_once()
    except ConfigError as error:
        print(f"Setup problem: {error}", file=sys.stderr)
        return 1
    except Exception as error:
        print(f"Could not check the inbox: {type(error).__name__}", file=sys.stderr)
        return 1

    print(f"Done. Games started: {started}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
