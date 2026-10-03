"""The local-observation CLI bridge enforces exact-profile mutation receipts."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
import typer

from ....application.calculations.observations_repository import ObservationSourceKind
from ....application.modelo.filing_record_view_operation import (
    ModeloFilingObservationLayerProjection,
    ModeloFilingObservationLayersProjection,
    ModeloFilingObservationOverrideProjection,
)
from ....application.modelo.local_observation_operation import (
    MODELO_LOCAL_OBSERVATION_OPERATION_DEFINITION_ID,
    ModeloLocalObservationCasillaValue,
    ModeloLocalObservationMutationProjection,
    ModeloLocalObservationMutationRequest,
)
from ....application.operations.public_period import PublicPeriod
from ....core.operations import (
    OperationEffect,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ....core.period import Period
from .. import runtime_modelo_local_observation as bridge
from .._filing_chain_payloads import ObservationLayersPayload
from ..errors import CliRefusedBoundaryError
from ..runtime_registered_operation import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_NOW = datetime(2026, 4, 10, 9, 0, tzinfo=UTC)
_OPERATION_ID = "a" * 64
_PERIOD = Period.from_year_and_code(2026, "1T")
_PUBLIC_PERIOD = PublicPeriod(filing_year=2026, code="1T")


def _record_projection(*, profile_id: UUID = _PROFILE) -> ModeloLocalObservationMutationProjection:
    actor = f"profile:{_PROFILE}"
    pending = ModeloFilingObservationLayerProjection(
        source_kind=ObservationSourceKind.OPERATOR_MANUAL,
        official_evidence=False,
        captured_at=_NOW,
        stamped_revision_id="revision-1",
        casilla_values=(("base_imponible", "125.00"),),
    )
    override = ModeloFilingObservationOverrideProjection(
        actor=actor,
        reason="operator estimate",
        recorded_at=_NOW,
        replaced_values=(),
    )
    return ModeloLocalObservationMutationProjection(
        profile_id=profile_id,
        action="recorded",
        modelo="130",
        period=_PUBLIC_PERIOD,
        revision_id="revision-1",
        observation_key="130:2026:1T",
        source_kind=ObservationSourceKind.OPERATOR_MANUAL,
        casilla_values=(ModeloLocalObservationCasillaValue(casilla_id="base_imponible", value="125.00"),),
        captured_at=_NOW,
        captured_by=actor,
        reason="operator estimate",
        observation_layers=ModeloFilingObservationLayersProjection(
            modelo="130",
            filing_year=2026,
            period="1T",
            pending_local=pending,
            effective_source_kind=ObservationSourceKind.OPERATOR_MANUAL,
            override=override,
        ),
    )


def _clear_projection(*, actor: str) -> ModeloLocalObservationMutationProjection:
    return ModeloLocalObservationMutationProjection(
        profile_id=_PROFILE,
        action="cleared",
        modelo="130",
        period=_PUBLIC_PERIOD,
        observation_key="130:2026:1T",
        captured_at=_NOW,
        captured_by=actor,
        reason="remove local override",
        observation_layers=ModeloFilingObservationLayersProjection(
            modelo="130",
            filing_year=2026,
            period="1T",
            effective_source_kind=None,
        ),
    )


def _bind(
    monkeypatch: pytest.MonkeyPatch,
    completion: RegisteredOperationCompletion[ModeloLocalObservationMutationProjection],
    submitted: list[ModeloLocalObservationMutationRequest],
) -> None:
    client = SimpleNamespace(profile_id=_PROFILE)
    monkeypatch.setattr(bridge, "bound_profile_client", lambda *_args, **_kwargs: client)

    def submit(
        submitted_client: object,
        request: ModeloLocalObservationMutationRequest,
        **kwargs: object,
    ) -> RegisteredOperationCompletion[ModeloLocalObservationMutationProjection]:
        submitted.append(request)
        assert submitted_client is client
        assert kwargs["definition_id"] == MODELO_LOCAL_OBSERVATION_OPERATION_DEFINITION_ID
        assert kwargs["subject_ref"] == profile_operation_subject(str(_PROFILE))
        assert kwargs["result_type"] is ModeloLocalObservationMutationProjection
        assert kwargs["request_version"] == kwargs["result_version"] == 1
        return completion

    monkeypatch.setattr(bridge, "run_registered_operation", submit)


def _record():
    return bridge.record_modelo_local_observation(
        cast(typer.Context, cast(object, None)),
        modelo="130",
        period=_PERIOD,
        casilla_values={"base_imponible": Decimal("125.00")},
        actor=None,
        reason="operator estimate",
    )


def _clear(*, actor: str):
    return bridge.clear_modelo_local_observation(
        cast(typer.Context, cast(object, None)),
        modelo="130",
        period=_PERIOD,
        actor=actor,
        reason="remove local override",
    )


def test_record_submits_exact_profile_and_projects_text_values(monkeypatch: pytest.MonkeyPatch) -> None:
    submitted: list[ModeloLocalObservationMutationRequest] = []
    completion = RegisteredOperationCompletion(
        operation_id=_OPERATION_ID,
        projection=_record_projection(),
        effect=OperationEffect.UPDATED,
        terminal_condition=OperationTerminalCondition.SUCCEEDED,
    )
    _bind(monkeypatch, completion, submitted)

    result = _record()

    assert len(submitted) == 1
    assert submitted[0].profile_id == _PROFILE
    assert submitted[0].actor is None
    assert submitted[0].casilla_values == (
        ModeloLocalObservationCasillaValue(casilla_id="base_imponible", value="125.00"),
    )
    assert result.action == "recorded"
    assert result.captured_by == f"profile:{_PROFILE}"
    assert result.casilla_values == {"base_imponible": "125.00"}


def test_clear_submits_exact_profile_and_preserves_explicit_actor(monkeypatch: pytest.MonkeyPatch) -> None:
    actor = "data-entry operator"
    submitted: list[ModeloLocalObservationMutationRequest] = []
    completion = RegisteredOperationCompletion(
        operation_id=_OPERATION_ID,
        projection=_clear_projection(actor=actor),
        effect=OperationEffect.UPDATED,
        terminal_condition=OperationTerminalCondition.SUCCEEDED,
    )
    _bind(monkeypatch, completion, submitted)

    result = _clear(actor=actor)

    assert len(submitted) == 1
    assert submitted[0].profile_id == _PROFILE
    assert submitted[0].action == "clear"
    assert submitted[0].actor == actor
    assert submitted[0].casilla_values == ()
    assert result.action == "cleared"
    assert result.captured_by == actor
    assert result.casilla_values == {}
    assert isinstance(result.observation_layers, ObservationLayersPayload)
    assert result.observation_layers.pending_local is None


@pytest.mark.parametrize(
    ("effect", "terminal_condition"),
    [
        (OperationEffect.NONE, OperationTerminalCondition.SUCCEEDED),
        (OperationEffect.UPDATED, OperationTerminalCondition.REFUSED),
    ],
)
def test_record_rejects_receipt_effect_or_terminal_mismatch(
    monkeypatch: pytest.MonkeyPatch,
    effect: OperationEffect,
    terminal_condition: OperationTerminalCondition,
) -> None:
    submitted: list[ModeloLocalObservationMutationRequest] = []
    _bind(
        monkeypatch,
        RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=_record_projection(),
            effect=effect,
            terminal_condition=terminal_condition,
            refusal_code="operation_refused" if terminal_condition is OperationTerminalCondition.REFUSED else None,
        ),
        submitted,
    )

    with pytest.raises(CliRefusedBoundaryError) as refused:
        _record()

    assert refused.value.context is not None
    assert refused.value.context["reason"] == "runtime_invalid_frame"
    assert refused.value.context["operation_id"] == _OPERATION_ID


def test_record_rejects_malformed_projection(monkeypatch: pytest.MonkeyPatch) -> None:
    projection = _record_projection()
    malformed = ModeloLocalObservationMutationProjection.model_construct(
        **(projection.model_dump(mode="python") | {"revision_id": None})
    )
    submitted: list[ModeloLocalObservationMutationRequest] = []
    _bind(
        monkeypatch,
        RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=malformed,
            effect=OperationEffect.UPDATED,
            terminal_condition=OperationTerminalCondition.SUCCEEDED,
        ),
        submitted,
    )

    with pytest.raises(CliRefusedBoundaryError) as refused:
        _record()

    assert refused.value.context is not None
    assert refused.value.context["reason"] == "runtime_invalid_frame"
    assert refused.value.context["operation_id"] == _OPERATION_ID


def test_record_rejects_foreign_profile_projection(monkeypatch: pytest.MonkeyPatch) -> None:
    submitted: list[ModeloLocalObservationMutationRequest] = []
    _bind(
        monkeypatch,
        RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=_record_projection(profile_id=UUID("6bb00000-0000-4000-8000-0000000000bb")),
            effect=OperationEffect.UPDATED,
            terminal_condition=OperationTerminalCondition.SUCCEEDED,
        ),
        submitted,
    )

    with pytest.raises(CliRefusedBoundaryError) as refused:
        _record()

    assert refused.value.context is not None
    assert refused.value.context["reason"] == "runtime_invalid_frame"
