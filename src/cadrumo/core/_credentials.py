"""Passphrase-strength advisory banding for operator-facing credential entry.

The only *enforced* passphrase policy is the length floor
(:data:`~cadrumo.adapters.persistence.storage.master_key.NIST_PASSPHRASE_MIN_LENGTH`),
which the master-key provider applies at the point of use. This module adds
the advisory band a credential surface renders beside the field so the
operator gets feedback while typing rather than a refusal after submitting.

The distinction is deliberate and load-bearing. NIST SP 800-63B §5.1.1.2
explicitly recommends *against* imposing composition rules — "verifiers
SHOULD NOT impose other composition rules for memorized secrets" — because
they push operators toward predictable substitutions without materially
raising entropy. So the character-class signal below feeds the advisory band
ONLY; it never gates. A long all-lowercase passphrase is accepted, and is
correctly banded as strong once it is long enough, because length is the
dominant entropy term.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

#: Length at which a passphrase is banded STRONG regardless of composition.
#: Grounded in the NIST SP 800-63B §5.1.1.2 guidance that length is the
#: primary entropy contributor and long memorized secrets should be
#: encouraged; a passphrase of this many characters is treated as strong
#: even when it uses a single character class.
LENGTH_ALONE_IS_STRONG: Final[int] = 20

#: Length at which a passphrase can reach STRONG with mixed character
#: classes, or FAIR on its own.
LENGTH_FAIR_FLOOR: Final[int] = 12


class PassphraseStrength(StrEnum):
    """Advisory band shown beside a passphrase field.

    Only :attr:`TOO_SHORT` corresponds to a refusal; it means the candidate
    is below the enforced NIST verifier minimum and the credential surface
    must not let it be submitted. The remaining members are guidance and
    never block: a :attr:`WEAK` passphrase is still accepted.
    """

    TOO_SHORT = "too_short"
    WEAK = "weak"
    FAIR = "fair"
    STRONG = "strong"


def character_class_count(candidate: str) -> int:
    """Return how many of the four character classes ``candidate`` uses.

    The classes are lowercase, uppercase, digit, and everything else
    (symbols and non-ASCII letters alike). Used only to lift a
    middling-length passphrase into a higher advisory band — never to
    refuse one, per the NIST guidance in this module's docstring.
    """
    return sum(
        (
            any(character.islower() for character in candidate),
            any(character.isupper() for character in candidate),
            any(character.isdigit() for character in candidate),
            any(not character.isalnum() for character in candidate),
        ),
    )


def assess_passphrase_strength(candidate: str, *, minimum_length: int) -> PassphraseStrength:
    """Band ``candidate`` for display beside a passphrase field.

    ``minimum_length`` is the enforced verifier minimum, supplied by the
    caller rather than imported here so this core module stays free of a
    dependency on the persistence adapter that owns the constant.

    A candidate shorter than the minimum is :attr:`PassphraseStrength.TOO_SHORT`
    — the one band that corresponds to a refusal. Above it, length dominates:
    a passphrase of :data:`LENGTH_ALONE_IS_STRONG` characters is strong on
    length alone, while a shorter one needs character-class variety to clear
    the same band.
    """
    length = len(candidate)
    if length < minimum_length:
        return PassphraseStrength.TOO_SHORT
    if length >= LENGTH_ALONE_IS_STRONG:
        return PassphraseStrength.STRONG
    if length >= LENGTH_FAIR_FLOOR:
        return PassphraseStrength.STRONG if character_class_count(candidate) >= 3 else PassphraseStrength.FAIR
    return PassphraseStrength.FAIR if character_class_count(candidate) >= 3 else PassphraseStrength.WEAK


__all__ = [
    "LENGTH_ALONE_IS_STRONG",
    "LENGTH_FAIR_FLOOR",
    "PassphraseStrength",
    "assess_passphrase_strength",
    "character_class_count",
]
