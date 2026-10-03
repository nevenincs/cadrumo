"""Encrypted canonical fixtures for registered Modelo 145 operation acceptance."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Literal, override
from uuid import UUID

from pydantic import BaseModel

from ...adapters.outbound.aeat.export.registry_record_renderer import RegistryFixedWidthRecordRenderer
from ...adapters.persistence.profile.m145_communication_records import build_m145_communication_records_ports
from ...application.modelo.m145_communication_operation import (
    M145_COMMUNICATION_CREATE_OPERATION_DEFINITION_ID,
    M145_COMMUNICATION_EXPORT_OPERATION_DEFINITION_ID,
    M145_COMMUNICATION_MARK_COMPLETED_OPERATION_DEFINITION_ID,
    M145_COMMUNICATION_MARK_DELIVERED_OPERATION_DEFINITION_ID,
    M145_COMMUNICATION_VALIDATE_OPERATION_DEFINITION_ID,
    M145CommunicationCreateRequest,
    M145CommunicationExportProjection,
    M145CommunicationExportRequest,
    M145CommunicationMarkCompletedRequest,
    M145CommunicationMarkDeliveredRequest,
    M145CommunicationOperationId,
    M145CommunicationOperationResult,
    M145CommunicationRecordProjection,
    M145CommunicationValidateRequest,
    M145CommunicationValidationProjection,
)
from ...application.modelo.m145_communication_period import M145CommunicationPeriod
from ...application.modelo.m145_communication_records import (
    M145CommunicationCreateCommand,
    M145CommunicationRecord,
    M145CommunicationRecordState,
    create_m145_communication_record,
    export_m145_communication_record,
    mark_m145_communication_record_delivered_to_payer,
    read_m145_communication_record,
    validate_m145_communication_record,
)
from ...application.modelo.m145_communication_records_ports import M145CommunicationRecordsPorts
from ...core.operations import OperationEffect
from ...core.secure_object_write import SecureObjectWrite
from ...domain.buckets.event import BucketEventHistoryCatalogue, BucketEventObjectType, BucketEventType
from ...domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ...domain.calculations.registry.authority import PinnedAuthorityOperation

_CREATED_AT = datetime(2026, 5, 8, 10, 15, tzinfo=UTC)
_ACTOR = "registered-m145-conformance"
_FIELD_VALUES = {
    "perceptor.nif": "12345678Z",
    "perceptor.primer-apellido": "Garcia",
    "perceptor.segundo-apellido": "Lopez",
    "perceptor.nombre": "Ana",
    "perceptor.anio-nacimiento": "1981",
}

_OPERATION_ACTION: dict[
    M145CommunicationOperationId, Literal["create", "validate", "export", "delivered", "completed"]
] = {
    M145_COMMUNICATION_CREATE_OPERATION_DEFINITION_ID: "create",
    M145_COMMUNICATION_VALIDATE_OPERATION_DEFINITION_ID: "validate",
    M145_COMMUNICATION_EXPORT_OPERATION_DEFINITION_ID: "export",
    M145_COMMUNICATION_MARK_DELIVERED_OPERATION_DEFINITION_ID: "delivered",
    M145_COMMUNICATION_MARK_COMPLETED_OPERATION_DEFINITION_ID: "completed",
}
_MUTATION_EVENT: dict[M145CommunicationOperationId, BucketEventType | None] = {
    M145_COMMUNICATION_CREATE_OPERATION_DEFINITION_ID: BucketEventType.MODELO_145_COMMUNICATION_CREATED,
    M145_COMMUNICATION_VALIDATE_OPERATION_DEFINITION_ID: None,
    M145_COMMUNICATION_EXPORT_OPERATION_DEFINITION_ID: BucketEventType.MODELO_145_COMMUNICATION_EXPORTED,
    M145_COMMUNICATION_MARK_DELIVERED_OPERATION_DEFINITION_ID: BucketEventType.MODELO_145_COMMUNICATION_DELIVERED_TO_PAYER,
    M145_COMMUNICATION_MARK_COMPLETED_OPERATION_DEFINITION_ID: BucketEventType.MODELO_145_COMMUNICATION_LOCALLY_COMPLETED,
}
_EXPECTED_STATE: dict[M145CommunicationOperationId, M145CommunicationRecordState] = {
    M145_COMMUNICATION_CREATE_OPERATION_DEFINITION_ID: M145CommunicationRecordState.CREATED,
    M145_COMMUNICATION_MARK_DELIVERED_OPERATION_DEFINITION_ID: M145CommunicationRecordState.DELIVERED_TO_PAYER,
    M145_COMMUNICATION_MARK_COMPLETED_OPERATION_DEFINITION_ID: M145CommunicationRecordState.LOCALLY_COMPLETED,
}


@dataclass(frozen=True, slots=True)
class M145CommunicationOperationConformanceCase:
    """Typed command and exact encrypted state before one registered operation."""

    definition_id: M145CommunicationOperationId
    action: Literal["create", "validate", "export", "delivered", "completed"]
    request: BaseModel
    expected_effect: OperationEffect
    profile_id: UUID
    record_id: str | None
    record_before: M145CommunicationRecord | None
    history_before: BucketEventHistoryCatalogue
    ports: M145CommunicationRecordsPorts
    operation: PinnedAuthorityOperation


class _NoWriteEventHistory(BucketEventHistoryRepositoryProtocol):
    """Capture a canonical export receipt proposal without persisting a second one."""

    def __init__(self, repository: BucketEventHistoryRepositoryProtocol) -> None:
        self._repository = repository
        self.proposed: BucketEventHistoryCatalogue | None = None

    @override
    def exists(self) -> bool:
        return self._repository.exists()

    @override
    def load(self) -> BucketEventHistoryCatalogue:
        return self._repository.load()

    @override
    def save(self, catalogue: BucketEventHistoryCatalogue) -> None:
        self.proposed = catalogue

    @override
    def to_secure_object_write(
        self,
        catalogue: BucketEventHistoryCatalogue,
        *,
        expected_revision_id: str | None = None,
    ) -> SecureObjectWrite:
        return self._repository.to_secure_object_write(catalogue, expected_revision_id=expected_revision_id)


def prepare_m145_communication_operation_conformance_case(
    definition_id: M145CommunicationOperationId,
    profile_id: UUID,
    *,
    operation: PinnedAuthorityOperation,
) -> M145CommunicationOperationConformanceCase:
    """Prepare one existing M145 command against its canonical encrypted record ports."""
    try:
        action = _OPERATION_ACTION[definition_id]
    except KeyError:
        raise ValueError(f"unsupported M145 communication definition: {definition_id}") from None

    bucket_id = str(profile_id)
    ports = build_m145_communication_records_ports(bucket_id=bucket_id)
    record_before: M145CommunicationRecord | None = None
    record_id: str | None = None
    if action != "create":
        record = create_m145_communication_record(
            M145CommunicationCreateCommand(
                communication_year=2026,
                period_token=M145CommunicationPeriod.COMMUNICATION,
                field_values=_FIELD_VALUES,
                note="Registered M145 operation conformance row",
            ),
            bucket_id=bucket_id,
            ports=ports,
            operation=operation,
            actor="conformance-seed",
        )
        record_id = record.communication_record_id
        if action == "completed":
            record = mark_m145_communication_record_delivered_to_payer(
                record_id,
                bucket_id=bucket_id,
                ports=ports,
                operation=operation,
                actor="conformance-seed",
            )
        record_before = read_m145_communication_record(
            record_id,
            bucket_id=bucket_id,
            ports=ports,
            operation=operation,
        )
        expected_before = (
            M145CommunicationRecordState.DELIVERED_TO_PAYER
            if action == "completed"
            else M145CommunicationRecordState.CREATED
        )
        if record_before.state is not expected_before:
            raise RuntimeError("M145 conformance seed did not reach the expected starting state")

    history_before = ports.bucket_event_repository.load()
    if action == "create":
        request: BaseModel = M145CommunicationCreateRequest.from_command(
            profile_id=profile_id,
            command=M145CommunicationCreateCommand(
                communication_year=2026,
                period_token=M145CommunicationPeriod.COMMUNICATION,
                field_values=_FIELD_VALUES,
                note="Registered M145 operation conformance row",
            ),
            actor=_ACTOR,
        )
        expected_effect = OperationEffect.UPDATED
    elif action == "validate":
        assert record_id is not None
        request = M145CommunicationValidateRequest(profile_id=profile_id, communication_record_id=record_id)
        expected_effect = OperationEffect.NONE
    elif action == "export":
        assert record_id is not None
        request = M145CommunicationExportRequest(
            profile_id=profile_id,
            communication_record_id=record_id,
            actor=_ACTOR,
        )
        expected_effect = OperationEffect.UPDATED
    elif action == "delivered":
        assert record_id is not None
        request = M145CommunicationMarkDeliveredRequest(
            profile_id=profile_id,
            communication_record_id=record_id,
            actor=_ACTOR,
        )
        expected_effect = OperationEffect.UPDATED
    else:
        assert record_id is not None
        request = M145CommunicationMarkCompletedRequest(
            profile_id=profile_id,
            communication_record_id=record_id,
            actor=_ACTOR,
        )
        expected_effect = OperationEffect.UPDATED

    return M145CommunicationOperationConformanceCase(
        definition_id=definition_id,
        action=action,
        request=request,
        expected_effect=expected_effect,
        profile_id=profile_id,
        record_id=record_id,
        record_before=record_before,
        history_before=history_before,
        ports=ports,
        operation=operation,
    )


def assert_m145_communication_operation_conformance_result(
    case: M145CommunicationOperationConformanceCase,
    projection: BaseModel,
) -> None:
    """Compare typed worker result with complete canonical encrypted state and event history."""
    assert isinstance(projection, M145CommunicationOperationResult)
    assert projection.profile_id == case.profile_id
    assert projection.operation_id == case.definition_id
    assert projection.outcome == "completed"
    assert projection.effect is case.expected_effect
    bucket_id = str(case.profile_id)
    history_after = case.ports.bucket_event_repository.load()
    assert all(history_after.events.get(event_id) == event for event_id, event in case.history_before.events.items())
    added_events = tuple(
        event for event_id, event in history_after.events.items() if event_id not in case.history_before.events
    )
    event_type = _MUTATION_EVENT[case.definition_id]
    assert len(added_events) == (0 if event_type is None else 1)
    canonical_record: M145CommunicationRecord | None = None

    if case.action == "create":
        result = projection.result
        assert isinstance(result, M145CommunicationRecordProjection)
        record = read_m145_communication_record(
            result.communication_record_id,
            bucket_id=bucket_id,
            ports=case.ports,
            operation=case.operation,
        )
        assert record.state is _EXPECTED_STATE[case.definition_id]
        assert result == M145CommunicationRecordProjection.from_record(record)
        canonical_record = record
    elif case.action == "validate":
        assert case.record_id is not None
        assert case.record_before is not None
        result = projection.result
        assert isinstance(result, M145CommunicationValidationProjection)
        current = read_m145_communication_record(
            case.record_id,
            bucket_id=bucket_id,
            ports=case.ports,
            operation=case.operation,
        )
        assert current == case.record_before
        expected = validate_m145_communication_record(
            case.record_id,
            bucket_id=bucket_id,
            ports=case.ports,
            operation=case.operation,
        )
        assert result == M145CommunicationValidationProjection.from_result(expected)
    elif case.action == "export":
        assert case.record_id is not None
        result = projection.result
        assert isinstance(result, M145CommunicationExportProjection)
        history_port = _NoWriteEventHistory(case.ports.bucket_event_repository)
        preview_ports = replace(case.ports, bucket_event_repository=history_port)
        expected = export_m145_communication_record(
            case.record_id,
            bucket_id=bucket_id,
            renderer=RegistryFixedWidthRecordRenderer(),
            ports=preview_ports,
            operation=case.operation,
            actor=_ACTOR,
        )
        assert result == M145CommunicationExportProjection.from_result(expected)
        assert history_port.proposed is not None
        assert history_port.proposed != case.history_before
        canonical_record = case.record_before
    else:
        assert case.record_id is not None
        result = projection.result
        assert isinstance(result, M145CommunicationRecordProjection)
        record = read_m145_communication_record(
            case.record_id,
            bucket_id=bucket_id,
            ports=case.ports,
            operation=case.operation,
        )
        assert record.state is _EXPECTED_STATE[case.definition_id]
        assert result == M145CommunicationRecordProjection.from_record(record)
        canonical_record = record

    if event_type is not None:
        assert canonical_record is not None
        event = added_events[0]
        assert event.bucket_id == bucket_id
        assert event.event_type is event_type
        assert event.object_type is BucketEventObjectType.COMMUNICATION_RECORD
        assert event.object_id == canonical_record.communication_record_id
        assert event.actor == _ACTOR
        assert event.payload_version == 1
        expected_payload = {
            "communication_record_id": canonical_record.communication_record_id,
            "modelo": canonical_record.modelo,
            "communication_year": str(canonical_record.communication_year),
            "period": canonical_record.period_token.value,
            "revision_id": canonical_record.revision_id,
            "state": canonical_record.state.value,
        }
        if case.action == "export":
            assert isinstance(projection.result, M145CommunicationExportProjection)
            expected_payload.update(
                {
                    "export_layout_id": projection.result.export_layout_id,
                    "payload_sha256": projection.result.payload_sha256,
                    "byte_length": str(projection.result.byte_length),
                    "record_count": str(projection.result.record_count),
                },
            )
        assert dict(event.payload) == expected_payload


__all__ = [
    "M145CommunicationOperationConformanceCase",
    "assert_m145_communication_operation_conformance_result",
    "prepare_m145_communication_operation_conformance_case",
]
