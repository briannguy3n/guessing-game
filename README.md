# guessing-game

A group, one category. Each person is assigned a character they don't know.
Everyone else can see it, and you ask yes/no questions until you work out your
own.

The point of this repo: nobody picks the characters. If you pick them yourself
you already know what's in play, and that skews every question you ask.

## How a game works

Email the game, or run it from the terminal. Either way:

- Claude picks one character per player, deliberately from opposite corners of
  the category — for "cats", think Meowth and Hello Kitty, not two cats from
  the same cartoon
- Real people count. Jesus, Princess Diana, and Meowth are all fair game
- Everyone gets an email listing every character **except their own**
- Start asking

Nothing ever prints a character to the terminal, because whoever ran it is a
player.

## Groups

Each group of players gets its own file, named for the group:

```
.env.c     PLAYER_1 = you, PLAYER_2 = c
.env.friends     PLAYER_1 = you, PLAYER_2..N = everyone else
```

Copy `.env.group.example` to make one. Number players from 1 with no gaps. Two
players is the classic game; with three or more, everyone sees every character
but their own.

Roster files are **not** in the repo — they hold real names and addresses, and
are gitignored. Keep your copy locally for `./guess`. To run the scheduled job,
give it its own copy of each roster as a repo secret, then add it to the
`Restore rosters` step in `.github/workflows/listen.yml` (each secret is named
individually there, rather than read in bulk). After editing a roster, update
the matching secret or the job keeps using the old one — there is no warning
when they drift.

## Starting a game by email

Send an email to your own address with the group as a plus-tag, and the
category as the subject:

```
To:      you+c@gmail.com
Subject: cats
```

A scheduled job checks the inbox every few minutes, starts the game, and
emails everyone. You get a confirmation that deliberately tells you nothing.

Plus-addressing means one mailbox serves every group — `you+c@` and
`you+friends@` both land in your normal inbox, and the tag picks the group.

The trigger works whether the email is read or unread — open it, star it,
archive it, it makes no difference. The listener never changes anything in
your mailbox; it keeps its own note of which messages it has handled, in
`.handled-mail.json`.

The very first run has nothing to compare against, so it records what is
already in the inbox and acts on none of it. That stops old mail replaying
games. Send your trigger after that first run.

What gets ignored, silently:

- Mail from anyone outside that group's roster
- Mail to a tag with no matching `.env.<group>` file
- Replies, forwards, and auto-responders, so the game's own emails can't
  trigger fresh games
- Anything past the group's daily game limit

## Starting a game from the terminal

```bash
./guess "cats" --group c
```

`--group` is optional if you only have one group.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
cp .env.group.example .env.c
```

Fill in `.env`:

- **`ANTHROPIC_API_KEY`** — from [console.anthropic.com](https://console.anthropic.com/settings/keys).
  A game costs well under a cent.
- **`SMTP_USER` / `SMTP_PASSWORD`** — the mailbox mail is sent from and the
  listener watches. For Gmail this must be an
  [App Password](https://myaccount.google.com/apppasswords), not your normal
  password (needs 2FA turned on). The same password covers IMAP. Other
  providers work too — change `SMTP_HOST`, `SMTP_PORT`, and `IMAP_HOST`.

Then fill in `.env.c` with the players, and:

```bash
chmod +x guess
./guess "cats" --group c
```

## Running the listener

One pass over the inbox, then exit:

```bash
.venv/bin/python -m guessing_game.listen
```

That works locally on any branch — good for testing before you commit to
hosting it.

For it to run without you, `.github/workflows/listen.yml` polls every five
minutes on GitHub Actions. To turn it on:

1. Add your `.env` values as repository secrets (Settings → Secrets and
   variables → Actions)
2. Merge to the default branch — **GitHub only runs scheduled workflows from
   the default branch**, never from a feature branch

Before merging you can still test the hosted path: Actions → *Check for game
requests* → Run workflow, and pick your branch. That path works from anywhere.

Two caveats worth knowing. GitHub's scheduler drifts under load, so five
minutes can stretch to twenty — fine for a party game. And scheduled workflows
switch themselves off after 60 days without repo activity; the job commits
history back on every game, which keeps that clock reset as long as you're
playing.

Moving to a small always-on box later is a cron line calling the same command.
Nothing in the code changes.

## No repeats

Past picks are saved to `.history.jsonl` and fed back to Claude so it never
reuses a character within a category. Entries are base64-encoded so an
accidental `cat` of the file doesn't spoil a live game — don't go decoding it
mid-game.

The scheduled job commits this file back to the repo, so the memory survives
between runs. If you also play from the terminal, `git pull` first or the two
histories drift apart.

## Adding SMS later

`guessing_game/delivery.py` defines a `Notifier` with one method.
`EmailNotifier` implements it; a `TwilioNotifier` would too, and nothing that
starts a game would change. SMS needs a Twilio number (~$1.15/mo plus about a
cent per text).
