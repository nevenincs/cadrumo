"""Focused public disclosure and scope checks for persisted expediente reads."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from ....core.errors.hierarchy import NoActiveProfileError
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....core.period import Period
from ...operations.access_resolution import OperationAccessContext
from ...operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ...operations.owner import OperationExecutorContext
from ...operations.registry import OperationFrontendProjection
from ...user_profile.access_contracts import AccessAction, AccessDenialCode, Availability
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..expedientes import PersistedExpedientesSnapshot
from ..expedientes_ports import ExpedientesDeclaration, ExpedientesDeclarationReaderProtocol, ExpedientesPorts
from ..expedientes_read_operation import (
    EXPEDIENTES_LIST_DEFINITION_ID,
    EXPEDIENTES_SHOW_DEFINITION_ID,
    ExpedientesListExecutor,
    ExpedientesListOperationReport,
    ExpedientesListRequest,
    ExpedientesShowOperationReport,
    ExpedientesShowPublicResultV1,
    ExpedientesShowRequest,
    build_expedientes_show_definition,
    build_expedientes_show_registration,
    resolve_expedientes_show_access,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("11111111-1111-4111-8111-111111111111")
_OTHER_PROFILE = UUID("22222222-2222-4222-8222-222222222222")
_NOW = datetime(2025, 4, 15, 10, tzinfo=UTC)


class _ExecutorEvents:
    def __init__(self) -> None:
        self.phases: list[str] = []
        self.effects: list[OperationEffect] = []

    async def phase(self, value: str) -> None:
        self.phases.append(value)

    async def effect(self, value: OperationEffect) -> None:
        self.effects.append(value)


class _ExecutorOperands:
    def __init__(self) -> None:
        self.values: list[BaseModel] = []

    async def put(self, value: BaseModel, *, written_at: datetime) -> str:
        assert written_at.tzinfo is not None
        self.values.append(value)
        return "synthetic-encrypted-result-reference"


def _executor_context(
    definition_id: str,
    *,
    subject_ref: str | None = None,
    events: _ExecutorEvents,
) -> tuple[OperationExecutorContext, _ExecutorOperands]:
    identity = OperationIdentity(
        operation_id="e" * 64,
        definition_id=definition_id,
        subject_ref=subject_ref or profile_operation_subject(str(_PROFILE)),
    )
    operands = _ExecutorOperands()
    return cast(
        OperationExecutorContext,
        SimpleNamespace(identity=identity, events=events, operands=operands),
    ), operands


class _EmptySnapshotRepository:
    def __init__(self, bucket_id: str) -> None:
        self.bucket_id = bucket_id

    def exists(self, snapshot_id: str) -> bool:
        return False

    def load(self, snapshot_id: str) -> PersistedExpedientesSnapshot:
        raise KeyError(snapshot_id)

    def list_snapshots(self) -> tuple[PersistedExpedientesSnapshot, ...]:
        return ()

    def resolve(self, snapshot_id: str) -> PersistedExpedientesSnapshot:
        raise KeyError(snapshot_id)

    def save(self, snapshot: PersistedExpedientesSnapshot) -> None:
        raise AssertionError("read-only list executor must not save snapshots")


def _registration():
    def unused_ports(*, bucket_id: str) -> ExpedientesPorts:
        raise AssertionError(f"executor unexpectedly composed ports for {bucket_id}")

    definition = build_expedientes_show_definition(unused_ports)
    return build_expedientes_show_registration(definition)


def _receipt(*, effect: OperationEffect = OperationEffect.NONE) -> OperationTerminalReceipt:
    return OperationTerminalReceipt(
        identity=OperationIdentity(
            operation_id="a" * 64,
            definition_id=EXPEDIENTES_SHOW_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(_PROFILE)),
        ),
        revision=0,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=effect,
        settled_at=_NOW,
        result_ref="result-ref",
    )


def test_list_executor_reads_the_exact_profile_and_records_empty_result(monkeypatch: pytest.MonkeyPatch) -> None:
    import cadrumo.application.live.expedientes_read_operation as operation

    events = _ExecutorEvents()
    composed_buckets: list[str] = []
    context, operands = _executor_context(EXPEDIENTES_LIST_DEFINITION_ID, events=events)
    request = OperationRequest[ExpedientesListRequest](
        definition_id=EXPEDIENTES_LIST_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=ExpedientesListRequest(profile_id=_PROFILE),
    )

    def ports_factory(*, bucket_id: str) -> ExpedientesPorts:
        composed_buckets.append(bucket_id)
        return ExpedientesPorts(
            declaration_reader=cast(ExpedientesDeclarationReaderProtocol, object()),
            snapshot_repository_factory=_EmptySnapshotRepository,
        )

    monkeypatch.setattr(operation, "require_active_bucket_id", lambda: str(_PROFILE))

    result_ref = asyncio.run(ExpedientesListExecutor(ports_factory).execute(request, context))

    assert result_ref == "synthetic-encrypted-result-reference"
    assert composed_buckets == [str(_PROFILE)]
    assert events.phases == ["expedientes-list.read", "expedientes-list.result"]
    assert events.effects == [OperationEffect.NONE]
    assert len(operands.values) == 1
    report = operands.values[0]
    assert isinstance(report, ExpedientesListOperationReport)
    assert report.bucket_id == str(_PROFILE)
    assert report.rows == ()


@pytest.mark.parametrize(
    ("request_definition_id", "context_definition_id", "context_subject_ref"),
    [
        (
            "live.expedientes.list.other",
            "live.expedientes.list.other",
            profile_operation_subject(str(_PROFILE)),
        ),
        (
            EXPEDIENTES_LIST_DEFINITION_ID,
            "live.expedientes.other",
            profile_operation_subject(str(_PROFILE)),
        ),
        (
            EXPEDIENTES_LIST_DEFINITION_ID,
            EXPEDIENTES_LIST_DEFINITION_ID,
            profile_operation_subject(str(_OTHER_PROFILE)),
        ),
    ],
)
def test_list_executor_refuses_request_or_context_identity_mismatch_before_work(
    monkeypatch: pytest.MonkeyPatch,
    request_definition_id: str,
    context_definition_id: str,
    context_subject_ref: str,
) -> None:
    import cadrumo.application.live.expedientes_read_operation as operation

    events = _ExecutorEvents()
    composed_buckets: list[str] = []
    context, operands = _executor_context(
        context_definition_id,
        subject_ref=context_subject_ref,
        events=events,
    )
    request = OperationRequest[ExpedientesListRequest](
        definition_id=request_definition_id,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=ExpedientesListRequest(profile_id=_PROFILE),
    )

    def unexpected_ports_factory(*, bucket_id: str) -> ExpedientesPorts:
        composed_buckets.append(bucket_id)
        raise AssertionError("identity refusal must happen before composing expedientes ports")

    monkeypatch.setattr(operation, "require_active_bucket_id", lambda: str(_PROFILE))

    with pytest.raises(ProfileAccessRefusedError) as refused:
        asyncio.run(ExpedientesListExecutor(unexpected_ports_factory).execute(request, context))

    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH
    assert events.phases == []
    assert events.effects == []
    assert composed_buckets == []
    assert operands.values == []


def test_list_executor_preserves_missing_profile_precedence_before_work(monkeypatch: pytest.MonkeyPatch) -> None:
    import cadrumo.application.live.expedientes_read_operation as operation

    events = _ExecutorEvents()
    composed_buckets: list[str] = []
    context, operands = _executor_context(
        "live.expedientes.other",
        subject_ref=profile_operation_subject(str(_OTHER_PROFILE)),
        events=events,
    )
    request = OperationRequest[ExpedientesListRequest](
        definition_id=EXPEDIENTES_LIST_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=ExpedientesListRequest(profile_id=_PROFILE),
    )

    def no_active_profile() -> str:
        raise NoActiveProfileError(translated_message="synthetic missing active profile")

    def unexpected_ports_factory(*, bucket_id: str) -> ExpedientesPorts:
        composed_buckets.append(bucket_id)
        raise AssertionError("missing active profile must refuse before composing expedientes ports")

    monkeypatch.setattr(operation, "require_active_bucket_id", no_active_profile)

    with pytest.raises(NoActiveProfileError):
        asyncio.run(ExpedientesListExecutor(unexpected_ports_factory).execute(request, context))

    assert events.phases == []
    assert events.effects == []
    assert composed_buckets == []
    assert operands.values == []


def test_show_projection_preserves_period_and_all_existing_declaration_fields() -> None:
    declaration = ExpedientesDeclaration(
        modelo="303",
        ejercicio=2025,
        period=Period.from_year_and_code(2025, "1T"),
        expediente_id="12345678901234567890",
        estado="ALTA",
        tipo_solicitud="Presentación",
        observaciones="Synthetic reference",
        presented_at=_NOW,
        justificante_link_text="Justificante",
        archive_link_text="Archivo",
        declaration_copy_link_text="Copia",
        justificante_cell_index=7,
        archive_cell_index=8,
        declaration_copy_cell_index=9,
    )
    report = ExpedientesShowOperationReport(
        snapshot=PersistedExpedientesSnapshot(
            snapshot_id="b" * 64,
            bucket_id=str(_PROFILE),
            captured_at=_NOW,
            source_url="https://sede.example/expedientes",
            authenticated_identity="12345678Z",
            declarations=(declaration,),
            persisted_at=_NOW,
        )
    )
    projector = _registration().result_projector
    assert projector is not None

    result = projector(report, _receipt())

    assert isinstance(result, ExpedientesShowPublicResultV1)
    assert result.declaration_count == 1
    assert result.declarations[0].period == declaration.period.registry_token
    assert result.declarations[0].observaciones == "Synthetic reference"
    assert result.declarations[0].declaration_copy_cell_index == 9
    assert set(result.declarations[0].model_dump()) == {
        "modelo",
        "ejercicio",
        "period",
        "expediente_id",
        "estado",
        "tipo_solicitud",
        "observaciones",
        "presented_at",
        "justificante_link_text",
        "archive_link_text",
        "declaration_copy_link_text",
        "justificante_cell_index",
        "archive_cell_index",
        "declaration_copy_cell_index",
        "mode",
    }
    with pytest.raises(ValueError, match="terminal receipt"):
        projector(report, _receipt(effect=OperationEffect.UPDATED))


def test_show_access_requires_exact_profile_and_whole_profile_disclosure() -> None:
    registration = _registration()
    request = OperationRequest(
        definition_id=EXPEDIENTES_SHOW_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=ExpedientesShowRequest(profile_id=_PROFILE, snapshot_id="b" * 8),
    )
    context = OperationAccessContext(
        profile_id=_PROFILE,
        destination_id=uuid4(),
        action=AccessAction.SUBMIT,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
    )

    access = resolve_expedientes_show_access(request, context)

    assert access.request.period_independent
    assert access.policy.requires_all_periods
    foreign = request.model_copy(
        update={"payload": ExpedientesShowRequest(profile_id=_OTHER_PROFILE, snapshot_id="b" * 8)}
    )
    with pytest.raises(ProfileAccessRefusedError) as error:
        resolve_expedientes_show_access(foreign, context)
    assert error.value.reason is AccessDenialCode.PROFILE_MISMATCH
