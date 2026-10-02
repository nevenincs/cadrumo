"""Manual-add bridge serializes bounded facts and correlates its receipt."""

from __future__ import annotations

from collections.abc import Sequence
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
import typer

from ....application.ledger.add_operation import (
    LEDGER_ADD_OPERATION_DEFINITION_ID,
    LedgerAddOperationResult,
    LedgerAddRequest,
)
from ....application.ledger.transaction_projection import LedgerTransactionProjection
from ....application.review.filter import LedgerReviewStatus
from ....core.operations import OperationEffect, profile_operation_subject
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from .. import runtime_ledger_add as bridge
from ..errors import CliRefusedBoundaryError
from ..runtime_registered_operation import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_TRANSACTION_ID = "b" * 64
_OPERATION_ID = "a" * 64


def _projection(
    *,
    input_classification: str | None = "exclusively_deductible",
    sector_id: str | None = "sector-typo",
    input_inert: bool = True,
    sector_unmatched: bool = True,
) -> LedgerAddOperationResult:
    transaction = LedgerTransactionProjection.model_construct(
        transaction_id=_TRANSACTION_ID,
        date="2026-04-15",
        booked_date="2026-04-15",
        amount="10",
        currency="EUR",
        direction="OUTGOING",
        counterparty="",
        description="Office materials",
        business_classification="NOT_YET_PROCESSED",
        business_pct=None,
    )
    return LedgerAddOperationResult.model_construct(
        outcome="created",
        profile_id=_PROFILE,
        transaction=transaction,
        review_status=LedgerReviewStatus.PENDING,
        bucket_event_ids=("e" * 64,),
        advisory_input_classification=input_classification,
        advisory_input_classification_inert=input_inert,
        advisory_sector_id=sector_id,
        advisory_sector_unmatched=sector_unmatched,
    )


def _bind(
    monkeypatch: pytest.MonkeyPatch,
    completion: RegisteredOperationCompletion[LedgerAddOperationResult],
    submitted: list[LedgerAddRequest],
) -> None:
    monkeypatch.setattr(
        bridge,
        "bound_profile_client",
        lambda *_args, **_kwargs: SimpleNamespace(profile_id=_PROFILE),
    )

    def submit(_client: object, request: LedgerAddRequest, **kwargs: object):
        submitted.append(request)
        assert kwargs["definition_id"] == LEDGER_ADD_OPERATION_DEFINITION_ID
        assert kwargs["subject_ref"] == profile_operation_subject(str(_PROFILE))
        assert kwargs["result_type"] is LedgerAddOperationResult
        assert kwargs["request_version"] == kwargs["result_version"] == 1
        assert kwargs["allow_refusal_detail"] is True
        return completion

    monkeypatch.setattr(bridge, "run_registered_operation", submit)


def _invoke(*, attachment_ids: Sequence[str] = ()) -> LedgerAddOperationResult:
    return bridge.run_ledger_add(
        cast(typer.Context, cast(object, None)),
        booked_date="2026-04-15",
        amount="10.00",
        direction=TransactionDirection.OUTGOING,
        description="Office materials",
        value_date=None,
        currency="EUR",
        counterparty=None,
        business_classification=BusinessClassification.NOT_YET_PROCESSED,
        business_pct=None,
        category_id=None,
        taxable_base=None,
        iva_rate=None,
        iva_amount=None,
        iva_category=None,
        deduction_fact_kind=None,
        investment_asset_id=None,
        counterparty_country=None,
        counterparty_identification_state=None,
        recargo_amount=None,
        irpf_category=None,
        usage_ratio_id=None,
        prorrata_reference=None,
        art_104_tres_exclusion=None,
        input_classification="exclusively_deductible",
        prorrata_sector="sector-typo",
        purchase_invoice_evidence_id=None,
        attachment_ids=attachment_ids,
        notes="",
        actor=None,
        idempotency_key="manual-add-once",
        source_jurisdiction=None,
    )


def test_bridge_submits_selected_prorrata_facts_and_correlates_advisories(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    projection = _projection()
    submitted: list[LedgerAddRequest] = []
    _bind(
        monkeypatch,
        RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=projection,
            effect=OperationEffect.UPDATED,
        ),
        submitted,
    )

    assert _invoke(attachment_ids=[]) == projection
    assert len(submitted) == 1
    request = submitted[0]
    assert request.profile_id == _PROFILE
    assert request.booked_date == "2026-04-15"
    assert request.amount == "10.00"
    assert request.input_classification == "exclusively_deductible"
    assert request.prorrata_sector == "sector-typo"
    assert request.attachment_ids == ()


@pytest.mark.parametrize(
    ("projection", "effect"),
    [
        (_projection(input_classification="other-token"), OperationEffect.UPDATED),
        (_projection(sector_id="other-sector"), OperationEffect.UPDATED),
        (_projection(), OperationEffect.NONE),
    ],
)
def test_bridge_rejects_unmatched_advisory_echo_or_effect(
    monkeypatch: pytest.MonkeyPatch,
    projection: LedgerAddOperationResult,
    effect: OperationEffect,
) -> None:
    submitted: list[LedgerAddRequest] = []
    _bind(
        monkeypatch,
        RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=projection,
            effect=effect,
        ),
        submitted,
    )

    with pytest.raises(CliRefusedBoundaryError) as refused:
        _invoke()

    assert refused.value.context is not None
    assert refused.value.context["reason"] == "runtime_invalid_frame"
