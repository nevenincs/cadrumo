"""CLI transport bridge for worker-owned single-transaction classification."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import cast

import typer

from ...application.ledger.actions_common import display_decimal
from ...application.ledger.classify_operation import (
    LEDGER_CLASSIFY_OPERATION_DEFINITION_ID,
    LEDGER_CLASSIFY_VALIDATION_REFUSAL_CODE,
    LedgerClassifyM210Options,
    LedgerClassifyOperationResult,
    LedgerClassifyPatch,
    LedgerClassifyPatchField,
    LedgerClassifyRequest,
)
from ...application.ledger.models import ManualLedgerTransactionPatch
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.transactions.enums import BusinessClassification
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import run_registered_operation, submitted_operation_error


def run_ledger_classify(
    ctx: typer.Context,
    *,
    transaction_id: str,
    classification: BusinessClassification,
    patch: ManualLedgerTransactionPatch,
    business_pct: Decimal | None,
    m210_tipo_renta_code: str | None,
    m210_gross_income_amount: Decimal | None,
    m210_applicable_rate: Decimal | None,
    m210_payer_mode: str | None,
    m210_payer_id: str | None,
    m210_asset_or_right_id: str | None,
    actor: str | None,
    reaffirm: bool,
) -> LedgerClassifyOperationResult:
    """Submit one exact-profile classify and correlate its result and effect."""
    client = bound_profile_client(ctx)
    patch_fields = cast(tuple[LedgerClassifyPatchField, ...], tuple(sorted(patch.model_fields_set)))
    wire_patch = LedgerClassifyPatch.model_validate(
        {field: _wire_patch_value(getattr(patch, field)) for field in patch_fields},
    )
    raw_m210 = (
        m210_tipo_renta_code,
        m210_gross_income_amount,
        m210_applicable_rate,
        m210_payer_mode,
        m210_payer_id,
        m210_asset_or_right_id,
    )
    m210 = None
    m210_answers_requested = any(value is not None for value in raw_m210[:4])
    if any(value is not None for value in raw_m210):
        m210 = LedgerClassifyM210Options(
            tipo_renta_code=m210_tipo_renta_code,
            gross_income_amount=(
                display_decimal(m210_gross_income_amount) if m210_gross_income_amount is not None else None
            ),
            applicable_rate=display_decimal(m210_applicable_rate) if m210_applicable_rate is not None else None,
            payer_mode=m210_payer_mode,
            payer_id=m210_payer_id,
            asset_or_right_id=m210_asset_or_right_id,
        )
    selected_fields = set[LedgerClassifyPatchField](patch_fields)
    if m210_answers_requested:
        selected_fields.add(cast(LedgerClassifyPatchField, "m210_income_classification"))
    selected_patch_fields = tuple(sorted(selected_fields))
    request = LedgerClassifyRequest(
        profile_id=client.profile_id,
        transaction_id=transaction_id,
        patch=wire_patch,
        patch_fields=selected_patch_fields,
        m210=m210,
        actor=actor if actor else None,
        reaffirm=reaffirm,
    )
    completed = run_registered_operation(
        client,
        request,
        definition_id=LEDGER_CLASSIFY_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=LedgerClassifyOperationResult,
        request_version=1,
        result_version=1,
        timeout=120,
        allow_refusal_detail=True,
    )
    projection = completed.projection
    if projection.outcome == "validation_error":
        invalid_refusal = (
            completed.terminal_condition is not OperationTerminalCondition.REFUSED
            or completed.refusal_code != LEDGER_CLASSIFY_VALIDATION_REFUSAL_CODE
            or completed.effect is not OperationEffect.NONE
            or projection.profile_id != client.profile_id
            or not projection.validation_messages
        )
        if invalid_refusal:
            raise submitted_operation_error(
                completed.operation_id,
                RuntimeRefusalCode.INVALID_FRAME.value,
                terminal_condition=completed.terminal_condition,
                effect=completed.effect,
                refusal_code=completed.refusal_code,
            )
        if completed.effect is not OperationEffect.NONE or projection.bucket_event_ids:
            raise submitted_operation_error(
                completed.operation_id,
                RuntimeRefusalCode.INVALID_FRAME.value,
                terminal_condition=completed.terminal_condition,
                effect=completed.effect,
                refusal_code=completed.refusal_code,
            )
        return projection
    transaction = projection.transaction
    if transaction is None or projection.review_status is None:
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        )
    prefix = transaction_id.strip().lower()
    expected_classification = classification.value
    expected_business_pct = (
        display_decimal(business_pct)
        if classification is BusinessClassification.MIXED and business_pct is not None
        else None
    )
    expected_effect = OperationEffect.UPDATED if projection.bucket_event_ids else OperationEffect.NONE
    invalid = (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not expected_effect
        or projection.profile_id != client.profile_id
        or not transaction.transaction_id.startswith(prefix)
        or transaction.business_classification != expected_classification
        or transaction.business_pct != expected_business_pct
        or not _matches_selected_fields(
            patch=wire_patch,
            fields=selected_patch_fields,
            m210=m210,
            result=projection,
        )
        or (reaffirm and not projection.bucket_event_ids)
    )
    if invalid:
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        )
    return projection


def _wire_patch_value(value: object) -> object:
    """Render one validated patch value as bounded canonical JSON text."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return display_decimal(value)
    if isinstance(value, StrEnum):
        return value.value
    return value


def _matches_selected_fields(
    *,
    patch: LedgerClassifyPatch,
    fields: tuple[str, ...],
    m210: LedgerClassifyM210Options | None,
    result: LedgerClassifyOperationResult,
) -> bool:
    """Correlate every selected classification fact the canonical action preserves."""
    transaction = result.transaction
    if transaction is None:
        return False
    business_classification = BusinessClassification(transaction.business_classification)
    business_bearing = business_classification in {
        BusinessClassification.BUSINESS,
        BusinessClassification.MIXED,
    }
    for field_name in fields:
        if field_name == "m210_income_classification":
            continue
        requested = getattr(patch, field_name)
        if field_name == "business_classification":
            if transaction.business_classification != requested:
                return False
        elif field_name == "business_pct":
            if transaction.business_pct != requested:
                return False
        elif field_name == "category_id":
            expected = requested.strip() or None if requested is not None else None
            if not business_bearing:
                expected = None
            if transaction.category_id != expected:
                return False
        elif field_name in {"taxable_base", "iva_rate", "iva_amount", "irpf_category"}:
            expected = requested
            if not business_bearing:
                expected = None
            if getattr(transaction, field_name) != expected:
                return False
        elif field_name == "iva_category":
            if transaction.iva_category != requested:
                return False
        elif field_name == "deduction_fact_kind":
            if result.deduction_fact_kind != requested:
                return False
        elif field_name == "investment_asset_id":
            if result.investment_asset_id != requested:
                return False
        elif field_name == "counterparty_country":
            if transaction.counterparty_country != requested:
                return False
        elif field_name == "counterparty_identification_state":
            if transaction.counterparty_identification_state != requested:
                return False
        elif field_name == "notes" and transaction.notes != (requested or ""):
            return False
    if "m210_income_classification" in fields:
        actual_m210 = transaction.m210_income_classification
        if not business_bearing:
            return actual_m210 is None
        if m210 is None or actual_m210 is None:
            return False
        expected_code = (m210.tipo_renta_code or "").strip()
        expected_gross = m210.gross_income_amount
        expected_rate = m210.applicable_rate
        expected_payer_mode = m210.payer_mode
        expected_payer_id = m210.payer_id or None
        expected_asset_id = m210.asset_or_right_id or None
        if (
            actual_m210.official_tipo_renta_code != expected_code
            or actual_m210.gross_income_amount != expected_gross
            or actual_m210.applicable_rate != expected_rate
            or actual_m210.payer_mode != expected_payer_mode
            or actual_m210.payer_id != expected_payer_id
            or actual_m210.asset_or_right_id != expected_asset_id
        ):
            return False
    return True


__all__ = ["run_ledger_classify"]
