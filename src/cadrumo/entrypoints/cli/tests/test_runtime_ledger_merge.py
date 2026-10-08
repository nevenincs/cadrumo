"""Merge bridge correlates exact-profile input, child prefixes, and operation receipt."""

from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
import typer
from typer.testing import CliRunner

from ....application.ledger.merge_operation import (
    LEDGER_MERGE_OPERATION_DEFINITION_ID,
    LedgerMergeOperationResult,
    LedgerMergeRequest,
)
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .. import _command_runtime, _profile_authentication_gate, ledger_lifecycle_cli
from .. import runtime_ledger_merge as bridge
from ..command_specs import COMMAND_GRAPH
from ..errors import CliRefusedBoundaryError
from ..registered_operation_contracts import RegisteredOperationCompletion
from .command_runtime_support import build_command_subtree

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")
_OPERATION_ID = "f" * 64


def _projection(
    *,
    profile_id: UUID = _PROFILE,
    source_child_ids: tuple[str, ...] = ("b" * 64, "c" * 64),
) -> LedgerMergeOperationResult:
    return LedgerMergeOperationResult.model_validate(
        {
            "profile_id": profile_id,
            "split_group_id": "e" * 64,
            "parent_transaction_id": "a" * 64,
            "merged_transaction_id": "d" * 64,
            "source_child_ids": source_child_ids,
            "bucket_event_id": "f" * 64,
        },
    )


def _bind(
    monkeypatch: pytest.MonkeyPatch,
    completion: RegisteredOperationCompletion[LedgerMergeOperationResult],
    submitted: list[LedgerMergeRequest],
) -> None:
    monkeypatch.setattr(
        bridge,
        "bound_profile_client",
        lambda *_args, **_kwargs: SimpleNamespace(profile_id=_PROFILE),
    )

    def submit(_client: object, request: LedgerMergeRequest, **kwargs: object):
        submitted.append(request)
        assert kwargs["definition_id"] == LEDGER_MERGE_OPERATION_DEFINITION_ID
        assert kwargs["subject_ref"] == profile_operation_subject(str(_PROFILE))
        assert kwargs["result_type"] is LedgerMergeOperationResult
        assert kwargs["request_version"] == kwargs["result_version"] == 1
        assert kwargs["timeout"] == 120
        return completion

    monkeypatch.setattr(bridge, "run_registered_operation", submit)


def _invoke() -> LedgerMergeOperationResult:
    return bridge.run_ledger_merge(
        cast(typer.Context, cast(object, None)),
        child_ids=("B" * 12, "c" * 13),
        reason="revert split",
        actor="operator",
    )


def test_bridge_normalizes_prefixes_and_correlates_merge(monkeypatch: pytest.MonkeyPatch) -> None:
    projection = _projection()
    submitted: list[LedgerMergeRequest] = []
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
    assert request.child_ids == ("b" * 12, "c" * 13)
    assert request.reason == "revert split"
    assert request.actor == "operator"


def test_repeated_child_id_argv_reaches_the_strict_merge_request(monkeypatch: pytest.MonkeyPatch) -> None:
    submitted: list[LedgerMergeRequest] = []
    _bind(
        monkeypatch,
        RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=_projection(),
            effect=OperationEffect.UPDATED,
        ),
        submitted,
    )
    monkeypatch.setattr(_profile_authentication_gate, "preflight_parsed_leaf", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(_command_runtime, "_governed_fact_scope", lambda *_args: nullcontext())
    monkeypatch.setattr(ledger_lifecycle_cli, "emit_envelope", lambda *_args, **_kwargs: None)
    result = CliRunner().invoke(
        build_command_subtree(COMMAND_GRAPH, "app_ledger"),
        [
            "merge",
            "--child-id",
            "B" * 12,
            "--child-id",
            "c" * 13,
            "--reason",
            "undo split",
            "--yes",
        ],
    )
    assert result.exit_code == 0, (result.output, result.exception)
    assert len(submitted) == 1
    assert submitted[0].child_ids == ("b" * 12, "c" * 13)


@pytest.mark.parametrize("invalid_case", ["profile", "source_child", "child_count", "effect", "terminal"])
def test_bridge_rejects_unmatched_projection_or_receipt(
    monkeypatch: pytest.MonkeyPatch,
    invalid_case: str,
) -> None:
    projection = _projection()
    effect = OperationEffect.UPDATED
    terminal = OperationTerminalCondition.SUCCEEDED
    if invalid_case == "profile":
        projection = _projection(profile_id=_OTHER_PROFILE)
    elif invalid_case == "source_child":
        projection = _projection(source_child_ids=("c" * 64, "9" * 64))
    elif invalid_case == "child_count":
        projection = _projection(source_child_ids=("b" * 64, "c" * 64, "9" * 64))
    elif invalid_case == "effect":
        effect = OperationEffect.NONE
    elif invalid_case == "terminal":
        terminal = OperationTerminalCondition.REFUSED
    submitted: list[LedgerMergeRequest] = []
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
