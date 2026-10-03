"""CLI bridge correlates metadata selection with its registered comparison result."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Literal, cast
from uuid import UUID

import pytest
import typer

from ....application.modelo.taxation_comparison import TaxationRecommendation
from ....application.modelo.taxation_comparison_operation import (
    MODELO_TAXATION_COMPARISON_OPERATION_DEFINITION_ID,
    ModeloTaxationComparisonProjection,
    ModeloTaxationComparisonRequest,
)
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....core.period import Period
from ....domain.modelos.work_unit import WorkUnit, WorkUnitState, derive_work_unit_id
from .. import runtime_modelo_taxation_comparison as bridge
from ..errors import CliRefusedBoundaryError
from ..runtime_registered_operation import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")
_NOW = datetime(2026, 4, 10, 9, 0, tzinfo=UTC)
_OPERATION_ID = "a" * 64
_REVISION = "renta-test-2025"


def _unit(
    *,
    profile_id: UUID = _PROFILE,
    modelo: str = "100",
    filing_year: int = 2025,
    revision: str = _REVISION,
) -> WorkUnit:
    period = Period.from_year_and_code(filing_year, "0A")
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=str(profile_id),
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            revision_id=revision,
        ),
        bucket_id=str(profile_id),
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        revision_id=revision,
        name="Annual declaration",
        created_at=_NOW,
        updated_at=_NOW,
        state=WorkUnitState.BORRADOR,
    )


def _projection(
    unit: WorkUnit,
    *,
    profile_id: UUID = _PROFILE,
    work_unit_id: str | None = None,
    filing_year: int | None = None,
    modelo: Literal["100"] | None = None,
    revision: str | None = None,
) -> ModeloTaxationComparisonProjection:
    return ModeloTaxationComparisonProjection(
        profile_id=profile_id,
        work_unit_id=work_unit_id or unit.work_unit_id,
        filing_year=unit.filing_year if filing_year is None else filing_year,
        modelo="100" if modelo is None else modelo,
        revision=unit.revision_id if revision is None else revision,
        conjunta_cuota_resultante=str(Decimal("1250.00")),
        individual_cuota_resultante=str(Decimal("1800.00")),
        conjunta_resultado=str(Decimal("900.00")),
        individual_resultado=str(Decimal("1450.00")),
        delta_resultado=str(Decimal("550.00")),
        recommendation=TaxationRecommendation.CONJUNTA,
        recommendation_reason="conjunta saves 550.00 €",
        individual_branch_single_earner_only=True,
        individual_branch_caveat=(
            "The individual-mode figure is faithful only for a single-earner household; "
            "a two-earner comparison is not yet available."
        ),
    )


def _invoke(
    *,
    work_unit_id: str | None = None,
    modelo: str | None = None,
    year: int | None = None,
    period: str | None = None,
    revision: str | None = None,
    bucket_id: str | None = None,
) -> ModeloTaxationComparisonProjection:
    return bridge.compare_modelo_taxation(
        cast(typer.Context, cast(object, None)),
        work_unit_id=work_unit_id,
        modelo=modelo,
        year=year,
        period=period,
        revision=revision,
        bucket_id=bucket_id,
    )


def _bind(
    monkeypatch: pytest.MonkeyPatch,
    unit: WorkUnit,
    completion: RegisteredOperationCompletion[ModeloTaxationComparisonProjection],
    submitted: list[ModeloTaxationComparisonRequest],
    metadata_reads: list[dict[str, object]],
) -> None:
    client = SimpleNamespace(profile_id=_PROFILE)
    monkeypatch.setattr(bridge, "bound_profile_client", lambda _ctx: client)

    def read_metadata(_ctx: object, **kwargs: object) -> WorkUnit:
        metadata_reads.append(kwargs)
        assert kwargs["expected_profile_id"] == _PROFILE
        return unit

    def submit(
        submitted_client: object,
        request: ModeloTaxationComparisonRequest,
        **kwargs: object,
    ) -> RegisteredOperationCompletion[ModeloTaxationComparisonProjection]:
        assert submitted_client is client
        submitted.append(request)
        assert kwargs == {
            "definition_id": MODELO_TAXATION_COMPARISON_OPERATION_DEFINITION_ID,
            "subject_ref": profile_operation_subject(str(_PROFILE)),
            "result_type": ModeloTaxationComparisonProjection,
            "request_version": 1,
            "result_version": 1,
            "timeout": 120,
        }
        return completion

    monkeypatch.setattr(bridge, "read_modelo_work_unit", read_metadata)
    monkeypatch.setattr(bridge, "run_registered_operation", submit)


def test_bridge_uses_exact_metadata_selection_and_returns_correlated_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unit = _unit()
    projection = _projection(unit)
    submitted: list[ModeloTaxationComparisonRequest] = []
    metadata_reads: list[dict[str, object]] = []
    _bind(
        monkeypatch,
        unit,
        RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=projection,
            effect=OperationEffect.NONE,
            terminal_condition=OperationTerminalCondition.SUCCEEDED,
        ),
        submitted,
        metadata_reads,
    )

    selected = _invoke(
        work_unit_id=unit.work_unit_id,
        modelo="100",
        year=2025,
        period="0A",
        revision=unit.revision_id,
        bucket_id=str(_PROFILE),
    )

    assert selected is projection
    assert metadata_reads == [
        {
            "work_unit_id": unit.work_unit_id,
            "modelo": "100",
            "year": 2025,
            "period": "0A",
            "revision": unit.revision_id,
            "bucket_id": str(_PROFILE),
            "expected_profile_id": _PROFILE,
        }
    ]
    assert submitted == [ModeloTaxationComparisonRequest(profile_id=_PROFILE, work_unit_id=unit.work_unit_id)]
    assert selected.profile_id == _PROFILE
    assert selected.work_unit_id == unit.work_unit_id
    assert selected.filing_year == unit.filing_year
    assert selected.modelo == str(unit.modelo)
    assert selected.revision == unit.revision_id
    assert selected.individual_branch_single_earner_only is True


@pytest.mark.parametrize(
    ("case", "expected_effect", "terminal"),
    [
        ("profile", OperationEffect.NONE, OperationTerminalCondition.SUCCEEDED),
        ("work_unit", OperationEffect.NONE, OperationTerminalCondition.SUCCEEDED),
        ("year", OperationEffect.NONE, OperationTerminalCondition.SUCCEEDED),
        ("modelo", OperationEffect.NONE, OperationTerminalCondition.SUCCEEDED),
        ("revision", OperationEffect.NONE, OperationTerminalCondition.SUCCEEDED),
        ("effect", OperationEffect.UPDATED, OperationTerminalCondition.SUCCEEDED),
        ("terminal", OperationEffect.NONE, OperationTerminalCondition.REFUSED),
    ],
)
def test_bridge_refuses_unmatched_projection_or_operation_receipt(
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    expected_effect: OperationEffect,
    terminal: OperationTerminalCondition,
) -> None:
    unit = _unit()
    changes: dict[str, object] = {}
    if case == "profile":
        changes["profile_id"] = _OTHER_PROFILE
    elif case == "work_unit":
        changes["work_unit_id"] = "b" * 64
    elif case == "year":
        changes["filing_year"] = 2026
    elif case == "modelo":
        changes["modelo"] = "303"
    elif case == "revision":
        changes["revision"] = "other-renta-revision"
    projection = _projection(unit).model_copy(update=changes)
    submitted: list[ModeloTaxationComparisonRequest] = []
    metadata_reads: list[dict[str, object]] = []
    _bind(
        monkeypatch,
        unit,
        RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=projection,
            effect=expected_effect,
            terminal_condition=terminal,
            refusal_code="operation_denied" if case == "terminal" else None,
        ),
        submitted,
        metadata_reads,
    )

    with pytest.raises(CliRefusedBoundaryError) as refused:
        _invoke(work_unit_id=unit.work_unit_id, modelo="100", year=2025, period="0A", revision=unit.revision_id)

    assert len(metadata_reads) == 1
    assert len(submitted) == 1
    assert refused.value.context is not None
    assert refused.value.context["operation_id"] == _OPERATION_ID
    assert refused.value.context["reason"] == "runtime_invalid_frame"
    assert refused.value.context["effect"] == expected_effect.value
    assert refused.value.context["terminal_condition"] == terminal.value


def test_bridge_localizes_typed_incomplete_comparison_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    unit = _unit()
    _bind(
        monkeypatch,
        unit,
        RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=_projection(unit),
            effect=OperationEffect.NONE,
            terminal_condition=OperationTerminalCondition.SUCCEEDED,
        ),
        [],
        [],
    )
    context = {"operation_id": _OPERATION_ID, "reason": "REFUSED_TAXATION_COMPARISON", "effect": "none"}

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise CliRefusedBoundaryError("REFUSED_TAXATION_COMPARISON", context=context)

    monkeypatch.setattr(bridge, "run_registered_operation", refuse)
    with pytest.raises(CliRefusedBoundaryError) as error:
        _invoke(work_unit_id=unit.work_unit_id)
    assert error.value.translated_message == "errors.refused.refused_taxation_comparison"
    assert error.value.context == context


def test_bridge_does_not_submit_if_authenticated_metadata_selection_refuses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unit = _unit()
    submitted: list[object] = []
    metadata_reads: list[object] = []
    monkeypatch.setattr(
        bridge,
        "bound_profile_client",
        lambda _ctx: SimpleNamespace(profile_id=_PROFILE),
    )

    def refuse_metadata(*_args: object, **_kwargs: object) -> WorkUnit:
        metadata_reads.append(object())
        raise CliRefusedBoundaryError("runtime_profile_mismatch")

    monkeypatch.setattr(bridge, "read_modelo_work_unit", refuse_metadata)
    monkeypatch.setattr(bridge, "run_registered_operation", lambda *_args, **_kwargs: submitted.append(object()))

    with pytest.raises(CliRefusedBoundaryError, match="runtime_profile_mismatch"):
        _invoke(work_unit_id=unit.work_unit_id, bucket_id=str(_OTHER_PROFILE))

    assert len(metadata_reads) == 1
    assert submitted == []
