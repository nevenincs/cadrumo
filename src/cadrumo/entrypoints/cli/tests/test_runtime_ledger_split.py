"""Split bridge verifies canonical wire inputs and terminal output correlation."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
import typer

from ....application.ledger.models import SplitChildCommand
from ....application.ledger.split_operation import (
    LEDGER_SPLIT_OPERATION_DEFINITION_ID,
    LedgerSplitOperationResult,
    LedgerSplitRequest,
)
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....domain.transactions.enums import BusinessClassification
from .. import runtime_ledger_split as bridge
from ..errors import CliRefusedBoundaryError
from ..runtime_registered_operation import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")
_PARENT_ID = "a" * 64
_OPERATION_ID = "f" * 64


def _projection(
    *,
    profile_id: UUID = _PROFILE,
    parent_transaction_id: str = _PARENT_ID,
    child_transaction_ids: tuple[str, ...] = ("b" * 64, "c" * 64),
) -> LedgerSplitOperationResult:
    return LedgerSplitOperationResult.model_validate(
        {
            "profile_id": profile_id,
            "parent_transaction_id": parent_transaction_id,
            "split_group_id": "d" * 64,
            "child_transaction_ids": child_transaction_ids,
            "bucket_event_id": "e" * 64,
            "parent_business_classification": BusinessClassification.PERSONAL,
        },
    )


def _bind(
    monkeypatch: pytest.MonkeyPatch,
    completion: RegisteredOperationCompletion[LedgerSplitOperationResult],
    submitted: list[LedgerSplitRequest],
) -> None:
    monkeypatch.setattr(
        bridge,
        "bound_profile_client",
        lambda *_args, **_kwargs: SimpleNamespace(profile_id=_PROFILE),
    )

    def submit(_client: object, request: LedgerSplitRequest, **kwargs: object):
        submitted.append(request)
        assert kwargs["definition_id"] == LEDGER_SPLIT_OPERATION_DEFINITION_ID
        assert kwargs["subject_ref"] == profile_operation_subject(str(_PROFILE))
        assert kwargs["result_type"] is LedgerSplitOperationResult
        assert kwargs["request_version"] == kwargs["result_version"] == 1
        assert kwargs["timeout"] == 120
        return completion

    monkeypatch.setattr(bridge, "run_registered_operation", submit)


def _invoke() -> LedgerSplitOperationResult:
    return bridge.run_ledger_split(
        cast(typer.Context, cast(object, None)),
        transaction_id=_PARENT_ID[:12].upper(),
        children=(
            SplitChildCommand(amount=Decimal("60.00"), description="business portion"),
            SplitChildCommand(amount=Decimal("40.00"), description="personal portion"),
        ),
        reason="separate use",
        actor="operator",
    )


def test_bridge_serializes_canonical_amounts_and_correlates_split(monkeypatch: pytest.MonkeyPatch) -> None:
    projection = _projection()
    submitted: list[LedgerSplitRequest] = []
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
    assert request.transaction_id == _PARENT_ID[:12]
    assert request.reason == "separate use"
    assert request.actor == "operator"
    assert tuple((child.amount, child.description) for child in request.children) == (
        ("60", "business portion"),
        ("40", "personal portion"),
    )


@pytest.mark.parametrize("invalid_case", ["profile", "parent", "child_count", "effect", "terminal"])
def test_bridge_rejects_unmatched_split_projection_or_receipt(
    monkeypatch: pytest.MonkeyPatch,
    invalid_case: str,
) -> None:
    projection = _projection()
    effect = OperationEffect.UPDATED
    terminal = OperationTerminalCondition.SUCCEEDED
    if invalid_case == "profile":
        projection = _projection(profile_id=_OTHER_PROFILE)
    elif invalid_case == "parent":
        projection = _projection(parent_transaction_id="b" * 64)
    elif invalid_case == "child_count":
        projection = _projection(child_transaction_ids=("b" * 64, "c" * 64, "d" * 64))
    elif invalid_case == "effect":
        effect = OperationEffect.NONE
    elif invalid_case == "terminal":
        terminal = OperationTerminalCondition.REFUSED
    submitted: list[LedgerSplitRequest] = []
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
        _invoke()

    assert refused.value.context is not None
    assert refused.value.context["reason"] == "runtime_invalid_frame"
