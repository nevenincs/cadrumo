"""Resolve selected manual classification fields against one pinned catalogue."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import cast

from ...core.decimal.grammar import try_parse_canonical_decimal
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.eu_member_state_catalogue import require_eu_member_state
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.calculations.registry.iva_category_catalogue import require_iva_category
from ...domain.calculations.registry.iva_deduction_catalogue import require_iva_deduction_fact_kind
from ...domain.categories.spending_category_catalogue import require_spending_category
from ...domain.transactions.enums import BusinessClassification
from ...domain.transactions.errors import TransactionValidationError
from ...domain.transactions.m210_income_classification import M210IncomeClassification
from ...domain.transactions.models import Transaction, TransactionCatalogue
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .classify_requests import (
    LedgerClassifyRequest,
)
from .m210_classification import resolve_m210_income_classification
from .models import (
    ManualLedgerTransactionPatch,
)


@dataclass(frozen=True, slots=True)
class _LoadedCatalogueView:
    """Expose the already-loaded COMMIT snapshot to the canonical M210 resolver."""

    bucket_id: str
    catalogue: TransactionCatalogue

    def load(self) -> TransactionCatalogue:
        """Return the exact catalogue snapshot already held by the executor."""
        return self.catalogue


def decode_classification_decimal_option(value: str | None, field_name: str) -> Decimal | None:
    """Decode one optional canonical decimal wire value."""
    if value is None:
        return None
    parsed = try_parse_canonical_decimal(value, signed=False)
    if parsed is None:
        raise TransactionValidationError(f"M210 {field_name} must be canonical decimal text")
    return parsed


def _resolve_manual_field_value(
    field_name: str,
    payload: LedgerClassifyRequest,
    *,
    current: Transaction,
    operation: PinnedAuthorityOperation,
) -> object:
    value = getattr(payload.patch, field_name)
    if value is None:
        return None
    if field_name == "business_classification":
        return BusinessClassification(value)
    if field_name in {"business_pct", "taxable_base", "iva_rate", "iva_amount"}:
        parsed = try_parse_canonical_decimal(value, signed=False)
        if parsed is None:
            raise TransactionValidationError(f"ledger classify {field_name} must be canonical decimal text")
        return parsed
    if field_name == "category_id":
        normalized = value.strip()
        return require_spending_category(normalized, authority=operation).value if normalized else None
    if field_name == "iva_category":
        return require_iva_category(value, effective_date=current.raw.booked_date, authority=operation)
    if field_name == "deduction_fact_kind":
        return require_iva_deduction_fact_kind(value, authority=operation)
    if field_name == "counterparty_identification_state":
        return require_eu_member_state(value, authority=operation)
    return value


def _resolve_m210_classification(
    payload: LedgerClassifyRequest,
    *,
    bucket_id: str,
    transaction_id: str,
    operation: PinnedAuthorityOperation,
    catalogue: TransactionCatalogue,
) -> M210IncomeClassification | None:
    if payload.m210 is None:
        return None
    m210 = payload.m210
    gross_income_amount = decode_classification_decimal_option(m210.gross_income_amount, "gross_income_amount")
    applicable_rate = decode_classification_decimal_option(m210.applicable_rate, "applicable_rate")
    snapshot = cast(
        TransactionCatalogueRepositoryProtocol,
        _LoadedCatalogueView(bucket_id=bucket_id, catalogue=catalogue),
    )
    with validating_governed_facts(operation):
        return resolve_m210_income_classification(
            bucket_id=bucket_id,
            transaction_id=transaction_id,
            tipo_renta_code=m210.tipo_renta_code,
            gross_income_amount=gross_income_amount,
            applicable_rate=applicable_rate,
            payer_mode=m210.payer_mode,
            payer_id=m210.payer_id,
            asset_or_right_id=m210.asset_or_right_id,
            transaction_repository=snapshot,
        )


def _validate_patch_selection(
    patch: ManualLedgerTransactionPatch,
    payload: LedgerClassifyRequest,
    transaction_id: str,
) -> ManualLedgerTransactionPatch:
    if set(patch.model_fields_set) != set(payload.patch_fields):
        raise TransactionValidationError(
            "ledger classify request omission mask does not match its canonical patch",
            context={"transaction_id": transaction_id},
        )
    return patch


def build_manual_classification_patch(
    payload: LedgerClassifyRequest,
    *,
    bucket_id: str,
    transaction_id: str,
    current: Transaction,
    operation: PinnedAuthorityOperation,
    catalogue: TransactionCatalogue,
) -> ManualLedgerTransactionPatch:
    """Rebuild the typed canonical patch under the selected registry authority.

    Parameter types: ``catalogue`` (:class:`~cadrumo.domain.transactions.models.TransactionCatalogue`).
    """
    if not isinstance(current, Transaction):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    patch_values: dict[str, object] = {}
    for field_name in payload.patch_fields:
        if field_name == "m210_income_classification":
            continue
        patch_values[field_name] = _resolve_manual_field_value(
            field_name,
            payload,
            current=current,
            operation=operation,
        )
    classification = _resolve_m210_classification(
        payload,
        bucket_id=bucket_id,
        transaction_id=transaction_id,
        operation=operation,
        catalogue=catalogue,
    )
    if classification is not None:
        patch_values["m210_income_classification"] = classification
    patch = ManualLedgerTransactionPatch.model_validate(patch_values)
    return _validate_patch_selection(patch, payload, transaction_id)
