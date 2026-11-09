"""Private gross-reconstitution diagnostic helpers for transactions."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import NoReturn

from ...core.money.rounding import round_to_cents
from ..calculations.registry.governed_fact_scope import GovernedFactSource
from ..calculations.registry.iva_category_catalogue import registry_category_projection
from ..iva.schema import IvaCategory
from .enums import TransactionDirection
from .errors import TransactionValidationError
from .irpf_categories import (
    has_activity_irpf_category,
    has_non_work_irpf_category,
    has_rent_irpf_category,
    is_net_paid_related_category,
)
from .retencion_facts import maximum_supported_activity_retencion_rate


class GrossReconstitutionFinding(StrEnum):
    """What the gross/tax-substrate identity says about one row.

    The identity has one owner, so a reader that must decide before a write
    (a staged-work check) and the writer's own admission rule read the same
    answer instead of each carrying a copy of the arithmetic.
    """

    RECONSTITUTES = "reconstitutes"
    """The declared substrate reconstitutes the cash, or no substrate is declared."""

    SELF_ASSESSED_BASE_MISMATCH = "self_assessed_base_mismatch"
    """A self-assessed row's base misses the cash."""

    NEEDS_IRPF_CATEGORY = "needs_irpf_category"
    """The substrate is above the cash in a shape an IRPF category would settle, and none is declared."""

    WITHHOLDING_ABOVE_SUPPORTED_RATE = "withholding_above_supported_rate"
    """The inferred withholding exceeds the supported activity rate."""

    MISMATCH = "mismatch"
    """The substrate and the cash disagree, and no declared fact explains the gap."""


def _within_supported_activity_rate(
    *,
    taxable_base: Decimal,
    expected: Decimal,
    reconstituted: Decimal,
    irpf_category: str | None,
    direction: TransactionDirection,
    effective_date: date,
    authority: GovernedFactSource | None,
) -> bool:
    """Return whether an activity row's cash gap stays inside the supported rate."""
    if not has_activity_irpf_category(irpf_category, direction=direction, authority=authority):
        return True
    inferred_withholding = round_to_cents(reconstituted - expected)
    maximum_supported_withholding = round_to_cents(
        taxable_base * maximum_supported_activity_retencion_rate(effective_date=effective_date, authority=authority),
    )
    return inferred_withholding <= maximum_supported_withholding


def _withholding_shape_declared(
    *,
    category_id: str | None,
    irpf_category: str | None,
    direction: TransactionDirection,
    authority: GovernedFactSource | None,
) -> bool:
    """Return whether a declared IRPF category explains cash below the substrate.

    An incoming non-employment row, an outgoing professional-service row and
    an outgoing rent row are the three settled-net-of-withholding shapes.
    """
    if direction is TransactionDirection.INCOMING:
        return has_non_work_irpf_category(irpf_category, direction=direction, authority=authority)
    if direction is not TransactionDirection.OUTGOING or not is_net_paid_related_category(
        category_id, authority=authority
    ):
        return False
    return has_activity_irpf_category(
        irpf_category, direction=direction, authority=authority
    ) or has_rent_irpf_category(irpf_category, direction=direction, authority=authority)


def _withholding_shape_available(
    *, category_id: str | None, direction: TransactionDirection, authority: GovernedFactSource | None
) -> bool:
    """Return whether an IRPF category could legitimately explain this row's gap.

    Only where one of the three shapes is reachable is the missing fact named;
    a transfer or an uncategorised expense keeps the bare arithmetic refusal
    rather than pointing at a field that would not settle it.
    """
    if direction is TransactionDirection.INCOMING:
        return True
    return direction is TransactionDirection.OUTGOING and is_net_paid_related_category(category_id, authority=authority)


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


GROSS_NEEDS_WITHHOLDING_CATEGORY_MESSAGE_KEY = "errors.error.ledger_gross_above_cash_needs_withholding_category"
"""The sentence said for a substrate above the cash that a declared withholding category would settle."""

GROSS_NEEDS_WITHHOLDING_CATEGORY_DETAIL = (
    "the declared base and IVA exceed the cash movement; a declared withholding category accepts that gap"
)
"""The same refusal in untranslated text, which a traceback and a log carry."""

GROSS_NEEDS_WITHHOLDING_CATEGORY_FIELD = "irpf_category"
"""The field that settles it. A reader names it in its own typed field list, never in a sentence."""


def _raise_needs_withholding_category() -> NoReturn:
    """Raise the refusal that says what is missing instead of restating the arithmetic.

    The sentence carries no field identifier: the operator meets the fact, and a
    frontend leads to the column through :data:`GROSS_NEEDS_WITHHOLDING_CATEGORY_FIELD`.
    """
    raise TransactionValidationError(
        GROSS_NEEDS_WITHHOLDING_CATEGORY_DETAIL,
        translated_message=GROSS_NEEDS_WITHHOLDING_CATEGORY_MESSAGE_KEY,
    )


def gross_reconstitution_finding(
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
    authority: GovernedFactSource | None = None,
) -> GrossReconstitutionFinding:
    """Answer what the gross/tax-substrate identity says, without refusing anything.

    This is the one owner of the identity. The model validator turns the
    answer into its refusal, and a reader that must judge a row before it is
    written reads the same answer.
    """
    if taxable_base is None or iva_amount is None:
        return GrossReconstitutionFinding.RECONSTITUTES
    expected = round_to_cents(abs(raw_amount))
    if iva_category in registry_category_projection("self_assessed", authority=authority):
        if round_to_cents(taxable_base) != expected:
            return GrossReconstitutionFinding.SELF_ASSESSED_BASE_MISMATCH
        return GrossReconstitutionFinding.RECONSTITUTES
    reconstituted = round_to_cents(taxable_base + (iva_amount + (recargo_amount or Decimal("0"))))
    if reconstituted == expected:
        return GrossReconstitutionFinding.RECONSTITUTES
    # Only a substrate ABOVE the cash is the withholding shape; below it is
    # an unrecorded surcharge, which no IRPF category settles.
    if reconstituted < expected:
        return GrossReconstitutionFinding.MISMATCH
    if _withholding_shape_declared(
        category_id=category_id, irpf_category=irpf_category, direction=direction, authority=authority
    ):
        if _within_supported_activity_rate(
            taxable_base=taxable_base,
            expected=expected,
            reconstituted=reconstituted,
            irpf_category=irpf_category,
            direction=direction,
            effective_date=effective_date,
            authority=authority,
        ):
            return GrossReconstitutionFinding.RECONSTITUTES
        return GrossReconstitutionFinding.WITHHOLDING_ABOVE_SUPPORTED_RATE
    if _withholding_shape_available(category_id=category_id, direction=direction, authority=authority):
        return GrossReconstitutionFinding.NEEDS_IRPF_CATEGORY
    return GrossReconstitutionFinding.MISMATCH


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

    The model owns the fields, while :func:`gross_reconstitution_finding` owns
    the cohesive monetary invariant. This function is the thin boundary that
    turns its answer into the refusal the writer raises.
    """
    finding = gross_reconstitution_finding(
        raw_amount=raw_amount,
        taxable_base=taxable_base,
        iva_amount=iva_amount,
        recargo_amount=recargo_amount,
        iva_category=iva_category,
        direction=direction,
        category_id=category_id,
        irpf_category=irpf_category,
        effective_date=effective_date,
    )
    if finding is GrossReconstitutionFinding.RECONSTITUTES:
        return
    if taxable_base is None or iva_amount is None:  # pragma: no cover - a finding needs both
        return
    expected = round_to_cents(abs(raw_amount))
    if finding is GrossReconstitutionFinding.SELF_ASSESSED_BASE_MISMATCH:
        _raise_self_assessed_gross_mismatch(taxable_base=taxable_base, expected=expected)
    if finding is GrossReconstitutionFinding.WITHHOLDING_ABOVE_SUPPORTED_RATE:
        raise TransactionValidationError(
            "inferred IRPF withholding exceeds supported activity rate; cash amount may be invoice base without IVA",
        )
    if finding is GrossReconstitutionFinding.NEEDS_IRPF_CATEGORY:
        _raise_needs_withholding_category()
    recargo = recargo_amount or Decimal("0")
    _raise_gross_mismatch(
        taxable_base=taxable_base,
        iva_amount=iva_amount,
        recargo=recargo,
        recargo_amount=recargo_amount,
        direction=direction,
        category_id=category_id,
        reconstituted=round_to_cents(taxable_base + iva_amount + recargo),
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
        if is_net_paid_related_category(category_id):
            return ""
        return ""
    if direction == TransactionDirection.INCOMING:
        return ""
    return ""
