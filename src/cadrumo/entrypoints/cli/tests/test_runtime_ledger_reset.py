"""Ledger reset bridge preserves exact-profile receipt and effect correlation."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
import typer

from ....application.ledger.reset_operation import (
    LEDGER_RESET_OPERATION_DEFINITION_ID,
    LedgerResetOperationResult,
    LedgerResetReportProjection,
    LedgerResetRequest,
)
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .. import runtime_ledger_reset as bridge
from ..errors import CliRefusedBoundaryError
from ..runtime_registered_operation import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")
_OPERATION_ID = "f" * 64


def _projection(
    *,
    profile_id: UUID = _PROFILE,
    dry_run: bool = True,
    reset: bool = False,
    actor: str = "operator",
):
    return LedgerResetOperationResult(
        profile_id=profile_id,
        report=LedgerResetReportProjection(
            bucket_id=str(profile_id),
            dry_run=dry_run,
            reset=reset,
            actor=actor,
            reason="reset contaminated import",
        ),
    )


def _bind(
    monkeypatch: pytest.MonkeyPatch,
    completion: RegisteredOperationCompletion[LedgerResetOperationResult],
    submitted: list[LedgerResetRequest],
) -> None:
    monkeypatch.setattr(
        bridge,
        "bound_profile_client",
        lambda *_args, **_kwargs: SimpleNamespace(profile_id=_PROFILE),
    )

    def submit(_client: object, request: LedgerResetRequest, **kwargs: object):
        submitted.append(request)
        assert kwargs["definition_id"] == LEDGER_RESET_OPERATION_DEFINITION_ID
        assert kwargs["subject_ref"] == profile_operation_subject(str(_PROFILE))
        assert kwargs["result_type"] is LedgerResetOperationResult
        assert kwargs["request_version"] == kwargs["result_version"] == 1
        return completion

    monkeypatch.setattr(bridge, "run_registered_operation", submit)


def _invoke(*, dry_run: bool = True, actor: str | None = None):
    return bridge.run_ledger_reset(
        cast(typer.Context, cast(object, None)),
        reason="reset contaminated import",
        dry_run=dry_run,
        actor=actor,
    )


def test_bridge_submits_exact_profile_and_correlated_preview(monkeypatch: pytest.MonkeyPatch) -> None:
    projection = _projection(actor=str(_PROFILE))
    submitted: list[LedgerResetRequest] = []
    _bind(
        monkeypatch,
        RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=projection,
            effect=OperationEffect.NONE,
        ),
        submitted,
    )

    result = _invoke()

    assert result == projection
    assert len(submitted) == 1
    assert submitted[0].profile_id == _PROFILE
    assert submitted[0].reason == "reset contaminated import"
    assert submitted[0].dry_run is True
    assert submitted[0].actor is None


def test_bridge_accepts_only_updated_effect_for_confirmed_reset(monkeypatch: pytest.MonkeyPatch) -> None:
    projection = _projection(dry_run=False, reset=True, actor=str(_PROFILE))
    submitted: list[LedgerResetRequest] = []
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
    assert submitted[0].profile_id == _PROFILE
    assert submitted[0].dry_run is False


@pytest.mark.parametrize("invalid_case", ["profile", "effect", "terminal", "reset-noop"])
def test_bridge_rejects_unmatched_profile_or_settlement(
    monkeypatch: pytest.MonkeyPatch,
    invalid_case: str,
) -> None:
    projection = _projection(actor=str(_PROFILE))
    effect = OperationEffect.NONE
    terminal = OperationTerminalCondition.SUCCEEDED
    if invalid_case == "profile":
        projection = _projection(profile_id=_OTHER_PROFILE, actor=str(_OTHER_PROFILE))
    elif invalid_case == "effect":
        effect = OperationEffect.UPDATED
    elif invalid_case == "terminal":
        terminal = OperationTerminalCondition.REFUSED
    elif invalid_case == "reset-noop":
        projection = _projection(dry_run=False, reset=False, actor=str(_PROFILE))
        effect = OperationEffect.NONE
    submitted: list[LedgerResetRequest] = []
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
        _invoke(dry_run=invalid_case != "reset-noop")

    assert refused.value.context is not None
    assert refused.value.context["reason"] == "runtime_invalid_frame"
