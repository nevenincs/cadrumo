"""Dependency CLI bridge correlates the authenticated inventory and receipt."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
import typer

from cadrumo_client.commands.errors import CliRefusedBoundaryError
from cadrumo_client.commands.registered_operation_contracts import RegisteredOperationCompletion

from ....application.modelo.dependency_operation import (
    ModeloDependencyProjection,
    ModeloDependencyRequest,
    ModeloDependencySnapshot,
)
from ....core.operations import OperationEffect, OperationTerminalCondition
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from .. import modelo_work_verification_cli
from .. import operation_modelo_dependencies as bridge

_YEAR = filing_year_envelope().horizon


pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER = UUID("6bb00000-0000-4000-8000-0000000000bb")
_OPERATION_ID = "a" * 64


def _projection(
    *, profile_id: UUID = _PROFILE, filing_year: int = _YEAR, modelo: str | None = None
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
        cast(typer.Context, cast(object, None)), filing_year=_YEAR, modelo="303", period=None
    )
    assert read.completion.operation_id == _OPERATION_ID
    assert read.snapshot.modelo_filter == "303"
    assert submitted == [ModeloDependencyRequest(profile_id=_PROFILE, filing_year=_YEAR, modelo="303")]


@pytest.mark.parametrize(
    ("profile_id", "filing_year", "modelo", "condition", "effect"),
    [
        (_OTHER, _YEAR, None, OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE),
        (_PROFILE, _YEAR + 1, None, OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE),
        (_PROFILE, _YEAR, "303", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE),
        (_PROFILE, _YEAR, None, OperationTerminalCondition.REFUSED, OperationEffect.NONE),
        (_PROFILE, _YEAR, None, OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED),
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
            cast(typer.Context, cast(object, None)), filing_year=_YEAR, modelo=None, period=None
        )
    assert refused.value.context is not None
    assert refused.value.context["operation_id"] == _OPERATION_ID
    assert refused.value.context["effect"] == effect.value
    assert refused.value.context["terminal_condition"] == condition.value


def test_presentation_error_retains_completed_operation(monkeypatch: pytest.MonkeyPatch) -> None:
    completion = RegisteredOperationCompletion(
        operation_id=_OPERATION_ID, projection=_projection(), effect=OperationEffect.NONE
    )
    monkeypatch.setattr(modelo_work_verification_cli, "activate_subcommand_output_language", lambda *_args: None)
    monkeypatch.setattr(
        modelo_work_verification_cli,
        "read_modelo_dependencies",
        lambda *_args, **_kwargs: bridge.ModeloDependenciesRead(
            completion=completion, snapshot=completion.projection.snapshot
        ),
    )
    monkeypatch.setattr(
        modelo_work_verification_cli,
        "emit_envelope",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("private")),
    )
    with pytest.raises(CliRefusedBoundaryError) as refused:
        modelo_work_verification_cli.work_dependencies(cast(typer.Context, cast(object, None)), year=_YEAR)
    assert refused.value.context is not None
    assert refused.value.context["operation_id"] == _OPERATION_ID
    assert refused.value.context["effect"] == OperationEffect.NONE.value
    assert refused.value.__cause__ is None
