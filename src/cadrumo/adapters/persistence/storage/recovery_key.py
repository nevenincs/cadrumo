"""Recovery-code minting and its canonical grouped-code encoder.

A recovery code is an opaque high-entropy secret as far as every consumer
is concerned; this module is the only thing in the substrate that can mint
one strong enough to resist offline guessing. A profile's recovery envelope
wraps that profile's DEK under its own supervised Argon2id parameters and
takes the canonical code as its secret. The encoder is bound to no custody
architecture, no file layout and no key schedule, and the substrate never
persists the code.

**Shape.** Six groups of five symbols drawn from a 32-symbol alphabet that
omits the characters people misread (``0/O``, ``1/I/L``), joined with
hyphens: ``XXXXX-XXXXX-XXXXX-XXXXX-XXXXX-XXXXX``. Thirty symbols at five bits
each carry 150 bits of entropy, which is more than the 128 bits behind the
password envelope's own key. Operator input is normalised before proof:
case, hyphens and whitespace are cosmetic, so a code typed in lowercase
without separators proves possession exactly as the displayed form does.

**Wipeable key material.** The code is held in a ``bytearray`` rather than an
immutable ``str``, so the substrate's :func:`zeroise` primitive can overwrite
it in place once the operator has copied it down. The honest limit is the
one the session path already discloses: reading :attr:`RecoveryKey.code`
materialises a transient ``str`` copy whose lifetime the garbage collector
owns. What this module does not do is hold the *only* copy of a secret in a
form no wipe primitive can reach.
"""

from __future__ import annotations

import secrets
from typing import Final, Self

from ....core.external_constants import UTF_8_ENCODING as _UTF_8_ENCODING
from .custody.zeroise import zeroise as _zeroise
from .errors import storage_validation_error as _storage_validation_error

RECOVERY_CODE_ALPHABET: Final[str] = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
RECOVERY_CODE_GROUP_LENGTH: Final[int] = 5
RECOVERY_CODE_GROUP_COUNT: Final[int] = 6
RECOVERY_CODE_SEPARATOR: Final[str] = "-"
RECOVERY_CODE_SYMBOL_COUNT: Final[int] = RECOVERY_CODE_GROUP_LENGTH * RECOVERY_CODE_GROUP_COUNT

_ALPHABET_SET: Final[frozenset[str]] = frozenset(RECOVERY_CODE_ALPHABET)
_IGNORED_INPUT_CHARACTERS: Final[frozenset[str]] = frozenset({RECOVERY_CODE_SEPARATOR, " ", "\t", "\n", "\r", "_"})


class RecoveryKey:
    """Wipeable container for one canonical recovery code.

    Deliberately not a pydantic model. The sibling ``BucketSession`` sets
    the precedent for live key material: a slotted plain class keeps the
    buffer mutable, and -- because there is no ``model_dump_json`` -- makes
    it structurally impossible to serialise the secret by accident.
    """

    __slots__ = ("_code_buffer",)

    def __init__(self, *, code: str) -> None:
        """Copy ``code`` into the wipeable buffer this key owns.

        Args:
            code: A canonical recovery code, exactly as :func:`format_recovery_code`
                renders it.

        Raises:
            StorageValidationError: If the code is not in canonical form.
        """
        if code != format_recovery_code(normalise_recovery_code(code)):
            raise _storage_validation_error("recovery code must be in canonical grouped form")
        self._code_buffer = bytearray(code.encode(_UTF_8_ENCODING))

    @property
    def code(self) -> str:
        """Return the canonical grouped code, decoded from its wipeable buffer."""
        return self._code_buffer.decode(_UTF_8_ENCODING)

    def wipe(self) -> None:
        """Overwrite the code buffer with zero bytes.

        Idempotent: wiping an already-wiped key is a no-op that leaves the
        buffer zeroed and its length unchanged.
        """
        _zeroise(self._code_buffer)

    def __enter__(self) -> Self:
        """Return this key, so a ``with`` block bounds the secret's lifetime."""
        return self

    def __exit__(self, *_exc_info: object) -> None:
        """Wipe the buffer on block exit, whether or not the body raised."""
        self.wipe()


def normalise_recovery_code(text: str) -> str:
    """Reduce operator input to the bare symbol run the code was minted from.

    Case, hyphens, underscores and whitespace are cosmetic and dropped. Any
    other character, or a run that is not exactly the minted length, is
    refused: a code that cannot be the minted one must not reach the KDF.

    Raises:
        StorageValidationError: When ``text`` cannot be a recovery code.
    """
    symbols = "".join(character for character in text.upper() if character not in _IGNORED_INPUT_CHARACTERS)
    if len(symbols) != RECOVERY_CODE_SYMBOL_COUNT:
        raise _storage_validation_error(
            f"recovery code must contain exactly {RECOVERY_CODE_SYMBOL_COUNT} symbols; got {len(symbols)}",
        )
    if any(character not in _ALPHABET_SET for character in symbols):
        raise _storage_validation_error("recovery code contains a character outside its alphabet")
    return symbols


def format_recovery_code(symbols: str) -> str:
    """Render a bare symbol run in the canonical hyphen-grouped form."""
    if len(symbols) != RECOVERY_CODE_SYMBOL_COUNT or any(character not in _ALPHABET_SET for character in symbols):
        raise _storage_validation_error("recovery code symbols are not a complete alphabet run")
    groups = (
        symbols[index : index + RECOVERY_CODE_GROUP_LENGTH]
        for index in range(0, RECOVERY_CODE_SYMBOL_COUNT, RECOVERY_CODE_GROUP_LENGTH)
    )
    return RECOVERY_CODE_SEPARATOR.join(groups)


def canonical_recovery_code(text: str) -> str:
    """Return the canonical form of an operator-supplied code, or refuse it."""
    return format_recovery_code(normalise_recovery_code(text))


def generate_recovery_key() -> RecoveryKey:
    """Mint a fresh :class:`RecoveryKey` from the process CSPRNG.

    Each symbol is drawn independently with :func:`secrets.choice`, so the
    code carries the full five bits per symbol. The returned record is the
    only in-memory copy; callers must arrange for the operator to copy the
    code down, then :meth:`RecoveryKey.wipe` it.
    """
    symbols = "".join(secrets.choice(RECOVERY_CODE_ALPHABET) for _ in range(RECOVERY_CODE_SYMBOL_COUNT))
    return RecoveryKey(code=format_recovery_code(symbols))


__all__ = [
    "RECOVERY_CODE_ALPHABET",
    "RECOVERY_CODE_GROUP_COUNT",
    "RECOVERY_CODE_GROUP_LENGTH",
    "RECOVERY_CODE_SEPARATOR",
    "RECOVERY_CODE_SYMBOL_COUNT",
    "RecoveryKey",
    "canonical_recovery_code",
    "format_recovery_code",
    "generate_recovery_key",
    "normalise_recovery_code",
]
