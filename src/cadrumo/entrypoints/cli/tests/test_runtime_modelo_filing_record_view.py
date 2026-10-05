"""The filing-record view bridge correlates its profile and exact receipt ID."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
import typer
from pydantic import ValidationError

from ....application.calculations.observations_repository import ObservationSourceKind
from ....application.modelo.filing_record_list_contracts import ModeloFilingRecordListEntryProjection
from ....application.modelo.filing_record_view_operation import (
    MODELO_FILING_RECORD_VIEW_OPERATION_DEFINITION_ID,
    ModeloFilingObservationLayerProjection,
    ModeloFilingObservationLayersProjection,
    ModeloFilingObservationOverrideProjection,
    ModeloFilingRecordViewProjection,
    ModeloFilingRecordViewRequest,
)
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....core.period import Period
from ....domain.modelos.filing_record import (
    AeatConfirmationState,
    FilingDeclarationKind,
    FilingOrigin,
    ModeloRecord,
    derive_filing_record_id,
)
from ....domain.modelos.work_unit import derive_work_unit_id
from .. import runtime_modelo_filing_record_view as bridge
from .._filing_chain_payloads import (
    ObservationLayerPayload,
    ObservationLayersPayload,
    ObservationOverridePayload,
)
from ..errors import CliRefusedBoundaryError
from ..registered_operation_contracts import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")
_NOW = datetime(2026, 4, 10, 9, 0, tzinfo=UTC)
_OPERATION_ID = "a" * 64


def _projection(*, profile_id: UUID = _PROFILE, request_id: str | None = None):
    period = Period.from_year_and_code(2026, "1T")
    unit_id = derive_work_unit_id(
        bucket_id=str(_PROFILE), modelo="303", filing_year=2026, period=period, revision_id="test-revision"
    )
    filing_id = derive_filing_record_id(
        work_unit_id=unit_id,
        calculation_revision_id="b" * 64,
        filed_by="test operator",
    )
    record = ModeloRecord(
        filing_record_id=filing_id,
        work_unit_id=unit_id,
        calculation_revision_id="b" * 64,
        bucket_id=str(_PROFILE),
        modelo="303",
        filing_year=2026,
        period=period,
        filed_at=_NOW,
        filed_by="test operator",
        origin=FilingOrigin.LOCAL,
        confirmation=AeatConfirmationState.PENDIENTE,
        declaration_kind=FilingDeclarationKind.ORIGINAL,
    )
    official = ModeloFilingObservationLayerProjection(
        source_kind=ObservationSourceKind.AEAT_CSV_REGISTER,
        official_evidence=True,
        captured_at=_NOW,
        stamped_revision_id="revision-2026",
        casilla_values=(("01", "10.25"),),
    )
    pending = ModeloFilingObservationLayerProjection(
        source_kind=ObservationSourceKind.OPERATOR_MANUAL,
        official_evidence=False,
        captured_at=_NOW,
        stamped_revision_id="revision-2026",
        casilla_values=(("01", "11.50"),),
    )
    layers = ModeloFilingObservationLayersProjection(
        modelo="303",
        filing_year=2026,
        period="1T",
        official=official,
        pending_local=pending,
        effective_source_kind=ObservationSourceKind.OPERATOR_MANUAL,
        override=ModeloFilingObservationOverrideProjection(
            actor="operator",
            reason="corrected from supporting evidence",
            recorded_at=_NOW,
            replaced_source_kind=ObservationSourceKind.AEAT_CSV_REGISTER,
            replaced_values=(("01", "10.25"),),
        ),
    )
    return ModeloFilingRecordViewProjection(
        profile_id=profile_id,
        filing_record_id=request_id or filing_id,
        record=ModeloFilingRecordListEntryProjection.from_record(record),
        observation_layers=layers,
    )


def _bind(monkeypatch: pytest.MonkeyPatch, completion, submitted: list[ModeloFilingRecordViewRequest]) -> None:
    monkeypatch.setattr(
        bridge,
        "bound_profile_client",
        lambda *_args, **_kwargs: SimpleNamespace(profile_id=_PROFILE),
    )

    def submit(_client: object, request: ModeloFilingRecordViewRequest, **kwargs: object):
        submitted.append(request)
        assert kwargs["definition_id"] == MODELO_FILING_RECORD_VIEW_OPERATION_DEFINITION_ID
        assert kwargs["subject_ref"] == profile_operation_subject(str(_PROFILE))
        assert kwargs["result_type"] is ModeloFilingRecordViewProjection
        assert kwargs["request_version"] == kwargs["result_version"] == 1
        return completion

    monkeypatch.setattr(bridge, "run_registered_operation", submit)


def _invoke(record_id: str):
    return bridge.read_modelo_filing_record_view(
        cast(typer.Context, cast(object, None)),
        filing_record_id=record_id,
    )


def test_bridge_submits_bound_profile_and_restores_renderer_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    projection = _projection()
    submitted: list[ModeloFilingRecordViewRequest] = []
    _bind(
        monkeypatch,
        RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=projection,
            effect=OperationEffect.NONE,
        ),
        submitted,
    )

    record, layers = _invoke(projection.filing_record_id)

    assert record.filing_record_id == projection.filing_record_id
    assert record.bucket_id == str(_PROFILE)
    assert layers == ObservationLayersPayload(
        official=ObservationLayerPayload(
            source_kind=ObservationSourceKind.AEAT_CSV_REGISTER,
            official_evidence=True,
            captured_at=_NOW,
            stamped_revision_id="revision-2026",
            casilla_values={"01": "10.25"},
        ),
        pending_local=ObservationLayerPayload(
            source_kind=ObservationSourceKind.OPERATOR_MANUAL,
            official_evidence=False,
            captured_at=_NOW,
            stamped_revision_id="revision-2026",
            casilla_values={"01": "11.50"},
        ),
        effective_source_kind=ObservationSourceKind.OPERATOR_MANUAL,
        override=ObservationOverridePayload(
            actor="operator",
            reason="corrected from supporting evidence",
            recorded_at=_NOW,
            replaced_source_kind=ObservationSourceKind.AEAT_CSV_REGISTER,
            replaced_values={"01": "10.25"},
        ),
    )
    assert len(submitted) == 1
    assert submitted[0].profile_id == _PROFILE
    assert submitted[0].filing_record_id == projection.filing_record_id


@pytest.mark.parametrize(
    "invalid_case",
    [
        "profile",
        "receipt",
        "effect",
        "terminal",
    ],
)
def test_bridge_rejects_profile_receipt_effect_or_terminal_mismatch(
    monkeypatch: pytest.MonkeyPatch,
    invalid_case: str,
) -> None:
    projection = _projection()
    effect = OperationEffect.UPDATED if invalid_case == "effect" else OperationEffect.NONE
    terminal_condition = (
        OperationTerminalCondition.REFUSED if invalid_case == "terminal" else OperationTerminalCondition.SUCCEEDED
    )
    if invalid_case == "profile":
        projection = ModeloFilingRecordViewProjection.model_construct(
            **(projection.model_dump(mode="python") | {"profile_id": _OTHER_PROFILE})
        )
    elif invalid_case == "receipt":
        projection = ModeloFilingRecordViewProjection.model_construct(
            **(projection.model_dump(mode="python") | {"filing_record_id": "c" * 64})
        )
    submitted: list[ModeloFilingRecordViewRequest] = []
    _bind(
        monkeypatch,
        RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=projection,
            effect=effect,
            terminal_condition=terminal_condition,
        ),
        submitted,
    )

    with pytest.raises(CliRefusedBoundaryError) as refused:
        _invoke(_projection().filing_record_id)
    assert refused.value.context is not None
    assert refused.value.context["reason"] == "runtime_invalid_frame"


def test_bridge_validates_record_id_before_submission(monkeypatch: pytest.MonkeyPatch) -> None:
    submitted: list[object] = []
    monkeypatch.setattr(
        bridge,
        "bound_profile_client",
        lambda *_args, **_kwargs: SimpleNamespace(profile_id=_PROFILE),
    )
    monkeypatch.setattr(bridge, "run_registered_operation", lambda *_args, **_kwargs: submitted.append(object()))

    with pytest.raises(ValidationError):
        _invoke("not-a-content-id")
    assert submitted == []
