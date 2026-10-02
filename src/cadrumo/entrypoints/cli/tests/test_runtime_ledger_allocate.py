"""Ledger-allocation bridge preserves profile, request, and effect correlation."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
import typer

from ....application.ledger.allocate_operation import (
    LEDGER_ALLOCATE_OPERATION_DEFINITION_ID,
    LedgerAllocateOperationResult,
    LedgerAllocateRequest,
)
from ....application.ledger.transaction_projection import LedgerTransactionProjection
from ....application.review.filter import LedgerReviewStatus
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .. import runtime_ledger_allocate as bridge
from ..errors import CliRefusedBoundaryError
from ..runtime_registered_operation import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")
_TRANSACTION_ID = "a" * 64
_OPERATION_ID = "f" * 64


def _projection(
    *,
    profile_id: UUID = _PROFILE,
    transaction_id: str = _TRANSACTION_ID,
    business_pct: str = "0.5",
    bucket_event_ids: tuple[str, ...] = ("e" * 64,),
) -> LedgerAllocateOperationResult:
    transaction = LedgerTransactionProjection(
        transaction_id=transaction_id,
        date="2026-01-01",
        booked_date="2026-01-01",
        value_date=None,
        amount="100",
        currency="EUR",
        direction="expense",
        counterparty="Fixture supplier",
        description="Allocated transaction",
        business_classification="MIXED",
        business_pct=business_pct,
        category_id=None,
        taxable_base=None,
        iva_rate=None,
        iva_amount=None,
        iva_category=None,
        counterparty_country=None,
        counterparty_identification_state=None,
        irpf_category=None,
        m210_income_classification=None,
        usage_ratio_id=None,
        prorrata_reference=None,
        purchase_invoice_evidence_id=None,
        invoice_id=None,
        attachment_ids=(),
        notes="",
        lifecycle_state="active",
        classified_by="operator:fixture",
        classified_at=None,
        classification_reason="Allocated by fixture",
        classification_confidence=None,
        source_jurisdiction=None,
        value_in_eur=None,
        fx_rate=None,
        created_at="2026-01-01T00:00:00Z",
        modified_at="2026-01-01T00:00:00Z",
    )
    return LedgerAllocateOperationResult(
        profile_id=profile_id,
        transaction=transaction,
        review_status=LedgerReviewStatus.PENDING,
        bucket_event_ids=bucket_event_ids,
    )


def _bind(
    monkeypatch: pytest.MonkeyPatch,
    completion: RegisteredOperationCompletion[LedgerAllocateOperationResult],
    submitted: list[LedgerAllocateRequest],
) -> None:
    monkeypatch.setattr(
        bridge,
        "bound_profile_client",
        lambda *_args, **_kwargs: SimpleNamespace(profile_id=_PROFILE),
    )

    def submit(_client: object, request: LedgerAllocateRequest, **kwargs: object):
        submitted.append(request)
        assert kwargs["definition_id"] == LEDGER_ALLOCATE_OPERATION_DEFINITION_ID
        assert kwargs["subject_ref"] == profile_operation_subject(str(_PROFILE))
        assert kwargs["result_type"] is LedgerAllocateOperationResult
        assert kwargs["request_version"] == kwargs["result_version"] == 1
        return completion

    monkeypatch.setattr(bridge, "run_registered_operation", submit)


def _invoke(*, transaction_id: str = _TRANSACTION_ID) -> LedgerAllocateOperationResult:
    return bridge.run_ledger_allocate(
        cast(typer.Context, cast(object, None)),
        transaction_id=transaction_id,
        business_pct=Decimal("0.50"),
        category_id=None,
        usage_ratio_id=None,
        prorrata_reference=None,
        actor=None,
    )


def test_bridge_submits_exact_profile_and_correlated_allocation(monkeypatch: pytest.MonkeyPatch) -> None:
    projection = _projection()
    submitted: list[LedgerAllocateRequest] = []
    _bind(
        monkeypatch,
        RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=projection,
            effect=OperationEffect.UPDATED,
        ),
        submitted,
    )

    result = _invoke(transaction_id=_TRANSACTION_ID[:12])

    assert result == projection
    assert len(submitted) == 1
    assert submitted[0].profile_id == _PROFILE
    assert submitted[0].transaction_id == _TRANSACTION_ID[:12]
    assert submitted[0].business_pct == "0.5"


def test_bridge_accepts_none_effect_for_a_confirmed_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    projection = _projection(bucket_event_ids=())
    submitted: list[LedgerAllocateRequest] = []
    _bind(
        monkeypatch,
        RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=projection,
            effect=OperationEffect.NONE,
        ),
        submitted,
    )

    assert _invoke() == projection
    assert len(submitted) == 1


@pytest.mark.parametrize("invalid_case", ["profile", "transaction", "share", "effect", "terminal", "noop-effect"])
def test_bridge_rejects_unmatched_profile_result_or_effect(
    monkeypatch: pytest.MonkeyPatch,
    invalid_case: str,
) -> None:
    projection = _projection()
    effect = OperationEffect.UPDATED
    terminal = OperationTerminalCondition.SUCCEEDED
    if invalid_case == "profile":
        projection = _projection(profile_id=_OTHER_PROFILE)
    elif invalid_case == "transaction":
        projection = _projection(transaction_id="b" * 64)
    elif invalid_case == "share":
        projection = _projection(business_pct="0.25")
    elif invalid_case == "effect":
        effect = OperationEffect.NONE
    elif invalid_case == "terminal":
        terminal = OperationTerminalCondition.REFUSED
    elif invalid_case == "noop-effect":
        projection = _projection(bucket_event_ids=())
        effect = OperationEffect.UPDATED
    submitted: list[LedgerAllocateRequest] = []
    _bind(
        monkeypatch,
        RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=projection,
            effect=effect,
            terminal_condition=terminal,
        ),
        submitted,
    )

    with pytest.raises(CliRefusedBoundaryError) as refused:
        _invoke(transaction_id=_TRANSACTION_ID[:12])

    assert refused.value.context is not None
    assert refused.value.context["reason"] == "runtime_invalid_frame"
