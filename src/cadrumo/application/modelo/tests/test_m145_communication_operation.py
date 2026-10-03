"""Closed-schema and full-value round trips for registered Modelo 145 commands."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Protocol, cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ....core.hashing import sha256_hex
from ....core.operations import OperationEffect, profile_operation_subject
from ....domain.buckets.event import BucketEventHistoryCatalogue
from ....domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ...operations.access_resolution import OperationAccessContext
from ...operations.capabilities import (
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ...operations.models import OperationIdentity, OperationRequest
from ...operations.operation_definition import OperationDefinition
from ...operations.owner import OperationExecutorContext
from ...operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationRegistry,
)
from ...user_profile.access_contracts import AccessAction, Availability
from .. import m145_communication_operation as m145_operation
from .._ports import FicheroBoeRecordRenderer
from ..m145_communication_operation import (
    M145_COMMUNICATION_CREATE_OPERATION_DEFINITION_ID,
    M145_COMMUNICATION_EXPORT_OPERATION_DEFINITION_ID,
    M145_COMMUNICATION_MARK_COMPLETED_OPERATION_DEFINITION_ID,
    M145_COMMUNICATION_MARK_DELIVERED_OPERATION_DEFINITION_ID,
    M145_COMMUNICATION_VALIDATE_OPERATION_DEFINITION_ID,
    M145CommunicationCreateRequest,
    M145CommunicationExecutionResult,
    M145CommunicationExecutor,
    M145CommunicationExportProjection,
    M145CommunicationExportRequest,
    M145CommunicationFieldValueProjection,
    M145CommunicationMarkCompletedRequest,
    M145CommunicationMarkDeliveredRequest,
    M145CommunicationOperationRecordNotFoundError,
    M145CommunicationRecordProjection,
    M145CommunicationValidateRequest,
    M145CommunicationValidationProjection,
    build_m145_communication_operation_definitions,
    build_m145_communication_operation_registrations,
)
from ..m145_communication_period import M145CommunicationPeriod
from ..m145_communication_records import (
    M145CommunicationCreateCommand,
    M145CommunicationExportResult,
    M145CommunicationRecord,
    M145CommunicationRecordState,
    M145CommunicationValidationIssue,
    M145CommunicationValidationIssueKind,
    M145CommunicationValidationResult,
)
from ..m145_communication_records_ports import (
    M145CommunicationRecordRepositoryPort,
    M145CommunicationRecordsPorts,
    M145CommunicationRecordsPortsFactory,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("44444444-4444-4444-8444-444444444444")
_BUCKET = str(_PROFILE)
_CREATED_AT = datetime(2026, 5, 8, 10, 15, tzinfo=UTC)
_VALUES = {
    "perceptor.nif": "12345678Z",
    "perceptor.primer-apellido": "Garcia",
    "perceptor.segundo-apellido": "Lopez",
    "perceptor.nombre": "Ana",
    "perceptor.anio-nacimiento": "1981",
}


def _canonical_record() -> M145CommunicationRecord:
    return M145CommunicationRecord(
        communication_record_id="a" * 64,
        bucket_id=_BUCKET,
        communication_year=2026,
        period_token=M145CommunicationPeriod.COMMUNICATION,
        revision_id="2012-01-31-y-siguientes",
        state=M145CommunicationRecordState.LOCALLY_COMPLETED,
        field_values=_VALUES,
        legal_refs=("rd-439-2007:art-88",),
        source_refs=("aeat-modelo-145-form",),
        created_at=_CREATED_AT,
        delivered_to_payer_at=datetime(2026, 5, 8, 10, 16, tzinfo=UTC),
        locally_completed_at=datetime(2026, 5, 8, 10, 17, tzinfo=UTC),
        note="Reviewed locally",
    )


def _factories() -> tuple[M145CommunicationRecordsPortsFactory, Callable[[], FicheroBoeRecordRenderer]]:
    def records_factory(*, bucket_id: str) -> M145CommunicationRecordsPorts:
        raise AssertionError("schema discovery must not open M145 record ports")

    def renderer_factory() -> FicheroBoeRecordRenderer:
        raise AssertionError("schema discovery must not build the M145 renderer")

    return records_factory, renderer_factory


def _definition_set() -> tuple[
    tuple[OperationDefinition, ...],
    tuple[OperationPublicDefinitionRegistrationV1, ...],
]:
    records_factory, renderer_factory = _factories()
    definitions = build_m145_communication_operation_definitions(
        records_ports_factory=records_factory,
        renderer_factory=renderer_factory,
    )
    registrations = build_m145_communication_operation_registrations(definitions)
    return definitions, registrations


def test_record_projection_round_trips_every_persisted_field() -> None:
    record = _canonical_record()

    projection = M145CommunicationRecordProjection.from_record(record)

    assert projection.to_record() == record
    assert projection.field_values == tuple(
        M145CommunicationFieldValueProjection(casilla_id=key, value=value) for key, value in sorted(_VALUES.items())
    )
    assert projection.legal_refs == record.legal_refs
    assert projection.source_refs == record.source_refs
    assert projection.created_at == record.created_at
    assert projection.delivered_to_payer_at == record.delivered_to_payer_at
    assert projection.locally_completed_at == record.locally_completed_at
    assert projection.note == record.note


def test_validation_projection_round_trips_ordered_findings_and_provenance() -> None:
    result = M145CommunicationValidationResult(
        communication_record_id="a" * 64,
        bucket_id=_BUCKET,
        communication_year=2026,
        period_token=M145CommunicationPeriod.COMMUNICATION,
        revision_id="2012-01-31-y-siguientes",
        valid=False,
        issue_count=2,
        issues=(
            M145CommunicationValidationIssue(
                kind=M145CommunicationValidationIssueKind.MISSING_REQUIRED,
                casilla_id="perceptor.nombre",
                data_type="text",
                message="required casilla 'perceptor.nombre' is missing",
                legal_refs=("rd-439-2007:art-88",),
                source_refs=("aeat-modelo-145-form",),
            ),
            M145CommunicationValidationIssue(
                kind=M145CommunicationValidationIssueKind.INVALID_VALUE,
                casilla_id="perceptor.nif",
                data_type="nif",
                message="casilla 'perceptor.nif' has an invalid value",
                legal_refs=("rd-439-2007:art-88",),
                source_refs=("aeat-modelo-145-form",),
            ),
        ),
        legal_refs=("rd-439-2007:art-88",),
        source_refs=("aeat-modelo-145-form",),
    )

    projection = M145CommunicationValidationProjection.from_result(result)

    assert projection.to_result() == result
    assert tuple(issue.message for issue in projection.issues) == tuple(issue.message for issue in result.issues)
    assert tuple(issue.legal_refs for issue in projection.issues) == tuple(issue.legal_refs for issue in result.issues)
    assert tuple(issue.source_refs for issue in projection.issues) == tuple(
        issue.source_refs for issue in result.issues
    )


def test_export_projection_keeps_payload_bytes_and_checks_receipt() -> None:
    payload = "<T145010>Comunicación local</T145010>\n".encode("iso-8859-1")
    result = M145CommunicationExportResult(
        communication_record_id="a" * 64,
        bucket_id=_BUCKET,
        communication_year=2026,
        period_token=M145CommunicationPeriod.COMMUNICATION,
        revision_id="2012-01-31-y-siguientes",
        export_layout_id="m145-comunicacion",
        encoding="iso-8859-1",
        record_count=1,
        byte_length=len(payload),
        payload_sha256=sha256_hex(payload),
        payload=payload,
        legal_refs=("rd-439-2007:art-88",),
        source_refs=("aeat-modelo-145-form",),
    )

    projection = M145CommunicationExportProjection.from_result(result)

    assert projection.to_result() == result
    assert projection.payload_text == payload.decode(result.encoding)
    assert projection.payload_sha256 == result.payload_sha256
    with pytest.raises(ValidationError, match="byte length"):
        M145CommunicationExportProjection.model_validate(
            projection.model_copy(update={"byte_length": result.byte_length + 1}).model_dump()
        )
    with pytest.raises(ValidationError, match="digest"):
        M145CommunicationExportProjection.model_validate(
            projection.model_copy(
                update={"payload_text": projection.payload_text.replace("local", "lOcal")}
            ).model_dump()
        )


class _EffectEvents:
    def __init__(self) -> None:
        self.effects: list[OperationEffect] = []

    async def phase(self, _value: str) -> None:
        return None

    async def effect(self, value: OperationEffect) -> None:
        self.effects.append(value)


class _ResultOperands:
    def __init__(self) -> None:
        self.values: list[M145CommunicationExecutionResult] = []

    async def put(self, value: M145CommunicationExecutionResult, *, written_at: datetime) -> str:
        assert written_at.tzinfo is not None
        self.values.append(value)
        return "m145-result-reference"


class _CancellationFence:
    def __init__(self) -> None:
        self.active = False

    @asynccontextmanager
    async def irreversible_section(self) -> AsyncIterator[None]:
        self.active = True
        try:
            yield
        finally:
            self.active = False


class _GuardedHistory:
    def __init__(self, fence: _CancellationFence) -> None:
        self.fence = fence
        self.entered = threading.Event()
        self.release = threading.Event()
        self.completed = False

    def append_guarded(
        self,
        appender: Callable[[BucketEventHistoryCatalogue], BucketEventHistoryCatalogue],
        *,
        attempts: int = 4,
    ) -> BucketEventHistoryCatalogue:
        assert attempts == 4
        assert self.fence.active
        self.entered.set()
        assert self.release.wait(timeout=5)
        result = appender(BucketEventHistoryCatalogue())
        self.completed = True
        return result


class _GuardedAppender(Protocol):
    def append_guarded(
        self,
        appender: Callable[[BucketEventHistoryCatalogue], BucketEventHistoryCatalogue],
        *,
        attempts: int = 4,
    ) -> BucketEventHistoryCatalogue: ...


@pytest.mark.asyncio
async def test_export_cancellation_waits_for_started_guarded_append_and_keeps_updated_effect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fence = _CancellationFence()
    history = _GuardedHistory(fence)
    events = _EffectEvents()
    operands = _ResultOperands()
    payload = "<T145010>Comunicación local</T145010>\n".encode("iso-8859-1")
    export = M145CommunicationExportResult(
        communication_record_id="a" * 64,
        bucket_id=_BUCKET,
        communication_year=2026,
        period_token=M145CommunicationPeriod.COMMUNICATION,
        revision_id="2012-01-31-y-siguientes",
        export_layout_id="m145-comunicacion",
        encoding="iso-8859-1",
        record_count=1,
        byte_length=len(payload),
        payload_sha256=sha256_hex(payload),
        payload=payload,
        legal_refs=("rd-439-2007:art-88",),
        source_refs=("aeat-modelo-145-form",),
    )
    monkeypatch.setattr(m145_operation, "require_active_bucket_id", lambda: _BUCKET)

    def invoke(
        _self: M145CommunicationExecutor,
        *,
        ports: M145CommunicationRecordsPorts,
        **_kwargs: object,
    ) -> M145CommunicationExportResult:
        cast(_GuardedAppender, ports.bucket_event_repository).append_guarded(lambda catalogue: catalogue)
        return export

    monkeypatch.setattr(M145CommunicationExecutor, "_invoke", invoke)

    def records_factory(*, bucket_id: str) -> M145CommunicationRecordsPorts:
        assert bucket_id == _BUCKET
        return M145CommunicationRecordsPorts(
            record_repository=cast(M145CommunicationRecordRepositoryPort, object()),
            bucket_event_repository=cast(BucketEventHistoryRepositoryProtocol, history),
        )

    executor = M145CommunicationExecutor(
        records_ports_factory=records_factory,
        renderer_factory=lambda: cast(FicheroBoeRecordRenderer, object()),
    )
    request = OperationRequest[BaseModel](
        definition_id=M145_COMMUNICATION_EXPORT_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(_BUCKET),
        payload=M145CommunicationExportRequest(
            profile_id=_PROFILE,
            communication_record_id="a" * 64,
            actor="M145 operator",
        ),
    )
    context = cast(
        OperationExecutorContext,
        SimpleNamespace(
            identity=OperationIdentity(
                operation_id="b" * 64,
                definition_id=M145_COMMUNICATION_EXPORT_OPERATION_DEFINITION_ID,
                subject_ref=profile_operation_subject(_BUCKET),
            ),
            authority_operation=object(),
            cancellation=fence,
            events=events,
            operands=operands,
        ),
    )

    task = asyncio.create_task(executor.execute(request, context))
    assert await asyncio.to_thread(history.entered.wait, 5)
    task.cancel()
    await asyncio.sleep(0)
    assert not task.done()
    history.release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert history.completed
    assert events.effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]
    assert len(operands.values) == 1
    assert operands.values[0].result.effect is OperationEffect.UPDATED


def test_five_registrations_are_cli_only_secure_and_require_all_periods() -> None:
    definitions, registrations = _definition_set()
    registry = OperationRegistry(definitions=definitions, public_registrations=registrations)
    assert len(registry.public_registrations) == 5
    expected_ids = {
        M145_COMMUNICATION_CREATE_OPERATION_DEFINITION_ID,
        M145_COMMUNICATION_VALIDATE_OPERATION_DEFINITION_ID,
        M145_COMMUNICATION_EXPORT_OPERATION_DEFINITION_ID,
        M145_COMMUNICATION_MARK_DELIVERED_OPERATION_DEFINITION_ID,
        M145_COMMUNICATION_MARK_COMPLETED_OPERATION_DEFINITION_ID,
    }

    assert {definition.definition_id for definition in definitions} == expected_ids
    assert {registration.contract.definition_id for registration in registrations} == expected_ids
    assert all(
        definition.permitted_frontends == frozenset({OperationFrontendProjection.CLI}) for definition in definitions
    )
    assert all(
        definition.capabilities.request_storage is OperationRequestStoragePolicy.SECURE_REFERENCE
        and definition.capabilities.sensitive_input is OperationSensitiveInputPolicy.SECURE_REFERENCE
        for definition in definitions
    )
    definitions_by_id = {definition.definition_id: definition for definition in definitions}
    assert definitions_by_id[
        M145_COMMUNICATION_VALIDATE_OPERATION_DEFINITION_ID
    ].capabilities.permitted_effects == frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN})
    assert all(
        definitions_by_id[definition_id].capabilities.permitted_effects
        == frozenset({OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.UNKNOWN})
        for definition_id in expected_ids - {M145_COMMUNICATION_VALIDATE_OPERATION_DEFINITION_ID}
    )
    assert all(definition.capabilities.replay is OperationReplayPolicy.IDEMPOTENT_SUBMIT for definition in definitions)
    assert all(
        definition.refusal_detail_codes
        and definition.refusal_detail_codes
        <= frozenset(
            {
                "REFUSED_M145_COMMUNICATION_RECORD_NOT_FOUND",
                "REFUSED_M145_COMMUNICATION_RECORD_AMBIGUOUS",
                "REFUSED_M145_COMMUNICATION_RECORD_VALIDATION",
                "REFUSED_M145_COMMUNICATION_RECORD_EXPORT",
                "REFUSED_M145_COMMUNICATION_RECORD_TRANSITION",
            },
        )
        for definition in definitions
    )

    requests: dict[str, BaseModel] = {
        M145_COMMUNICATION_CREATE_OPERATION_DEFINITION_ID: M145CommunicationCreateRequest.from_command(
            profile_id=_PROFILE,
            command=M145CommunicationCreateCommand(communication_year=2026, field_values=_VALUES),
            actor="M145 operator",
        ),
        M145_COMMUNICATION_VALIDATE_OPERATION_DEFINITION_ID: M145CommunicationValidateRequest(
            profile_id=_PROFILE,
            communication_record_id="a" * 64,
        ),
        M145_COMMUNICATION_EXPORT_OPERATION_DEFINITION_ID: M145CommunicationExportRequest(
            profile_id=_PROFILE,
            communication_record_id="a" * 64,
            actor="M145 operator",
        ),
        M145_COMMUNICATION_MARK_DELIVERED_OPERATION_DEFINITION_ID: M145CommunicationMarkDeliveredRequest(
            profile_id=_PROFILE,
            communication_record_id="a" * 64,
            actor="M145 operator",
        ),
        M145_COMMUNICATION_MARK_COMPLETED_OPERATION_DEFINITION_ID: M145CommunicationMarkCompletedRequest(
            profile_id=_PROFILE,
            communication_record_id="a" * 64,
            actor="M145 operator",
        ),
    }
    for registration in registrations:
        request = OperationRequest[BaseModel](
            definition_id=registration.contract.definition_id,
            subject_ref=profile_operation_subject(str(_PROFILE)),
            payload=requests[registration.contract.definition_id],
        )
        resolver = registration.access_resolver
        assert resolver is not None
        resolved = resolver(
            request,
            OperationAccessContext(
                profile_id=_PROFILE,
                destination_id=uuid4(),
                action=AccessAction.SUBMIT,
                frontend=OperationFrontendProjection.CLI,
                contract=registration.contract,
                published_authority=Availability.AVAILABLE,
            ),
        )
        assert resolved.request.periods == frozenset()
        assert resolved.request.period_independent is True
        assert resolved.policy.requires_all_periods is True
        assert AccessAction.SUBMIT in resolved.policy.actions
        assert (AccessAction.COMMIT in resolved.policy.actions) is (
            registration.contract.definition_id != M145_COMMUNICATION_VALIDATE_OPERATION_DEFINITION_ID
        )


def test_record_not_found_refusal_uses_the_new_correlated_refusal_error() -> None:
    error = M145CommunicationOperationRecordNotFoundError(
        "Modelo 145 communication record not found",
        context={"communication_record_id": "a" * 12},
    )

    assert error.code.code == "REFUSED_M145_COMMUNICATION_RECORD_NOT_FOUND"
    assert error.code.category.value == "REFUSED"
