# guessing-game

Two people, one category. Each person is assigned a character they don't know.
You each know the *other's* character, and you ask yes/no questions until you
work out your own.

The point of this repo: nobody picks the characters. If you pick them yourself
you already know what's in play, and that skews every question you ask.

## How a round works

```
./guess "cats"
```

- Claude picks two famous characters in that category, deliberately from
  opposite corners of it — for "cats", think Meowth and Hello Kitty, not two
  cats from the same cartoon
- Real people count. Jesus, Princess Diana, and Meowth are all fair game
- You get an email with **her** character
- She gets an email with **your** character
- Neither of you knows your own — start asking

The terminal prints `Sent.` and nothing else. It never shows either character,
because you're one of the players.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env`:

- **`ANTHROPIC_API_KEY`** — from [console.anthropic.com](https://console.anthropic.com/settings/keys).
  A round costs well under a cent.
- **Both names and emails.**
- **`SMTP_USER` / `SMTP_PASSWORD`** — the account the mail is sent from. For
  Gmail this must be an [App Password](https://myaccount.google.com/apppasswords),
  not your normal password (needs 2FA turned on). Other providers work too —
  change `SMTP_HOST` and `SMTP_PORT`.

Then:

```bash
chmod +x guess
./guess "cats"
```

## No repeats

Past picks are saved to `.history.jsonl` and fed back to Claude so it never
reuses a character within a category. Entries are base64-encoded so an
accidental `cat` of the file doesn't spoil a live round — don't go decoding it
mid-game.

## Adding SMS later

`guessing_game/delivery.py` defines a `Notifier` with one method. `EmailNotifier`
implements it; a `TwilioNotifier` would too, and `cli.py` wouldn't change. SMS
needs a Twilio number (~$1.15/mo plus about a cent per text).

To start rounds from your phone rather than your laptop, something has to be
running to receive the trigger — that's an always-on host, not just a new
notifier.
