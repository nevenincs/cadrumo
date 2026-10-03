"""The filing-record list bridge binds filters and receipt to its profile."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
import typer

from ....adapters.local_runtime.frontend_client import RuntimeFrontendRefusedError
from ....application.modelo.filing_record_list_operation import (
    MODELO_FILING_RECORD_LIST_OPERATION_DEFINITION_ID,
    ModeloFilingRecordListEntryProjection,
    ModeloFilingRecordListProjection,
    ModeloFilingRecordListRequest,
)
from ....application.user_profile.access_contracts import AccessDenialCode
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....core.period import Period
from ....domain.modelos.filing_record import (
    AeatConfirmationState,
    FilingDeclarationKind,
    FilingOrigin,
    ModeloRecordStatus,
    derive_filing_record_id,
)
from ....domain.modelos.work_unit import derive_work_unit_id
from .. import runtime_modelo_filing_record_list as bridge
from ..errors import CliRefusedBoundaryError
from ..runtime_registered_operation import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER = UUID("6bb00000-0000-4000-8000-0000000000bb")
_OPERATION_ID = "a" * 64
_NOW = datetime(2026, 4, 10, 9, 0, tzinfo=UTC)


def _row(*, profile_id: UUID = _PROFILE) -> ModeloFilingRecordListEntryProjection:
    period = Period.from_year_and_code(2026, "1T")
    work_unit_id = derive_work_unit_id(
        bucket_id=str(profile_id),
        modelo="303",
        filing_year=2026,
        period=period,
        revision_id="runtime-test-revision",
    )
    actor = "synthetic filing operator"
    return ModeloFilingRecordListEntryProjection(
        filing_record_id=derive_filing_record_id(
            work_unit_id=work_unit_id,
            calculation_revision_id="b" * 64,
            filed_by=actor,
        ),
        work_unit_id=work_unit_id,
        calculation_revision_id="b" * 64,
        bucket_id=str(profile_id),
        modelo="303",
        filing_year=2026,
        period="1T",
        filed_at=_NOW,
        filed_by=actor,
        member_nif=None,
        notes=None,
        origin=FilingOrigin.LOCAL,
        confirmation=AeatConfirmationState.PENDIENTE,
        declaration_kind=FilingDeclarationKind.ORIGINAL,
        aeat_register=None,
        aeat_accepted=False,
        status=ModeloRecordStatus.VIGENTE,
        superseded_at=None,
        superseded_by_filing_record_id=None,
        external_evidence=None,
        amends_filing_record_id=None,
    )


def _projection(row: ModeloFilingRecordListEntryProjection | None = None):
    records = (row,) if row is not None else ()
    return ModeloFilingRecordListProjection(
        profile_id=_PROFILE,
        modelo="303",
        include_superseded=False,
        record_count=len(records),
        records=records,
    )


def _context():
    return cast(typer.Context, cast(object, None))


def _bind(
    monkeypatch: pytest.MonkeyPatch,
    completion: RegisteredOperationCompletion[ModeloFilingRecordListProjection],
    submitted: list[ModeloFilingRecordListRequest],
) -> None:
    monkeypatch.setattr(
        bridge,
        "bound_profile_client",
        lambda *_args, **_kwargs: SimpleNamespace(profile_id=_PROFILE),
    )

    def submit(_client: object, request: ModeloFilingRecordListRequest, **kwargs: object):
        submitted.append(request)
        assert kwargs["definition_id"] == MODELO_FILING_RECORD_LIST_OPERATION_DEFINITION_ID
        assert kwargs["subject_ref"] == profile_operation_subject(str(_PROFILE))
        assert kwargs["result_type"] is ModeloFilingRecordListProjection
        assert kwargs["request_version"] == kwargs["result_version"] == 1
        return completion

    monkeypatch.setattr(bridge, "run_registered_operation", submit)


def test_bridge_submits_profile_and_filters_then_returns_existing_row_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    submitted: list[ModeloFilingRecordListRequest] = []
    projection = _projection(_row())
    _bind(
        monkeypatch,
        RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=projection,
            effect=OperationEffect.NONE,
            terminal_condition=OperationTerminalCondition.SUCCEEDED,
        ),
        submitted,
    )

    result = bridge.read_modelo_filing_record_list(
        _context(),
        bucket_id=str(_PROFILE),
        modelo="303",
        include_superseded=False,
    )

    assert len(result) == 1
    assert result[0].bucket_id == str(_PROFILE)
    assert result[0].modelo == "303"
    assert result[0].period == Period.from_year_and_code(2026, "1T")
    assert result[0].live_submission is False
    assert submitted == [ModeloFilingRecordListRequest(profile_id=_PROFILE, modelo="303", include_superseded=False)]


def test_bridge_refuses_foreign_bucket_filter_before_submit(monkeypatch: pytest.MonkeyPatch) -> None:
    submitted: list[ModeloFilingRecordListRequest] = []
    _bind(
        monkeypatch,
        RegisteredOperationCompletion(
            operation_id=_OPERATION_ID, projection=_projection(), effect=OperationEffect.NONE
        ),
        submitted,
    )

    with pytest.raises(RuntimeFrontendRefusedError) as refused:
        bridge.read_modelo_filing_record_list(
            _context(),
            bucket_id=str(_OTHER),
            modelo=None,
            include_superseded=False,
        )
    assert refused.value.reason == AccessDenialCode.PROFILE_MISMATCH.value
    assert submitted == []


@pytest.mark.parametrize(
    ("effect", "terminal_condition"),
    [
        (OperationEffect.UPDATED, OperationTerminalCondition.SUCCEEDED),
        (OperationEffect.NONE, OperationTerminalCondition.REFUSED),
    ],
)
def test_bridge_refuses_non_none_or_unsettled_receipt(
    monkeypatch: pytest.MonkeyPatch,
    effect: OperationEffect,
    terminal_condition: OperationTerminalCondition,
) -> None:
    submitted: list[ModeloFilingRecordListRequest] = []
    _bind(
        monkeypatch,
        RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=_projection(_row()),
            effect=effect,
            terminal_condition=terminal_condition,
        ),
        submitted,
    )

    with pytest.raises(CliRefusedBoundaryError) as refused:
        bridge.read_modelo_filing_record_list(_context(), bucket_id=None, modelo="303", include_superseded=False)
    details = refused.value.context
    assert details is not None
    assert details["reason"] == "runtime_invalid_frame"
    assert len(submitted) == 1


def test_bridge_refuses_foreign_rows_even_when_projection_was_constructed_unsafely(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    submitted: list[ModeloFilingRecordListRequest] = []
    invalid = ModeloFilingRecordListProjection.model_construct(
        profile_id=_PROFILE,
        modelo="303",
        include_superseded=False,
        record_count=1,
        records=(_row(profile_id=_OTHER),),
    )
    _bind(
        monkeypatch,
        RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=invalid,
            effect=OperationEffect.NONE,
            terminal_condition=OperationTerminalCondition.SUCCEEDED,
        ),
        submitted,
    )

    with pytest.raises(CliRefusedBoundaryError):
        bridge.read_modelo_filing_record_list(_context(), bucket_id=None, modelo="303", include_superseded=False)
    assert len(submitted) == 1


def test_bridge_correlates_malformed_row_conversion_as_invalid_frame(monkeypatch: pytest.MonkeyPatch) -> None:
    submitted: list[ModeloFilingRecordListRequest] = []
    malformed_row = _row().model_copy(update={"period": "bad"})
    invalid = ModeloFilingRecordListProjection.model_construct(
        profile_id=_PROFILE,
        modelo="303",
        include_superseded=False,
        record_count=1,
        records=(malformed_row,),
    )
    _bind(
        monkeypatch,
        RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=invalid,
            effect=OperationEffect.NONE,
            terminal_condition=OperationTerminalCondition.SUCCEEDED,
        ),
        submitted,
    )

    with pytest.raises(CliRefusedBoundaryError) as refused:
        bridge.read_modelo_filing_record_list(_context(), bucket_id=None, modelo="303", include_superseded=False)
    details = refused.value.context
    assert details is not None
    assert details["reason"] == "runtime_invalid_frame"
    assert len(submitted) == 1
