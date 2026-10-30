"""Read eligible acquisition candidates from the activity-asset ledger."""

from __future__ import annotations

from decimal import Decimal

from ...core.external_constants import DEFAULT_CURRENCY
from ...domain.calculations.registry.prorrata_vocabulary import resolve_input_classification_definition
from ...domain.renta.actividad_asset.claims import current_revisions
from ...domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ...domain.transactions.models import Transaction, TransactionCatalogue
from ..operations.public_scalar import PublicDecimal, project_scalar
from .activity_asset_read_models import (
    NON_DEDUCTIBLE_IVA_STATE_FAMILY,
    ActivityAssetAcquisitionCandidate,
    ActivityAssetNonDeductibleIvaState,
    activity_asset_label_key,
)
from .history import ActivityAssetHistory


def _amount(value: Decimal) -> PublicDecimal:
    return project_scalar(value)


def _optional_amount(value: Decimal | None) -> PublicDecimal | None:
    return None if value is None else _amount(value)


def acquisition_candidates(
    catalogue: TransactionCatalogue,
    history: ActivityAssetHistory,
) -> tuple[ActivityAssetAcquisitionCandidate, ...]:
    """List the business payments in a :class:`TransactionCatalogue` not yet named as acquisitions.

    The candidates are returned newest first.

    Returns:
        One candidate per row.  What the ledger does not know is null, never zero.
    """
    owned = {
        transaction_id
        for revision in current_revisions(history.revisions).values()
        for transaction_id in revision.acquisition_transaction_ids
    }
    rows = (
        row
        for row in catalogue.transactions.values()
        if row.direction is TransactionDirection.OUTGOING
        and row.lifecycle_state is TransactionLifecycleState.ACTIVE
        and row.business_classification in {BusinessClassification.BUSINESS, BusinessClassification.MIXED}
        and row.transaction_id not in owned
    )
    return tuple(
        _candidate(row)
        for row in sorted(rows, key=lambda item: (item.raw.booked_date, item.transaction_id), reverse=True)
    )


def _non_deductible_iva(row: Transaction) -> Decimal | None:
    """Read the row's non-deductible IVA from its classification; anything else stays unknown."""
    if row.iva_amount is None or row.input_classification is None or row.raw.currency != DEFAULT_CURRENCY:
        return None
    definition = resolve_input_classification_definition(row.input_classification)
    if definition.uses_general_percentage or definition.deductible_percentage is None:
        return None
    if definition.deductible_percentage == Decimal("100"):
        return Decimal("0.00")
    if definition.deductible_percentage == Decimal("0"):
        return row.iva_amount
    return None


def _candidate(row: Transaction) -> ActivityAssetAcquisitionCandidate:
    non_deductible = _non_deductible_iva(row)
    state = (
        ActivityAssetNonDeductibleIvaState.UNKNOWN
        if non_deductible is None
        else ActivityAssetNonDeductibleIvaState.KNOWN
    )
    evidence_id = row.purchase_invoice_evidence_id
    paid = row.raw.amount if row.raw.currency == DEFAULT_CURRENCY else row.value_in_eur
    return ActivityAssetAcquisitionCandidate(
        transaction_id=row.transaction_id,
        booked_date=row.raw.booked_date,
        description=row.raw.description,
        amount=_amount(row.raw.amount),
        currency=row.raw.currency,
        paid_in_euro=_optional_amount(paid),
        taxable_base=_optional_amount(row.taxable_base),
        iva_amount=_optional_amount(row.iva_amount),
        non_deductible_iva_state=state,
        non_deductible_iva_state_key=activity_asset_label_key(NON_DEDUCTIBLE_IVA_STATE_FAMILY, state),
        non_deductible_iva=_optional_amount(non_deductible),
        invoice_evidence_id=evidence_id,
        evidence_fingerprint=evidence_id if _is_digest(evidence_id) else None,
    )


def _is_digest(value: str | None) -> bool:
    return value is not None and len(value) == 64 and all(char in "0123456789abcdef" for char in value)
