"""The CLI work-create bridge correlates success and bounded refusal receipts."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
import typer

from ....adapters.local_runtime.frontend_client import RuntimeFrontendRefusedError
from ....application.modelo.metadata_projection import ModeloWorkMetadataSnapshot
from ....application.modelo.work_create_operation import (
    MODELO_WORK_CREATE_APPLICABILITY_REFUSAL_CODE,
    ModeloWorkCreateProjection,
    ModeloWorkCreateRefusal,
    ModeloWorkCreateRequest,
    ModeloWorkCreateSuccess,
)
from ....application.operations.public_period import PublicPeriod
from ....core.operations import OperationEffect, OperationTerminalCondition
from ....core.period import Period
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from .. import runtime_modelo_work_create as bridge
from ..errors import CliRefusedBoundaryError
from ..registered_operation_contracts import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER = UUID("6bb00000-0000-4000-8000-0000000000bb")
_PERIOD = Period.from_year_and_code(2026, "1T")
_REVISION = "2026-y-siguientes"
_OPERATION_ID = "a" * 64


def _unit() -> ModeloWorkMetadataSnapshot:
    instant = datetime(2026, 3, 10, tzinfo=UTC)
    return ModeloWorkMetadataSnapshot.from_work_unit(
        WorkUnit(
            work_unit_id=derive_work_unit_id(
                bucket_id=str(_PROFILE),
                modelo="303",
                filing_year=2026,
                period=_PERIOD,
                revision_id=_REVISION,
            ),
            bucket_id=str(_PROFILE),
            modelo="303",
            filing_year=2026,
            period=_PERIOD,
            revision_id=_REVISION,
            name="Draft",
            created_at=instant,
            updated_at=instant,
        )
    )


def _invoke(*, bucket_id: str | None = None, allow_not_applicable: bool = False):
    return bridge.create_modelo_work(
        cast(typer.Context, cast(object, None)),
        modelo="303",
        period=_PERIOD,
        revision_id=_REVISION,
        bucket_id=bucket_id,
        name="Draft",
        actor="operator",
        causante_ccaa=None,
        allow_not_applicable=allow_not_applicable,
    )


def _bind(monkeypatch: pytest.MonkeyPatch, completion, submitted: list[ModeloWorkCreateRequest]) -> None:
    monkeypatch.setattr(bridge, "resolve_active_bucket_id", lambda: str(_PROFILE))
    monkeypatch.setattr(
        bridge, "require_profile_client", lambda *_args, **_kwargs: SimpleNamespace(profile_id=_PROFILE)
    )

    def submit(_client: object, request: ModeloWorkCreateRequest, **_kwargs: object):
        submitted.append(request)
        return completion

    monkeypatch.setattr(bridge, "run_registered_operation", submit)


def test_foreign_explicit_bucket_refused_before_submission(monkeypatch: pytest.MonkeyPatch) -> None:
    submitted: list[ModeloWorkCreateRequest] = []
    _bind(monkeypatch, None, submitted)
    with pytest.raises(RuntimeFrontendRefusedError):
        _invoke(bucket_id=str(_OTHER))
    assert submitted == []


@pytest.mark.parametrize(
    ("reused", "name_applied", "effect"),
    [
        (False, None, OperationEffect.UPDATED),
        (True, None, OperationEffect.NONE),
        (True, "Draft", OperationEffect.UPDATED),
    ],
)
def test_success_correlates_exact_request_and_effect(
    monkeypatch: pytest.MonkeyPatch, reused: bool, name_applied: str | None, effect: OperationEffect
) -> None:
    submitted: list[ModeloWorkCreateRequest] = []
    projection = ModeloWorkCreateProjection(
        profile_id=_PROFILE,
        period=PublicPeriod.from_period(_PERIOD),
        outcome=ModeloWorkCreateSuccess(
            unit=_unit(),
            reused=reused,
            name_applied=name_applied,
            applicability_guard_bypassed=False,
            advisory_keys=(),
        ),
    )
    _bind(
        monkeypatch,
        RegisteredOperationCompletion(operation_id=_OPERATION_ID, projection=projection, effect=effect),
        submitted,
    )
    observed = _invoke()
    assert observed.completion.operation_id == _OPERATION_ID
    assert observed.result == projection.outcome
    assert len(submitted) == 1
    assert submitted[0].profile_id == _PROFILE
    assert submitted[0].period == PublicPeriod.from_period(_PERIOD)
    assert submitted[0].revision_id == _REVISION
    assert submitted[0].allow_not_applicable is False


def test_valid_refusal_preserves_receipt_and_bounded_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    submitted: list[ModeloWorkCreateRequest] = []
    projection = ModeloWorkCreateProjection(
        profile_id=_PROFILE,
        period=PublicPeriod.from_period(_PERIOD),
        outcome=ModeloWorkCreateRefusal(modelo="303", reason="the profile is outside the declared taxpayer scope"),
    )
    _bind(
        monkeypatch,
        RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=projection,
            effect=OperationEffect.NONE,
            terminal_condition=OperationTerminalCondition.REFUSED,
            refusal_code=MODELO_WORK_CREATE_APPLICABILITY_REFUSAL_CODE,
        ),
        submitted,
    )
    with pytest.raises(CliRefusedBoundaryError) as refused:
        _invoke()
    details = refused.value.context
    assert details is not None
    assert details == {
        "modelo": "303",
        "reason": "the profile is outside the declared taxpayer scope",
        "operation_id": _OPERATION_ID,
        "refusal_code": MODELO_WORK_CREATE_APPLICABILITY_REFUSAL_CODE,
        "terminal_condition": "refused",
        "effect": "none",
    }
    assert len(submitted) == 1


@pytest.mark.parametrize("altered", ["profile", "period", "modelo", "revision", "allow", "effect", "terminal"])
def test_mismatched_success_preserves_bad_receipt_as_refusal(monkeypatch: pytest.MonkeyPatch, altered: str) -> None:
    unit = _unit()
    outcome = ModeloWorkCreateSuccess(
        unit=unit,
        reused=False,
        name_applied=None,
        applicability_guard_bypassed=altered == "allow",
        advisory_keys=(),
    )
    projection = ModeloWorkCreateProjection(
        profile_id=_PROFILE, period=PublicPeriod.from_period(_PERIOD), outcome=outcome
    )
    if altered == "profile":
        projection = projection.model_copy(update={"profile_id": _OTHER})
    elif altered == "period":
        projection = projection.model_copy(update={"period": PublicPeriod(filing_year=2026, code="2T")})
    elif altered == "modelo":
        projection = projection.model_copy(
            update={"outcome": outcome.model_copy(update={"unit": unit.model_copy(update={"modelo": "130"})})}
        )
    elif altered == "revision":
        projection = projection.model_copy(
            update={"outcome": outcome.model_copy(update={"unit": unit.model_copy(update={"revision_id": "other"})})}
        )
    effect = OperationEffect.NONE if altered == "effect" else OperationEffect.UPDATED
    terminal = OperationTerminalCondition.REFUSED if altered == "terminal" else OperationTerminalCondition.SUCCEEDED
    submitted: list[ModeloWorkCreateRequest] = []
    _bind(
        monkeypatch,
        RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=projection,
            effect=effect,
            terminal_condition=terminal,
            refusal_code=MODELO_WORK_CREATE_APPLICABILITY_REFUSAL_CODE if altered == "terminal" else None,
        ),
        submitted,
    )
    with pytest.raises(CliRefusedBoundaryError) as refused:
        _invoke()
    assert refused.value.context is not None
    assert refused.value.context["operation_id"] == _OPERATION_ID
    assert refused.value.context["effect"] == effect.value


@pytest.mark.parametrize("altered", ["profile", "period", "modelo", "code", "effect", "allow", "terminal"])
def test_malformed_refusal_never_becomes_success(monkeypatch: pytest.MonkeyPatch, altered: str) -> None:
    outcome = ModeloWorkCreateRefusal(modelo="303", reason="not applicable")
    projection = ModeloWorkCreateProjection(
        profile_id=_PROFILE, period=PublicPeriod.from_period(_PERIOD), outcome=outcome
    )
    if altered == "profile":
        projection = projection.model_copy(update={"profile_id": _OTHER})
    elif altered == "period":
        projection = projection.model_copy(update={"period": PublicPeriod(filing_year=2026, code="2T")})
    elif altered == "modelo":
        projection = projection.model_copy(update={"outcome": outcome.model_copy(update={"modelo": "130"})})
    effect = OperationEffect.UNKNOWN if altered == "effect" else OperationEffect.NONE
    terminal = OperationTerminalCondition.SUCCEEDED if altered == "terminal" else OperationTerminalCondition.REFUSED
    code = "REFUSED_MODELO_PROFILE_READINESS" if altered == "code" else MODELO_WORK_CREATE_APPLICABILITY_REFUSAL_CODE
    submitted: list[ModeloWorkCreateRequest] = []
    _bind(
        monkeypatch,
        RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=projection,
            effect=effect,
            terminal_condition=terminal,
            refusal_code=code,
        ),
        submitted,
    )
    with pytest.raises(CliRefusedBoundaryError) as refused:
        _invoke(allow_not_applicable=altered == "allow")
    assert refused.value.context is not None
    assert refused.value.context["operation_id"] == _OPERATION_ID
    assert refused.value.context["effect"] == effect.value
