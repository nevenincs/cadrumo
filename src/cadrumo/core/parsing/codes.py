"""Canonical normalisers for the inbound ISO code tokens ledger records carry.

Currency (ISO 4217) and source jurisdiction (ISO 3166-1 alpha-2) both arrive
as free text from bank exports, operator input, and CLI options, and both are
persisted on ledger records. Each previously carried a per-boundary copy of
its shape check, so the same token could be accepted at one boundary and
refused at the next.

These are pure functions at the ``core`` layer. They raise
:class:`~core.errors.CoreValidationError` — a :class:`ValueError` subclass, so
a Pydantic validator delegating here reports a normal validation failure —
and each caller re-raises its own domain error to keep operator diagnostics
boundary-specific.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BeforeValidator

from ..errors.hierarchy import CoreValidationError

_ISO_4217_LENGTH: int = 3
_ISO_3166_ALPHA2_LENGTH: int = 2


def normalise_iso_4217_currency(value: object) -> str:
    """Normalise a raw currency token to its uppercase ISO 4217 code.

    Trims surrounding whitespace and uppercases before the shape check, so a
    padded or lowercase source cell (``" usd "``) normalises to ``"USD"``
    rather than being refused for its padding. Callers that validate through
    Pydantic must run this as a ``mode="before"`` validator: a bare
    ``min_length`` / ``max_length`` field constraint fires on the padding
    first and never reaches the normaliser.

    Args:
        value: Raw currency token from a bank export, OFX statement header,
            operator input, or persisted payload.

    Returns:
        The three-letter uppercase ISO 4217 code.

    Raises:
        CoreValidationError: The token is not exactly three alphabetic
            characters once trimmed.
    """
    normalised = str(value).strip().upper()
    if len(normalised) != _ISO_4217_LENGTH or not normalised.isalpha():
        raise CoreValidationError("currency must be a three-letter ISO 4217 code")
    return normalised


def normalise_iso_3166_alpha2_jurisdiction(value: str | None) -> str | None:
    """Validate a source-jurisdiction token as an ISO 3166-1 alpha-2 code.

    Trims surrounding whitespace, then requires exactly two alphabetic
    characters that are **already uppercase**. Unlike
    :func:`normalise_iso_4217_currency` this deliberately refuses a lowercase
    token rather than folding it: the jurisdiction axis selects the
    regulatory-source treatment of a ledger row (Spanish-source versus
    foreign-source), so a caller that supplies ``"es"`` is told to declare the
    canonical code rather than having one guessed for it.

    Args:
        value: Raw jurisdiction token, or ``None`` when the record explicitly
            declares the jurisdiction unknown.

    Returns:
        The trimmed uppercase alpha-2 code, or ``None`` when ``value`` is
        ``None``.

    Raises:
        CoreValidationError: The token is not exactly two uppercase
            alphabetic characters once trimmed.
    """
    if value is None:
        return None
    normalised = value.strip()
    if len(normalised) != _ISO_3166_ALPHA2_LENGTH or not normalised.isalpha() or normalised != normalised.upper():
        raise CoreValidationError(
            "source_jurisdiction must be a two-letter ISO 3166-1 alpha-2 uppercase code",
        )
    return normalised


IsoCurrencyCode = Annotated[str, BeforeValidator(normalise_iso_4217_currency)]
"""A three-letter uppercase ISO 4217 code, normalised before it is checked.

The normalisation has to happen BEFORE the shape check, which is why this is a
``BeforeValidator`` and not a pattern. :func:`normalise_iso_4217_currency` says
so in its own docstring: a bare ``min_length`` / ``max_length`` field constraint
fires on the padding first and never reaches the normaliser, so `` usd `` is
refused for its spaces rather than accepted as ``USD``.

Three sites had written the shape out instead, in three different strengths --
a length-only bound that accepted ``eur`` and ``$$$``, and two hand-rolled
``^[A-Z]{3}$`` patterns that refused padding the normaliser exists to absorb.
"""

__all__ = [
    "IsoCurrencyCode",
    "normalise_iso_3166_alpha2_jurisdiction",
    "normalise_iso_4217_currency",
]
