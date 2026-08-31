"""Printed-vs-derived IVA advisory cross-check.

A non-blocking diagnostic: when an invoice's on-host-extracted text appears to
print an IVA figure that disagrees with the registry-DERIVED IVA, surface an
advisory so the operator verifies before filing. The public
:func:`printed_iva_advisory` helper feeds the ``evidence_advisory`` field on
:class:`cadrumo.application.ledger.llm_classification.LLMSaturatedSuggestion`
after the saturation path has resolved evidence through
:class:`cadrumo.domain.transactions.PromptSpec`.

The printed figure is parsed deterministically on-host from the evidence text
(never emitted by the model) and is used ONLY for this advisory -- it is never
persisted and never overrides the derived value
(llm-selects-system-derives-tax-numbers / no-silent-under-declaration). Parsing
is best-effort; a miss simply yields no advisory.
"""

from __future__ import annotations

import re
from decimal import Decimal

from ...core.decimal._coerce import coerce_finite_european_decimal

__all__ = ["printed_iva_advisory"]

# "IVA" followed (within a short gap) by a Spanish- or plain-formatted amount.
_IVA_AMOUNT = re.compile(
    r"\bIVA\b[^\d-]{0,12}(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2}|\d+(?:\.\d{1,2})?)",
    re.IGNORECASE,
)


def _parse_amount(raw: str) -> Decimal | None:
    """Parse a Spanish- or plain-formatted :class:`~decimal.Decimal` string, best-effort.

    The EXTRACTION contract, read from the canonical home rather than
    re-implemented here. This function previously spelled out the same
    normalise-then-construct sequence inline, which is how it came to disagree
    with the rest of the codebase: a printed ``8.000`` was read as eight euros,
    because the thousands strip only fires when a comma is present to settle
    the convention. The canonical helper drops a token whose reading cannot be
    settled, so the advisory reports nothing rather than a figure a thousandfold
    out, and the operator is asked instead.
    """
    return coerce_finite_european_decimal(raw)


def printed_iva_advisory(
    evidence_text: str | None,
    derived_iva_amount: Decimal | None,
    *,
    tolerance: Decimal = Decimal("0.01"),
) -> str | None:
    """Return an advisory string when the printed IVA disagrees with the derived IVA.

    The comparison is a best-effort cross-check between on-host-extracted
    evidence text and the registry-derived IVA amount carried by
    :class:`cadrumo.application.ledger.llm_classification.LLMSaturatedSuggestion`;
    it never supplies a tax value for persistence.

    Args:
        evidence_text: On-host-extracted text of the attached evidence, or ``None``.
        derived_iva_amount: The registry-derived :class:`~decimal.Decimal` IVA
            amount, or ``None``.
        tolerance: Absolute cent :class:`~decimal.Decimal` tolerance for the
            comparison.

    Returns:
        A non-blocking advisory message when a printed IVA figure is found and
        differs from ``derived_iva_amount`` beyond ``tolerance``; otherwise ``None``
        (no evidence, no derived value, no parseable printed figure, or a match).
    """
    if not evidence_text or derived_iva_amount is None:
        return None
    match = _IVA_AMOUNT.search(evidence_text)
    if match is None:
        return None
    printed = _parse_amount(match.group(1))
    if printed is None:
        return None
    if abs(printed - derived_iva_amount) > tolerance:
        return (
            f"the attached evidence appears to print an IVA of {printed} but the registry-derived "
            f"IVA is {derived_iva_amount}; verify the classification before filing (advisory only -- "
            f"the derived value is authoritative)"
        )
    return None
