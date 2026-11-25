"""Which modelos the law lets pay their result in two instalments, and the first instalment's share.

The registry declares both in the dated ``payment-instalment-split`` fact,
grounded in Ley 35/2006 art. 97.2 and RD 439/2007 art. 62.2 as the Orden
approving the Modelo 100 of each ejercicio and the Manual práctico de Renta of
that ejercicio restate them. The fact is read on the declaration's own period,
so a period the fact does not cover declares no split.

No official source says how an instalment that is not a whole number of cents
is rounded, so the fact declares no rounding: the split
:func:`~cadrumo.core.payment_instalment_election.instalment_amounts` works to
the cent is Cadrumo's own, and every consumer serves it as advisory.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Final

from .errors import GovernedFactNotApplicableError, RegistryValidationError
from .facts.string_mapping import MappingValueWhitespace, StringMappingFact, StringMappingPolicy
from .form_codes import FormCodes
from .governed_fact_scope import GovernedFactSource
from .schema_base import DateAxis

_SPLIT_FACT: Final = "payment-instalment-split"
_FACT: Final = StringMappingFact(
    fact_id=_SPLIT_FACT,
    date_axis=DateAxis.FILING_PERIOD,
    policy=StringMappingPolicy(
        subject=f"fact {_SPLIT_FACT!r}",
        value_whitespace=MappingValueWhitespace.STRIP,
    ),
)


def _split_codes(period_day: date, authority: GovernedFactSource | None) -> FormCodes | None:
    """The fact as it stands for the period holding ``period_day``; ``None`` where the law authors no split."""
    try:
        entries = _FACT.resolve_scoped_entries(effective_date=period_day, authority=authority)
    except GovernedFactNotApplicableError:
        return None
    return FormCodes(fact_id=_SPLIT_FACT, entries=entries)


def two_instalments_declared(modelo: str, *, period_day: date, authority: GovernedFactSource | None = None) -> bool:
    """Return whether ``modelo``'s positive result in the period holding ``period_day`` may be split in two."""
    codes = _split_codes(period_day, authority)
    return codes is not None and modelo in codes.codes("modelos")


def first_instalment_share(
    modelo: str, *, period_day: date, authority: GovernedFactSource | None = None
) -> Decimal | None:
    """Return the share of the amount paid as the first instalment, or ``None`` when no split is declared.

    Raises:
        RegistryValidationError: The fact declares a share that is not a fraction between nought and one.
    """
    codes = _split_codes(period_day, authority)
    if codes is None or modelo not in codes.codes("modelos"):
        return None
    raw = codes.code("first_instalment_share")
    try:
        share = Decimal(raw)
    except InvalidOperation as exc:
        raise RegistryValidationError(f"fact {_SPLIT_FACT!r} first_instalment_share is not a number: {raw!r}") from exc
    if not Decimal(0) < share < Decimal(1):
        raise RegistryValidationError(f"fact {_SPLIT_FACT!r} first_instalment_share is not a fraction: {raw!r}")
    return share


__all__ = ["first_instalment_share", "two_instalments_declared"]
