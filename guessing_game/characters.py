"""Ask Claude for characters that fit a category."""

from __future__ import annotations

import anthropic
from pydantic import BaseModel, Field


class Pick(BaseModel):
    name: str = Field(description="The character's commonly known name.")
    hint: str = Field(
        description=(
            "One short sentence placing the character, without naming them or "
            "giving away a defining trait. Shown to the guesser only if they ask for help."
        )
    )


class Round(BaseModel):
    picks: list[Pick] = Field(description="The requested number of distinct characters.")


class GenerationError(Exception):
    pass


PROMPT = """\
Pick {count} characters for a verbal guessing game in the category: {category}

{count} people each get assigned one of these characters without knowing which
is theirs. Everyone can see everyone else's character but their own. They ask
each other yes/no questions to work out who they are.

Go wide and have fun with it. The picks should come from completely different
corners of the category — different franchises, different media, different
decades, different tones. Picks that sit right next to each other make for a
boring round; a line-up nobody would ever put in the same sentence makes a
great one. No two picks should feel like near-neighbours of each other.

Tonal contrast is doing a lot of the work. Put something epic or menacing
against something cozy or ridiculous. Pairings in this spirit:

- cats: Meowth (Pokémon) and Hello Kitty (Sanrio mascot)
- secret agents: Kim Possible and Mr. Bean
- rich characters: Smaug and Tom Nook
- characters who can't speak English: Chewbacca and Glep from Smiling Friends

"Character" is meant loosely — anyone famous enough to be recognized. Fiction
from film, TV, anime, games, books, comics, and memes all count, and so do
real people: historical figures, religious figures, royalty, athletes,
musicians, politicians. Jesus and Princess Diana are exactly as valid as
Meowth. Mixing real people with fictional ones in the same round is
encouraged where the category allows it.

Requirements:
- Every pick belongs to the category, even if only by a silly technicality.
- Each is guessable through questions about appearance, personality, role,
  and setting.
- They do not need to be equally famous. A household name against a deeper
  cut is fine and often funnier — the mismatch is part of the joke. The floor
  is recognition, not equal fame: if the player heard the name out loud they
  should think "oh, of course," not "who?"
- Avoid picks so obscure that the round dies. A character from a niche show
  is fine if that show is widely talked about; an incidental background
  character is not.
{avoid}"""


def generate(category: str, model: str, avoid: list[str], count: int = 2) -> list[Pick]:
    if count < 2:
        raise GenerationError("A round needs at least two characters.")

    client = anthropic.Anthropic()

    avoid_clause = ""
    if avoid:
        avoid_clause = (
            "\nDo not pick any of these, they have been used before: "
            + ", ".join(sorted(set(avoid)))
        )

    response = client.messages.parse(
        model=model,
        max_tokens=4000,
        output_format=Round,
        messages=[
            {
                "role": "user",
                "content": PROMPT.format(
                    count=count, category=category.strip(), avoid=avoid_clause
                ),
            }
        ],
    )

    if response.stop_reason == "refusal":
        raise GenerationError("Claude declined this category. Try a different one.")

    result = response.parsed_output
    if result is None or len(result.picks) != count:
        raise GenerationError(f"Claude did not return {count} characters. Try again.")

    names = [p.name.strip().lower() for p in result.picks]
    if len(set(names)) != len(names):
        raise GenerationError("Claude repeated a character. Try again.")

    return result.picks
