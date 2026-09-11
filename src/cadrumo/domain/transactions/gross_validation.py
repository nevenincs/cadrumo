"""Private gross-reconstitution diagnostic helpers for transactions."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import NoReturn

from ...core.money.rounding import round_to_cents
from ..iva.schema import IvaCategory
from .enums import TransactionDirection
from .errors import TransactionValidationError
from .irpf_categories import (
    PROFESSIONAL_SERVICE_CATEGORIES_PAID_NET_OF_WITHHOLDING,
    RENT_CATEGORIES_PAID_NET_OF_WITHHOLDING,
    has_activity_irpf_category,
    has_non_work_irpf_category,
    has_rent_irpf_category,
)
from .retencion_facts import maximum_supported_activity_retencion_rate

_SELF_ASSESSED_IVA_CATEGORIES: frozenset[IvaCategory] = frozenset(
    {
        IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
        IvaCategory.DOMESTIC_REVERSE_CHARGE,
        IvaCategory.IMPORT_THIRD_COUNTRY,
    },
)


def _activity_withholding_is_supported(
    *,
    taxable_base: Decimal,
    expected: Decimal,
    reconstituted: Decimal,
    irpf_category: str | None,
    direction: TransactionDirection,
    effective_date: date,
) -> bool:
    """Refuse an activity row whose cash gap exceeds the supported rate."""
    if not has_activity_irpf_category(irpf_category, direction=direction):
        return True
    inferred_withholding = round_to_cents(reconstituted - expected)
    maximum_supported_withholding = round_to_cents(
        taxable_base * maximum_supported_activity_retencion_rate(effective_date=effective_date),
    )
    if inferred_withholding > maximum_supported_withholding:
        raise TransactionValidationError(
            "inferred IRPF withholding exceeds supported activity rate; cash amount may be invoice base without IVA",
        )
    return True


def _incoming_withholding_is_supported(
    *,
    taxable_base: Decimal,
    expected: Decimal,
    reconstituted: Decimal,
    irpf_category: str | None,
    direction: TransactionDirection,
    effective_date: date,
) -> bool:
    """Recognise an incoming non-work row settled net of withholding."""
    if (
        direction is not TransactionDirection.INCOMING
        or not has_non_work_irpf_category(irpf_category, direction=direction)
        or reconstituted <= expected
    ):
        return False
    return _activity_withholding_is_supported(
        taxable_base=taxable_base,
        expected=expected,
        reconstituted=reconstituted,
        irpf_category=irpf_category,
        direction=direction,
        effective_date=effective_date,
    )


def _outgoing_professional_withholding_is_supported(
    *,
    taxable_base: Decimal,
    expected: Decimal,
    reconstituted: Decimal,
    category_id: str | None,
    irpf_category: str | None,
    direction: TransactionDirection,
    effective_date: date,
) -> bool:
    """Recognise an outgoing professional-service row settled net of withholding."""
    if (
        direction is not TransactionDirection.OUTGOING
        or category_id not in PROFESSIONAL_SERVICE_CATEGORIES_PAID_NET_OF_WITHHOLDING
        or not has_activity_irpf_category(irpf_category, direction=direction)
        or reconstituted <= expected
    ):
        return False
    return _activity_withholding_is_supported(
        taxable_base=taxable_base,
        expected=expected,
        reconstituted=reconstituted,
        irpf_category=irpf_category,
        direction=direction,
        effective_date=effective_date,
    )


def _outgoing_rent_withholding_is_supported(
    *,
    category_id: str | None,
    irpf_category: str | None,
    direction: TransactionDirection,
    reconstituted: Decimal,
    expected: Decimal,
) -> bool:
    """Recognise an outgoing rent row settled net of withholding."""
    return (
        direction is TransactionDirection.OUTGOING
        and category_id in RENT_CATEGORIES_PAID_NET_OF_WITHHOLDING
        and has_rent_irpf_category(irpf_category, direction=direction)
        and reconstituted > expected
    )


def _raise_self_assessed_gross_mismatch(*, taxable_base: Decimal, expected: Decimal) -> NoReturn:
    """Raise the refusal for a self-assessed row whose base misses cash."""
    raise TransactionValidationError(
        f"taxable_base must equal the gross to the cent for self-assessed IVA: {taxable_base} != {expected}",
    )


def _raise_gross_mismatch(
    *,
    taxable_base: Decimal,
    iva_amount: Decimal,
    recargo: Decimal,
    recargo_amount: Decimal | None,
    direction: TransactionDirection,
    category_id: str | None,
    reconstituted: Decimal,
    expected: Decimal,
) -> NoReturn:
    """Raise the ordinary gross-reconstitution refusal with its operator detail."""
    detail = gross_mismatch_detail(
        direction=direction,
        category_id=category_id,
        recargo_amount=recargo_amount,
        reconstituted=reconstituted,
        expected=expected,
    )
    raise TransactionValidationError(
        "taxable_base + iva_amount + recargo_amount must equal the gross to the cent: "
        f"{taxable_base} + {iva_amount} + {recargo} = {reconstituted} != {expected}.{detail}",
    )


def validate_gross_reconstitution(
    *,
    raw_amount: Decimal,
    taxable_base: Decimal | None,
    iva_amount: Decimal | None,
    recargo_amount: Decimal | None,
    iva_category: IvaCategory | None,
    direction: TransactionDirection,
    category_id: str | None,
    irpf_category: str | None,
    effective_date: date,
) -> None:
    """Validate the transaction's gross/tax-substrate identity.

    The model owns the fields, while this function owns the cohesive monetary
    invariant. Keeping the branches here makes the model validator a thin
    boundary adapter without changing the order or wording of any refusal.
    """
    if taxable_base is None or iva_amount is None:
        return
    expected = round_to_cents(abs(raw_amount))
    if iva_category in _SELF_ASSESSED_IVA_CATEGORIES:
        reconstituted = round_to_cents(taxable_base)
        if reconstituted != expected:
            _raise_self_assessed_gross_mismatch(taxable_base=taxable_base, expected=expected)
        return
    recargo = recargo_amount or Decimal("0")
    reconstituted = round_to_cents(taxable_base + iva_amount + recargo)
    if reconstituted == expected:
        return
    if _incoming_withholding_is_supported(
        taxable_base=taxable_base,
        expected=expected,
        reconstituted=reconstituted,
        irpf_category=irpf_category,
        direction=direction,
        effective_date=effective_date,
    ):
        return
    if _outgoing_professional_withholding_is_supported(
        taxable_base=taxable_base,
        expected=expected,
        reconstituted=reconstituted,
        category_id=category_id,
        irpf_category=irpf_category,
        direction=direction,
        effective_date=effective_date,
    ):
        return
    if _outgoing_rent_withholding_is_supported(
        category_id=category_id,
        irpf_category=irpf_category,
        direction=direction,
        reconstituted=reconstituted,
        expected=expected,
    ):
        return
    _raise_gross_mismatch(
        taxable_base=taxable_base,
        iva_amount=iva_amount,
        recargo=recargo,
        recargo_amount=recargo_amount,
        direction=direction,
        category_id=category_id,
        reconstituted=reconstituted,
        expected=expected,
    )


def gross_mismatch_detail(
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
