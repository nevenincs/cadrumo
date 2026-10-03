"""Dependency CLI bridge correlates the authenticated inventory and receipt."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
import typer

from ....application.modelo.dependency_operation import (
    ModeloDependencyProjection,
    ModeloDependencyRequest,
    ModeloDependencySnapshot,
)
from ....core.operations import OperationEffect, OperationTerminalCondition
from .. import _modelo_work_verification_cli as handler
from .. import runtime_modelo_dependencies as bridge
from ..errors import CliRefusedBoundaryError
from ..registered_operation_contracts import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER = UUID("6bb00000-0000-4000-8000-0000000000bb")
_OPERATION_ID = "a" * 64


def _projection(
    *, profile_id: UUID = _PROFILE, filing_year: int = 2025, modelo: str | None = None
) -> ModeloDependencyProjection:
    return ModeloDependencyProjection(
        profile_id=profile_id,
        snapshot=ModeloDependencySnapshot(
            filing_year=filing_year,
            modelo_filter=modelo,
            period_filter=None,
            target_modelos=(),
            source_modelos=(),
            items=(),
            clean_state=None,
        ),
    )


def _client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bridge, "require_active_bucket_id", lambda: str(_PROFILE))
    monkeypatch.setattr(
        bridge, "require_profile_client", lambda *_args, **_kwargs: SimpleNamespace(profile_id=_PROFILE)
    )


def test_bridge_submits_exact_profile_and_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    _client(monkeypatch)
    submitted: list[ModeloDependencyRequest] = []

    def submit(_client: object, request: ModeloDependencyRequest, **_kwargs: object):
        submitted.append(request)
        return RegisteredOperationCompletion(
            operation_id=_OPERATION_ID, projection=_projection(modelo="303"), effect=OperationEffect.NONE
        )

    monkeypatch.setattr(bridge, "run_registered_operation", submit)
    read = bridge.read_modelo_dependencies(
        cast(typer.Context, cast(object, None)), filing_year=2025, modelo="303", period=None
    )
    assert read.completion.operation_id == _OPERATION_ID
    assert read.snapshot.modelo_filter == "303"
    assert submitted == [ModeloDependencyRequest(profile_id=_PROFILE, filing_year=2025, modelo="303")]


@pytest.mark.parametrize(
    ("profile_id", "filing_year", "modelo", "condition", "effect"),
    [
        (_OTHER, 2025, None, OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE),
        (_PROFILE, 2026, None, OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE),
        (_PROFILE, 2025, "303", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE),
        (_PROFILE, 2025, None, OperationTerminalCondition.REFUSED, OperationEffect.NONE),
        (_PROFILE, 2025, None, OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED),
    ],
)
def test_bad_projection_retains_submitted_receipt(
    monkeypatch: pytest.MonkeyPatch,
    profile_id: UUID,
    filing_year: int,
    modelo: str | None,
    condition: OperationTerminalCondition,
    effect: OperationEffect,
) -> None:
    _client(monkeypatch)
    monkeypatch.setattr(
        bridge,
        "run_registered_operation",
        lambda *_args, **_kwargs: RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=_projection(profile_id=profile_id, filing_year=filing_year, modelo=modelo),
            terminal_condition=condition,
            effect=effect,
        ),
    )
    with pytest.raises(CliRefusedBoundaryError) as refused:
        bridge.read_modelo_dependencies(
            cast(typer.Context, cast(object, None)), filing_year=2025, modelo=None, period=None
        )
    assert refused.value.context is not None
    assert refused.value.context["operation_id"] == _OPERATION_ID
    assert refused.value.context["effect"] == effect.value
    assert refused.value.context["terminal_condition"] == condition.value


def test_presentation_error_retains_completed_operation(monkeypatch: pytest.MonkeyPatch) -> None:
    completion = RegisteredOperationCompletion(
        operation_id=_OPERATION_ID, projection=_projection(), effect=OperationEffect.NONE
    )
    monkeypatch.setattr(handler, "activate_subcommand_output_language", lambda *_args: None)
    monkeypatch.setattr(
        handler,
        "read_modelo_dependencies",
        lambda *_args, **_kwargs: bridge.ModeloDependenciesRead(
            completion=completion, snapshot=completion.projection.snapshot
        ),
    )
    monkeypatch.setattr(
        handler, "emit_envelope", lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("private"))
    )
    with pytest.raises(CliRefusedBoundaryError) as refused:
        handler.work_dependencies(cast(typer.Context, cast(object, None)), year=2025)
    assert refused.value.context is not None
    assert refused.value.context["operation_id"] == _OPERATION_ID
    assert refused.value.context["effect"] == OperationEffect.NONE.value
    assert refused.value.__cause__ is None
