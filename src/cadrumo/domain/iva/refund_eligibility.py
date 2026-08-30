"""Modelo 303 refund (devolución) disposition eligibility.

A negative Modelo 303 result may be elected as a refund — fichero "Tipo de
declaración" code ``D`` (solicitud de devolución) — only when the taxpayer is
inscribed in the Registro de devolución mensual (REDEME, art. 30 RD 1624/1992),
which makes a monthly refund available *every* period, OR when the period is the
last filing period of the year (the annual liquidación). Outside those two cases
the only lawful negative disposition is compensación — code ``C``, a credit
carried forward. The operator may always carry forward; the refund is the gated
election.

This module is the law-determined eligibility gate of the REDEME company refund
schema. It is a pure predicate over the typed ``redeme_enrolled`` axis and the
:class:`~core.Period` — it raises no error and resolves no locale, so it has
no dependency on the result-disposition serialization framework or on operator
message catalogues; a consumer layers the operator-facing election + refusal on
top. The ``reason`` it returns is a machine code, not operator-facing prose.

Legal basis: RD 1624/1992 (RIVA) art. 30 (Registro de devolución mensual);
Ley 37/1992 (LIVA) art. 116 (the monthly-refund right of an inscribed taxpayer).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

from ...core.period import Period, StandardPeriodCode

#: The last Modelo 303 filing-period codes of a year, after which a negative
#: result may be requested as a refund: ``4T`` (quarterly cadence), ``12`` (monthly
#: cadence), ``0A`` (annual). Membership is the "annual liquidación" condition.
LAST_FILING_PERIOD_TOKENS: Final[frozenset[StandardPeriodCode]] = frozenset(
    {
        StandardPeriodCode.Q4,
        StandardPeriodCode.DEC,
        StandardPeriodCode.ANNUAL,
    },
)


class RefundEligibilityReason(StrEnum):
    """Why a Modelo 303 refund (devolución) is or is not available for a period.

    A machine code (not operator-facing prose) that a consumer maps to a grounded
    message. ``REDEME_INSCRIBED`` and ``LAST_PERIOD_OF_YEAR`` permit the ``D``
    election; ``NOT_ELIGIBLE`` permits only compensación (``C``).
    """

    REDEME_INSCRIBED = "redeme_inscribed"
    LAST_PERIOD_OF_YEAR = "last_period_of_year"
    NOT_ELIGIBLE = "not_eligible"


def is_last_filing_period_of_year(period: Period) -> bool:
    """Return whether ``period`` is the last Modelo 303 filing period of its year."""
    return period.registry_token in LAST_FILING_PERIOD_TOKENS


def refund_disposition_available(*, redeme_enrolled: bool, period: Period) -> bool:
    """Return whether a refund (devolución, ``D``) may be elected for a negative result.

    ``True`` iff the taxpayer is REDEME-inscribed (art. 30 RD 1624/1992 — monthly
    refund, available every period) OR ``period`` is the last filing period of the
    year (the annual refund, Ley 37/1992 art. 116). Otherwise only compensación
    (``C``) is lawful and this returns ``False``.
    """
    return redeme_enrolled or is_last_filing_period_of_year(period)


def refund_eligibility_reason(*, redeme_enrolled: bool, period: Period) -> RefundEligibilityReason:
    """Classify the refund eligibility of a Modelo 303 period as a machine reason code.

    REDEME enrolment takes precedence (it makes the refund available every period);
    otherwise the last-period condition; otherwise ``NOT_ELIGIBLE`` (carry forward).
    The consumer maps the code to a grounded operator message.

    Returns:
        The :class:`RefundEligibilityReason` for the supplied period.
    """
    if redeme_enrolled:
        return RefundEligibilityReason.REDEME_INSCRIBED
    if is_last_filing_period_of_year(period):
        return RefundEligibilityReason.LAST_PERIOD_OF_YEAR
    return RefundEligibilityReason.NOT_ELIGIBLE
