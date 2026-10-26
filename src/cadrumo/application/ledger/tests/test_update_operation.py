"""Ledger update wire requests and terminal results stay profile-bound."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from ....application.review.filter import LedgerReviewStatus
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...operations.models import OperationIdentity, OperationTerminalReceipt
from .. import update_contracts as contracts
from .. import update_operation as operation
from ..transaction_projection import LedgerTransactionProjection

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")


@pytest.mark.parametrize("value", ["eur", " EUR ", "12A"])
def test_currency_patch_refuses_noncanonical_text_instead_of_rewriting_it(value: str) -> None:
    """An edit names the exact stored token; domain normalization is not transport policy."""
    with pytest.raises(ValidationError):
        contracts.LedgerUpdatePatch(currency=value)


def _transaction() -> LedgerTransactionProjection:
    return LedgerTransactionProjection.model_validate(
        {
            "transaction_id": "b" * 64,
            "date": "2026-04-15",
            "booked_date": "2026-04-15",
            "value_date": None,
            "amount": "121.00",
            "currency": "EUR",
            "direction": "OUTFLOW",
            "counterparty": "Client SL",
            "description": "Invoice 1",
            "business_classification": "MIXED",
            "business_pct": "0.5",
            "category_id": None,
            "taxable_base": None,
            "iva_rate": None,
            "iva_amount": None,
            "iva_category": None,
            "counterparty_country": None,
            "counterparty_identification_state": None,
            "irpf_category": None,
            "m210_income_classification": None,
            "usage_ratio_id": None,
            "prorrata_reference": None,
            "purchase_invoice_evidence_id": None,
            "invoice_id": None,
            "attachment_ids": (),
            "notes": "",
            "lifecycle_state": "ACTIVE",
            "classified_by": "manual",
            "classified_at": None,
            "classification_reason": "",
            "classification_confidence": None,
            "source_jurisdiction": None,
            "value_in_eur": None,
            "fx_rate": None,
            "created_at": "2026-04-15T09:30:00+00:00",
            "modified_at": "2026-04-15T09:30:00+00:00",
        },
    )


def _receipt(
    condition: OperationTerminalCondition,
    effect: OperationEffect,
) -> OperationTerminalReceipt:
    refused = condition is OperationTerminalCondition.REFUSED
    return OperationTerminalReceipt(
        identity=OperationIdentity(
            operation_id="a" * 64,
            definition_id=contracts.LEDGER_UPDATE_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(_PROFILE)),
        ),
        revision=1,
        condition=condition,
        effect=effect,
        settled_at=datetime(2026, 4, 15, tzinfo=UTC),
        result_ref=None if refused else "f" * 64,
        refusal_ref=contracts.LEDGER_UPDATE_VALIDATION_REFUSAL_CODE if refused else None,
        refusal_detail_ref="e" * 64 if refused else None,
    )


def test_wire_request_preserves_explicit_null_and_rejects_unselected_values() -> None:
    request = contracts.LedgerUpdateRequest(
        profile_id=_PROFILE,
        transaction_id="b" * 12,
        patch=contracts.LedgerUpdatePatch(booked_date="2026-04-16", group_label=None),
        patch_fields=("booked_date", "group_label"),
    )

    assert contracts.LedgerUpdateRequest.model_validate_json(request.model_dump_json()) == request
    with pytest.raises(ValidationError):
        contracts.LedgerUpdateRequest(
            profile_id=_PROFILE,
            transaction_id="b" * 12,
            patch=contracts.LedgerUpdatePatch(booked_date="2026-04-16", direction="INFLOW"),
            patch_fields=("booked_date",),
        )


def test_terminal_projector_rejects_forged_definition_and_result_reference() -> None:
    result = contracts.LedgerUpdateExecutionResult(
        outcome="updated",
        profile_id=_PROFILE,
        result=contracts.LedgerUpdateOperationResult(
            outcome="updated",
            profile_id=_PROFILE,
            source_transaction_id="a" * 64,
            transaction=_transaction(),
            review_status=LedgerReviewStatus.PENDING,
            bucket_event_ids=("d" * 64,),
        ),
    )
    receipt = _receipt(OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED)
    wrong_definition = receipt.model_copy(
        update={
            "identity": receipt.identity.model_copy(update={"definition_id": "ledger.remove"}),
        },
    )

    with pytest.raises(ValueError):
        operation._project_operation_result(result, wrong_definition)
    with pytest.raises(ValidationError):
        OperationTerminalReceipt.model_validate({**receipt.model_dump(), "result_ref": None})


def test_terminal_projector_rejects_foreign_refusal_and_receipt_forbids_its_result_reference() -> None:
    result = contracts.LedgerUpdateExecutionResult(
        outcome="validation_error",
        profile_id=_PROFILE,
        validation_messages=("amount: must satisfy transaction rules",),
    )
    receipt = _receipt(OperationTerminalCondition.REFUSED, OperationEffect.NONE)

    with pytest.raises(ValueError):
        operation._project_operation_result(result, receipt.model_copy(update={"refusal_ref": "REFUSED_OTHER"}))
    with pytest.raises(ValidationError):
        OperationTerminalReceipt.model_validate({**receipt.model_dump(), "result_ref": "f" * 64})


def test_update_result_preserves_the_source_id_across_the_worker_wire() -> None:
    projected = contracts.LedgerUpdateOperationResult(
        outcome="updated",
        profile_id=_PROFILE,
        source_transaction_id="a" * 64,
        transaction=_transaction(),
        review_status=LedgerReviewStatus.PENDING,
        bucket_event_ids=("d" * 64,),
    )
    result = contracts.LedgerUpdateExecutionResult(outcome="updated", profile_id=_PROFILE, result=projected)
    decoded = contracts.LedgerUpdateExecutionResult.model_validate_json(result.model_dump_json())
    assert (
        operation._project_operation_result(
            decoded,
            _receipt(OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED),
        )
        == projected
    )
    assert decoded.result is not None and decoded.result.source_transaction_id == "a" * 64
    assert decoded.result.transaction is not None and decoded.result.transaction.transaction_id == "b" * 64


@pytest.mark.parametrize("case", ["missing_source", "changed_without_effect", "refused_with_source"])
def test_update_result_refuses_missing_or_inconsistent_source_identity(case: str) -> None:
    values: dict[str, object] = {
        "outcome": "updated",
        "profile_id": _PROFILE,
        "source_transaction_id": "a" * 64,
        "transaction": _transaction(),
        "review_status": LedgerReviewStatus.PENDING,
        "bucket_event_ids": ("d" * 64,),
    }
    if case == "missing_source":
        del values["source_transaction_id"]
    elif case == "changed_without_effect":
        values["bucket_event_ids"] = ()
    else:
        values = {
            "outcome": "validation_error",
            "profile_id": _PROFILE,
            "source_transaction_id": "a" * 64,
            "validation_messages": ("invalid patch",),
        }
    with pytest.raises(ValidationError):
        contracts.LedgerUpdateOperationResult.model_validate(values)
