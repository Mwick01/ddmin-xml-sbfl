from __future__ import annotations

from dataclasses import dataclass
import random


# IMPORTANT:
# This is an AFL-style mutation prototype.
# It is NOT AFL or AFLSmart itself.
#
# Its purpose is to validate:
#
# DDMIN seed -> mutation -> existing oracle -> PASS/FAIL/UNRESOLVED
#
# Once this works, this mutator will be replaced by the real
# AFL/AFLSmart mutation stage.

XML_FRIENDLY_BYTES = (
    b'<>/="\'?!-_:. '
    b"abcdefghijklmnopqrstuvwxyz"
    b"ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    b"0123456789"
    b"\n\t"
)


@dataclass(frozen=True)
class Mutation:
    data: bytes
    operator: str


def _random_byte(rng: random.Random) -> int:
    """
    Mostly choose bytes commonly found in XML so that every mutation
    is not immediately rejected.

    Occasionally choose any possible byte to keep the mutation stage
    byte-oriented.
    """
    if rng.random() < 0.85:
        return XML_FRIENDLY_BYTES[
            rng.randrange(len(XML_FRIENDLY_BYTES))
        ]

    return rng.randrange(256)


def mutate(data: bytes, rng: random.Random) -> Mutation:
    """
    Apply one simple AFL-style byte mutation.

    Returns both the mutated bytes and the mutation operator used.
    """

    if not data:
        return Mutation(
            bytes([_random_byte(rng)]),
            "insert_byte",
        )

    operators = [
        "bit_flip",
        "delete_byte",
        "insert_byte",
        "replace_byte",
        "duplicate_block",
    ]

    operator = rng.choice(operators)

    mutated = bytearray(data)

    if operator == "bit_flip":
        position = rng.randrange(len(mutated))
        bit = 1 << rng.randrange(8)
        mutated[position] ^= bit

    elif operator == "delete_byte":
        position = rng.randrange(len(mutated))
        del mutated[position]

    elif operator == "insert_byte":
        position = rng.randrange(len(mutated) + 1)

        mutated.insert(
            position,
            _random_byte(rng),
        )

    elif operator == "replace_byte":
        position = rng.randrange(len(mutated))

        mutated[position] = _random_byte(rng)

    elif operator == "duplicate_block":
        start = rng.randrange(len(mutated))

        max_length = min(
            8,
            len(mutated) - start,
        )

        length = rng.randint(
            1,
            max_length,
        )

        block = mutated[
            start : start + length
        ]

        insert_at = rng.randrange(
            len(mutated) + 1
        )

        mutated[insert_at:insert_at] = block

    return Mutation(
        bytes(mutated),
        operator,
    )