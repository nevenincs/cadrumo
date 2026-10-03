"""Ledger-update bridge correlates dates, direction, grouping, and profile."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
import typer

from ....application.ledger.models import ManualLedgerTransactionPatch
from ....application.ledger.transaction_projection import LedgerTransactionProjection
from ....application.ledger.update_contracts import (
    LEDGER_UPDATE_OPERATION_DEFINITION_ID,
    LedgerUpdateOperationResult,
    LedgerUpdateRequest,
)
from ....application.review.filter import LedgerReviewStatus
from ....core.operations import OperationEffect, profile_operation_subject
from ....domain.transactions.enums import TransactionDirection
from .. import runtime_ledger_update as bridge
from ..errors import CliRefusedBoundaryError
from ..registered_operation_contracts import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_TRANSACTION_ID = "a" * 64
_OPERATION_ID = "f" * 64


def _projection(*, group_label: str = "Travel") -> LedgerUpdateOperationResult:
    transaction = LedgerTransactionProjection.model_construct(
        transaction_id=_TRANSACTION_ID,
        booked_date="2026-04-16",
        value_date=None,
        amount="121.00",
        direction="INCOMING",
    )
    return LedgerUpdateOperationResult.model_construct(
        outcome="updated",
        profile_id=_PROFILE,
        transaction=transaction,
        review_status=LedgerReviewStatus.PENDING,
        bucket_event_ids=("e" * 64,),
        group_label=group_label,
    )


def _bind(
    monkeypatch: pytest.MonkeyPatch,
    completion: RegisteredOperationCompletion[LedgerUpdateOperationResult],
    submitted: list[LedgerUpdateRequest],
) -> None:
    monkeypatch.setattr(
        bridge,
        "bound_profile_client",
        lambda *_args, **_kwargs: SimpleNamespace(profile_id=_PROFILE),
    )

    def submit(_client: object, request: LedgerUpdateRequest, **kwargs: object):
        submitted.append(request)
        assert kwargs["definition_id"] == LEDGER_UPDATE_OPERATION_DEFINITION_ID
        assert kwargs["subject_ref"] == profile_operation_subject(str(_PROFILE))
        assert kwargs["result_type"] is LedgerUpdateOperationResult
        assert kwargs["request_version"] == kwargs["result_version"] == 1
        return completion

    monkeypatch.setattr(bridge, "run_registered_operation", submit)


def _invoke() -> LedgerUpdateOperationResult:
    return bridge.run_ledger_update(
        cast(typer.Context, cast(object, None)),
        transaction_id=_TRANSACTION_ID[:12],
        patch=ManualLedgerTransactionPatch(
            booked_date=date(2026, 4, 16),
            direction=TransactionDirection.INCOMING,
            group_label="Travel",
        ),
        actor=None,
    )


def test_bridge_submits_and_correlates_wire_date_direction_and_group(monkeypatch: pytest.MonkeyPatch) -> None:
    projection = _projection()
    submitted: list[LedgerUpdateRequest] = []
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
    assert set(request.patch_fields) == {"booked_date", "direction", "group_label"}
    assert request.patch.booked_date == "2026-04-16"
    assert request.patch.direction == "INCOMING"
    assert request.patch.group_label == "Travel"


def test_bridge_rejects_a_group_label_that_does_not_match_the_request(monkeypatch: pytest.MonkeyPatch) -> None:
    submitted: list[LedgerUpdateRequest] = []
    _bind(
        monkeypatch,
        RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=_projection(group_label="Home"),
            effect=OperationEffect.UPDATED,
        ),
        submitted,
    )

    with pytest.raises(CliRefusedBoundaryError) as refused:
        _invoke()

    assert refused.value.context is not None
    assert refused.value.context["reason"] == "runtime_invalid_frame"
