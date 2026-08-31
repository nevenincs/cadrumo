"""Private gross-reconstitution diagnostic helpers for transactions."""

from __future__ import annotations

from decimal import Decimal

from .enums import TransactionDirection
from .irpf_categories import (
    PROFESSIONAL_SERVICE_CATEGORIES_PAID_NET_OF_WITHHOLDING,
    RENT_CATEGORIES_PAID_NET_OF_WITHHOLDING,
)


def _gross_mismatch_detail(
    *,
    direction: TransactionDirection,
    category_id: str | None,
    recargo_amount: Decimal | None,
    reconstituted: Decimal,
    expected: Decimal,
) -> str:
    """Build the operator hint appended to a gross-reconstitution refusal.

    Each branch names the one field that would legitimately explain the gap it
    sees, so the refusal is actionable rather than a bare arithmetic mismatch
    the operator has to decompose. The direction of the gap selects the
    vocabulary: a substrate *above* the cash is the withholding shape, and a
    substrate *below* it is the unrecorded-surcharge shape. Returns the empty
    string when no branch recognises the gap, which leaves the arithmetic to
    speak for itself rather than guessing.
    """
    if reconstituted < expected:
        if recargo_amount is not None:
            return ""
        return (
            " The cash movement is above the declared substrate. If this is a supply to or "
            "from a comerciante minorista under recargo de equivalencia (LIVA art. 161), the "
            "surcharge is part of what was charged: record it with --recargo-amount so the "
            "gross reconstitutes."
        )
    if reconstituted <= expected:
        return ""
    if direction == TransactionDirection.OUTGOING:
        if category_id in RENT_CATEGORIES_PAID_NET_OF_WITHHOLDING:
            return ""
        if category_id in PROFESSIONAL_SERVICE_CATEGORIES_PAID_NET_OF_WITHHOLDING:
            return ""
        return ""
    if direction == TransactionDirection.INCOMING:
        return ""
    return ""
