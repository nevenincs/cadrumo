"""CLI transport bridge for worker-owned single-transaction classification."""

from __future__ import annotations

from decimal import Decimal
from typing import cast

import typer

from ...application.ledger.classify_operation import (
    LEDGER_CLASSIFY_OPERATION_DEFINITION_ID,
    LEDGER_CLASSIFY_VALIDATION_REFUSAL_CODE,
    LEDGER_OPERATOR_IVA_DEFINITION_ID,
    LedgerClassifyOperationResult,
    LedgerClassifyPatch,
    LedgerClassifyPatchField,
    LedgerClassifyRequest,
    LedgerOperatorIvaRequest,
    LedgerOperatorIvaResult,
)
from ...application.ledger.models import ManualLedgerTransactionPatch
from ...core.operations import OperationTerminalCondition, profile_operation_subject
from ...domain.transactions.enums import BusinessClassification
from .ledger_classify_correlation import (
    correlate_classification_refusal,
    correlate_classification_success,
    operator_iva_expected_effect,
)
from .ledger_classify_inputs import classification_m210_selection, classification_wire_value
from .registered_operation_errors import invalid_completion_error
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import run_registered_operation


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
        {field: classification_wire_value(getattr(patch, field)) for field in patch_fields},
    )
    m210, selected_patch_fields = classification_m210_selection(
        patch_fields,
        m210_tipo_renta_code,
        m210_gross_income_amount,
        m210_applicable_rate,
        m210_payer_mode,
        m210_payer_id,
        m210_asset_or_right_id,
    )
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
        correlate_classification_refusal(completed, projection, client.profile_id)
        return projection
    correlate_classification_success(
        completed,
        projection,
        client.profile_id,
        transaction_id,
        classification,
        business_pct,
        wire_patch,
        selected_patch_fields,
        m210,
        reaffirm,
    )
    return projection


def run_ledger_operator_iva(
    ctx: typer.Context, *, transaction_id: str, iva_category: str, actor: str | None
) -> LedgerOperatorIvaResult:
    """Derive the operator-selected IVA substrate in the exact-profile worker."""
    client = bound_profile_client(ctx)
    payload = LedgerOperatorIvaRequest(
        profile_id=client.profile_id, transaction_id=transaction_id, iva_category=iva_category, actor=actor
    )
    completed = run_registered_operation(
        client,
        payload,
        definition_id=LEDGER_OPERATOR_IVA_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=LedgerOperatorIvaResult,
        request_version=1,
        result_version=1,
        timeout=120,
        allow_refusal_detail=True,
    )
    result = completed.projection
    expected_effect = operator_iva_expected_effect(result)
    if (
        result.profile_id != client.profile_id
        or not result.transaction_id.startswith(payload.transaction_id)
        or result.iva_category != iva_category
        or completed.effect is not expected_effect
        or (
            result.outcome == "validation_error"
            and (
                completed.terminal_condition is not OperationTerminalCondition.REFUSED
                or completed.refusal_code != LEDGER_CLASSIFY_VALIDATION_REFUSAL_CODE
            )
        )
        or (result.outcome == "derived" and completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED)
    ):
        raise invalid_completion_error(completed)
    return result
