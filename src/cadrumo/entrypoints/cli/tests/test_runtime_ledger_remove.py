"""Ledger-removal bridge preserves exact-profile receipt and effect correlation."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
import typer

from ....application.ledger.remove_operation import (
    LEDGER_REMOVE_OPERATION_DEFINITION_ID,
    LedgerRemoveOperationResult,
    LedgerRemoveReportProjection,
    LedgerRemoveRequest,
)
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .. import runtime_ledger_remove as bridge
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
    dry_run: bool = True,
    removed: bool = False,
):
    return LedgerRemoveOperationResult(
        profile_id=profile_id,
        report=LedgerRemoveReportProjection(
            bucket_id=str(profile_id),
            transaction_id=transaction_id,
            dry_run=dry_run,
            removed=removed,
            actor="operator",
            reason="duplicate row",
        ),
    )


def _bind(
    monkeypatch: pytest.MonkeyPatch,
    completion: RegisteredOperationCompletion[LedgerRemoveOperationResult],
    submitted: list[LedgerRemoveRequest],
) -> None:
    monkeypatch.setattr(
        bridge,
        "bound_profile_client",
        lambda *_args, **_kwargs: SimpleNamespace(profile_id=_PROFILE),
    )

    def submit(_client: object, request: LedgerRemoveRequest, **kwargs: object):
        submitted.append(request)
        assert kwargs["definition_id"] == LEDGER_REMOVE_OPERATION_DEFINITION_ID
        assert kwargs["subject_ref"] == profile_operation_subject(str(_PROFILE))
        assert kwargs["result_type"] is LedgerRemoveOperationResult
        assert kwargs["request_version"] == kwargs["result_version"] == 1
        return completion

    monkeypatch.setattr(bridge, "run_registered_operation", submit)


def _invoke(*, transaction_id: str = _TRANSACTION_ID, dry_run: bool = True):
    return bridge.run_ledger_remove(
        cast(typer.Context, cast(object, None)),
        transaction_id=transaction_id,
        reason="duplicate row",
        dry_run=dry_run,
        actor="operator",
    )


def test_bridge_submits_exact_profile_and_correlated_dry_run(monkeypatch: pytest.MonkeyPatch) -> None:
    projection = _projection()
    submitted: list[LedgerRemoveRequest] = []
    _bind(
        monkeypatch,
        RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=projection,
            effect=OperationEffect.NONE,
        ),
        submitted,
    )

    result = _invoke(transaction_id=_TRANSACTION_ID[:12])

    assert result == projection
    assert len(submitted) == 1
    assert submitted[0].profile_id == _PROFILE
    assert submitted[0].transaction_id == _TRANSACTION_ID[:12]
    assert submitted[0].dry_run is True
    assert submitted[0].reason == "duplicate row"


def test_bridge_accepts_only_updated_effect_for_confirmed_removal(monkeypatch: pytest.MonkeyPatch) -> None:
    projection = _projection(dry_run=False, removed=True)
    submitted: list[LedgerRemoveRequest] = []
    _bind(
        monkeypatch,
        RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=projection,
            effect=OperationEffect.UPDATED,
        ),
        submitted,
    )

    result = _invoke(dry_run=False)

    assert result == projection
    assert submitted[0].dry_run is False


@pytest.mark.parametrize("invalid_case", ["profile", "receipt", "effect", "terminal", "mutation-noop"])
def test_bridge_rejects_unmatched_profile_receipt_or_settlement(
    monkeypatch: pytest.MonkeyPatch,
    invalid_case: str,
) -> None:
    projection = _projection()
    effect = OperationEffect.NONE
    terminal = OperationTerminalCondition.SUCCEEDED
    if invalid_case == "profile":
        projection = _projection(profile_id=_OTHER_PROFILE)
    elif invalid_case == "receipt":
        projection = _projection(transaction_id="b" * 64)
    elif invalid_case == "effect":
        effect = OperationEffect.UPDATED
    elif invalid_case == "terminal":
        terminal = OperationTerminalCondition.REFUSED
    elif invalid_case == "mutation-noop":
        projection = _projection(dry_run=False, removed=False)
    submitted: list[LedgerRemoveRequest] = []
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
        _invoke(transaction_id=_TRANSACTION_ID[:12], dry_run=invalid_case != "mutation-noop")

    assert refused.value.context is not None
    assert refused.value.context["reason"] == "runtime_invalid_frame"
