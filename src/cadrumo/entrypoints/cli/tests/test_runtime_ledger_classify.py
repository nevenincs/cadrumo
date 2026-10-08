"""Classification bridge preserves canonical wire fields and checks the result envelope."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
import typer

from ....application.ledger.classify_requests import (
    LEDGER_CLASSIFY_OPERATION_DEFINITION_ID,
    LedgerClassifyM210Options,
    LedgerClassifyRequest,
)
from ....application.ledger.classify_result_contracts import (
    LEDGER_CLASSIFY_VALIDATION_REFUSAL_CODE,
    LedgerClassifyOperationResult,
)
from ....application.ledger.models import ManualLedgerTransactionPatch
from ....application.ledger.transaction_projection import LedgerM210IncomeProjection, LedgerTransactionProjection
from ....application.review.filter import LedgerReviewStatus
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....domain.transactions.enums import BusinessClassification
from .. import runtime_ledger_classify as bridge
from ..errors import CliRefusedBoundaryError
from ..registered_operation_contracts import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_TRANSACTION_ID = "b" * 64
_OPERATION_ID = "f" * 64


def _projection(*, investment_asset_id: str = "equipment-1") -> LedgerClassifyOperationResult:
    transaction = LedgerTransactionProjection.model_construct(
        transaction_id=_TRANSACTION_ID,
        business_classification="MIXED",
        business_pct="0.25",
        category_id=None,
        taxable_base=None,
        iva_rate=None,
        iva_amount=None,
        irpf_category=None,
        iva_category=None,
        counterparty_country=None,
        counterparty_identification_state=None,
        notes="Rental split",
        m210_income_classification=LedgerM210IncomeProjection.model_construct(
            official_tipo_renta_code="01",
            gross_income_amount="1000",
            applicable_rate="0.19",
            payer_mode="single",
            payer_id="payer-1",
            asset_or_right_id="flat-1",
        ),
    )
    return LedgerClassifyOperationResult.model_construct(
        outcome="classified",
        profile_id=_PROFILE,
        transaction=transaction,
        deduction_fact_kind=None,
        investment_asset_id=investment_asset_id,
        review_status=LedgerReviewStatus.PENDING,
        bucket_event_ids=("e" * 64,),
    )


def _bind(
    monkeypatch: pytest.MonkeyPatch,
    completion: RegisteredOperationCompletion[LedgerClassifyOperationResult],
    submitted: list[LedgerClassifyRequest],
) -> None:
    monkeypatch.setattr(
        bridge,
        "bound_profile_client",
        lambda *_args, **_kwargs: SimpleNamespace(profile_id=_PROFILE),
    )

    def submit(_client: object, request: LedgerClassifyRequest, **kwargs: object):
        submitted.append(request)
        assert kwargs["definition_id"] == LEDGER_CLASSIFY_OPERATION_DEFINITION_ID
        assert kwargs["subject_ref"] == profile_operation_subject(str(_PROFILE))
        assert kwargs["result_type"] is LedgerClassifyOperationResult
        assert kwargs["request_version"] == kwargs["result_version"] == 1
        assert kwargs["allow_refusal_detail"] is True
        return completion

    monkeypatch.setattr(bridge, "run_registered_operation", submit)


def _invoke() -> LedgerClassifyOperationResult:
    return bridge.run_ledger_classify(
        cast(typer.Context, cast(object, None)),
        transaction_id=_TRANSACTION_ID[:12],
        classification=BusinessClassification.MIXED,
        patch=ManualLedgerTransactionPatch(
            business_classification=BusinessClassification.MIXED,
            business_pct=Decimal("0.25"),
            investment_asset_id="equipment-1",
            notes="Rental split",
        ),
        business_pct=Decimal("0.25"),
        m210_tipo_renta_code="01",
        m210_gross_income_amount=Decimal("1000.00"),
        m210_applicable_rate=Decimal("0.19"),
        m210_payer_mode="single",
        m210_payer_id="payer-1",
        m210_asset_or_right_id="flat-1",
        actor="operator",
        reaffirm=False,
    )


def test_bridge_serializes_canonical_m210_values_and_correlates_all_selected_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    projection = _projection()
    submitted: list[LedgerClassifyRequest] = []
    _bind(
        monkeypatch,
        RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=projection,
            effect=OperationEffect.UPDATED,
        ),
        submitted,
    )

    result = _invoke()

    assert result == projection
    assert len(submitted) == 1
    request = submitted[0]
    assert request.profile_id == _PROFILE
    assert request.transaction_id == _TRANSACTION_ID[:12]
    assert set(request.patch_fields) == {
        "business_classification",
        "business_pct",
        "investment_asset_id",
        "m210_income_classification",
        "notes",
    }
    assert request.patch.business_pct == "0.25"
    assert request.m210 == LedgerClassifyM210Options(
        tipo_renta_code="01",
        gross_income_amount="1000",
        applicable_rate="0.19",
        payer_mode="single",
        payer_id="payer-1",
        asset_or_right_id="flat-1",
    )


def test_bridge_rejects_a_selected_private_fact_that_does_not_match_the_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    submitted: list[LedgerClassifyRequest] = []
    _bind(
        monkeypatch,
        RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=_projection(investment_asset_id="other-equipment"),
            effect=OperationEffect.UPDATED,
        ),
        submitted,
    )

    with pytest.raises(CliRefusedBoundaryError) as refused:
        _invoke()

    assert refused.value.context is not None
    assert refused.value.context["reason"] == "runtime_invalid_frame"


def test_bridge_accepts_only_the_bound_no_effect_m210_validation_refusal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    refusal = LedgerClassifyOperationResult.model_construct(
        outcome="validation_error",
        profile_id=_PROFILE,
        transaction=None,
        review_status=None,
        bucket_event_ids=(),
        validation_kind="m210_required_options",
        validation_messages=("M210 declaration is incomplete",),
    )
    submitted: list[LedgerClassifyRequest] = []
    _bind(
        monkeypatch,
        RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=refusal,
            effect=OperationEffect.NONE,
            terminal_condition=OperationTerminalCondition.REFUSED,
            refusal_code=LEDGER_CLASSIFY_VALIDATION_REFUSAL_CODE,
        ),
        submitted,
    )

    result = _invoke()
    assert result is refusal
    assert result.validation_kind == "m210_required_options"

    _bind(
        monkeypatch,
        RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=refusal,
            effect=OperationEffect.UPDATED,
            terminal_condition=OperationTerminalCondition.REFUSED,
            refusal_code=LEDGER_CLASSIFY_VALIDATION_REFUSAL_CODE,
        ),
        submitted,
    )
    with pytest.raises(CliRefusedBoundaryError):
        _invoke()
