"""Ask Claude for two characters that fit a category."""

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
    picks: list[Pick] = Field(description="Exactly two distinct characters.")


class GenerationError(Exception):
    pass


PROMPT = """\
Pick two characters for a verbal guessing game in the category: {category}

Two people each get assigned one of these characters without knowing which is
theirs. They ask each other yes/no questions to work out who they are.

Requirements:
- Both characters clearly belong to the category.
- Both are widely known — a reasonably well-read adult should recognize them.
  Obscure picks make the game unwinnable.
- The two are distinct from each other and guessable through questions about
  appearance, personality, role, and setting.
- Roughly comparable in fame, so neither round is lopsided.
{avoid}"""


def generate(category: str, model: str, avoid: list[str]) -> list[Pick]:
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
                "content": PROMPT.format(category=category.strip(), avoid=avoid_clause),
            }
        ],
    )

    if response.stop_reason == "refusal":
        raise GenerationError("Claude declined this category. Try a different one.")

    result = response.parsed_output
    if result is None or len(result.picks) != 2:
        raise GenerationError("Claude did not return two characters. Try again.")

    return result.picks
