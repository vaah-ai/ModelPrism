"""Agent naming utility — generates unique friendly names.

Names follow the pattern ``{adjective}-{animal}-{number}``, e.g. ``cyan-koala-42``.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    pass

_ADJECTIVES: list[str] = [
    "ancient",
    "autumn",
    "bold",
    "brave",
    "bright",
    "calm",
    "chilly",
    "clever",
    "cool",
    "crimson",
    "cuddly",
    "curious",
    "cyan",
    "dark",
    "dawn",
    "deep",
    "distant",
    "dry",
    "dusty",
    "eager",
    "early",
    "faint",
    "fallen",
    "fancy",
    "fast",
    "flat",
    "fresh",
    "frosty",
    "gentle",
    "golden",
    "grand",
    "great",
    "green",
    "happy",
    "hidden",
    "holy",
    "icy",
    "jolly",
    "kind",
    "large",
    "late",
    "lazy",
    "light",
    "little",
    "lively",
    "lone",
    "long",
    "loud",
    "lovely",
    "lucky",
    "misty",
    "muddy",
    "mute",
    "noble",
    "odd",
    "old",
    "pale",
    "patient",
    "plain",
    "proud",
    "pure",
    "quiet",
    "rapid",
    "red",
    "rich",
    "rough",
    "royal",
    "shy",
    "silent",
    "silly",
    "slow",
    "small",
    "smart",
    "smooth",
    "soft",
    "solid",
    "strange",
    "sunny",
    "swift",
    "tall",
    "tame",
    "tidy",
    "tiny",
    "tough",
    "tricky",
    "true",
    "vivid",
    "warm",
    "wild",
    "winter",
    "wise",
    "young",
    "zen",
]

_ANIMALS: list[str] = [
    "anteater",
    "badger",
    "bat",
    "bear",
    "beaver",
    "bison",
    "boar",
    "camel",
    "cat",
    "cheetah",
    "cobra",
    "coyote",
    "crane",
    "crocodile",
    "crow",
    "deer",
    "dolphin",
    "dove",
    "dragonfly",
    "duck",
    "eagle",
    "eel",
    "elk",
    "falcon",
    "ferret",
    "finch",
    "fox",
    "frog",
    "gecko",
    "goat",
    "goose",
    "hawk",
    "heron",
    "horse",
    "ibis",
    "jackal",
    "jaguar",
    "jay",
    "koala",
    "lemur",
    "leopard",
    "lizard",
    "lynx",
    "mantis",
    "marten",
    "mink",
    "mole",
    "monkey",
    "moose",
    "moth",
    "newt",
    "ocelot",
    "octopus",
    "oriole",
    "otter",
    "owl",
    "panda",
    "panther",
    "parrot",
    "pelican",
    "penguin",
    "pigeon",
    "puma",
    "python",
    "quail",
    "rabbit",
    "raccoon",
    "raven",
    "robin",
    "salamander",
    "seal",
    "shark",
    "sheep",
    "skunk",
    "sloth",
    "snake",
    "sparrow",
    "spider",
    "squid",
    "squirrel",
    "swan",
    "swift",
    "tiger",
    "toad",
    "turtle",
    "viper",
    "vulture",
    "walrus",
    "weasel",
    "wolf",
    "wombat",
    "wren",
    "yak",
    "zebra",
]


def generate_name() -> str:
    """Generate a random agent name in adjective-animal-number format.

    Returns:
        A name string like ``"cyan-koala-42"``.
    """
    adjective = random.choice(_ADJECTIVES)
    animal = random.choice(_ANIMALS)
    number = random.randint(1, 999)
    return f"{adjective}-{animal}-{number}"


async def generate_unique_name(db: AsyncSession, max_attempts: int = 20) -> str:
    """Generate a unique agent name not already used in the database.

    Args:
        db: An active SQLAlchemy async session.
        max_attempts: Maximum number of name generation attempts before
            raising an error (default 20).

    Returns:
        A unique name string.

    Raises:
        RuntimeError: If a unique name cannot be generated within
            ``max_attempts`` attempts.
    """
    from app.models.agent import Agent

    for _ in range(max_attempts):
        name = generate_name()
        result = await db.execute(select(Agent).where(Agent.name == name))
        if result.scalar_one_or_none() is None:
            return name
    msg = f"Could not generate a unique agent name after {max_attempts} attempts"
    raise RuntimeError(msg)
