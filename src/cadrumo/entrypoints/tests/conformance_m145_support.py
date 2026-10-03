"""Complete local payer-communication lifecycle through registered Modelo 145 operations."""

from __future__ import annotations

from ...adapters.persistence.profile.m145_communication_records import build_m145_communication_records_ports
from ...application.modelo.m145_communication_contracts import (
    M145CommunicationCreateRequest,
    M145CommunicationExportProjection,
    M145CommunicationExportRequest,
    M145CommunicationMarkCompletedRequest,
    M145CommunicationMarkDeliveredRequest,
    M145CommunicationOperationResult,
    M145CommunicationRecordProjection,
    M145CommunicationValidateRequest,
    M145CommunicationValidationProjection,
)
from ...application.modelo.m145_communication_records import (
    M145CommunicationCreateCommand,
    M145CommunicationRecordState,
    create_m145_communication_record,
    mark_m145_communication_record_delivered_to_payer,
    read_m145_communication_record,
)
from ...core.hashing import sha256_hex
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .conformance_family_contract import (
    ConformanceFamily,
    ConformanceFamilyContext,
    ConformanceOutcome,
    ConformancePreparation,
    RegisteredExecutorConformanceCase,
)

_VALUES = {
    "perceptor.nif": "12345678Z",
    "perceptor.primer-apellido": "Garcia",
    "perceptor.segundo-apellido": "Lopez",
    "perceptor.nombre": "Ana",
    "perceptor.anio-nacimiento": "1981",
}


def _prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
    profile = str(context.profile_id)
    operation_id = context.definition.definition_id
    command = M145CommunicationCreateCommand(
        communication_year=2026, field_values=_VALUES, note="conformance local communication"
    )
    ports = build_m145_communication_records_ports(bucket_id=profile)
    record_id: str | None = None
    if operation_id == "modelo.m145.create":
        request = M145CommunicationCreateRequest.from_command(
            profile_id=context.profile_id, command=command, actor="conformance"
        )
    else:
        record = create_m145_communication_record(
            command, bucket_id=profile, actor="conformance seed", ports=ports, operation=context.operation
        )
        record_id = record.communication_record_id
        selector = record_id[:16]
        if operation_id == "modelo.m145.mark_locally_completed":
            mark_m145_communication_record_delivered_to_payer(
                record_id, bucket_id=profile, actor="conformance seed", ports=ports, operation=context.operation
            )
            request = M145CommunicationMarkCompletedRequest(
                profile_id=context.profile_id, communication_record_id=selector, actor="conformance"
            )
        elif operation_id == "modelo.m145.mark_delivered_to_payer":
            request = M145CommunicationMarkDeliveredRequest(
                profile_id=context.profile_id, communication_record_id=selector, actor="conformance"
            )
        elif operation_id == "modelo.m145.export":
            request = M145CommunicationExportRequest(
                profile_id=context.profile_id, communication_record_id=selector, actor="conformance"
            )
        elif operation_id == "modelo.m145.validate":
            request = M145CommunicationValidateRequest(profile_id=context.profile_id, communication_record_id=selector)
        else:
            raise AssertionError(operation_id)

    def verify(outcome: ConformanceOutcome) -> None:
        actual = outcome.resolve_result(M145CommunicationOperationResult)
        assert actual.profile_id == context.profile_id and actual.operation_id == operation_id
        assert actual.outcome == "completed" and actual.result is not None
        result = actual.result
        assert result.bucket_id == profile and result.communication_year == 2026
        if record_id is not None:
            assert result.communication_record_id == record_id
        persisted = read_m145_communication_record(
            result.communication_record_id, bucket_id=profile, ports=ports, operation=context.operation
        )
        assert persisted.field_values == _VALUES and persisted.note == command.note
        if isinstance(result, M145CommunicationValidationProjection):
            assert result.valid and result.issue_count == 0 and result.issues == ()
            assert persisted.state is M145CommunicationRecordState.CREATED
        elif isinstance(result, M145CommunicationExportProjection):
            payload = result.payload_text.encode(result.encoding.value)
            assert payload.startswith(b"<T145010>") and payload.endswith(b"</T145010>")
            assert b"12345678Z" in payload and b"Garcia" in payload
            assert result.payload_sha256 == sha256_hex(payload) and result.byte_length == len(payload)
            assert persisted.state is M145CommunicationRecordState.CREATED
        else:
            assert isinstance(result, M145CommunicationRecordProjection)
            expected = {
                "modelo.m145.create": M145CommunicationRecordState.CREATED,
                "modelo.m145.mark_delivered_to_payer": M145CommunicationRecordState.DELIVERED_TO_PAYER,
                "modelo.m145.mark_locally_completed": M145CommunicationRecordState.LOCALLY_COMPLETED,
            }[operation_id]
            assert persisted.state is expected and result.state is expected
            if expected is M145CommunicationRecordState.LOCALLY_COMPLETED:
                assert persisted.delivered_to_payer_at is not None and persisted.locally_completed_at is not None
                assert persisted.locally_completed_at >= persisted.delivered_to_payer_at

    return ConformancePreparation(profile_operation_subject(profile), request, verify=verify)


M145_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=tuple(
        RegisteredExecutorConformanceCase(
            "modelo.m145." + suffix,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE if suffix == "validate" else OperationEffect.UPDATED,
            ("modelo.m145." + suffix,),
        )
        for suffix in ("create", "validate", "export", "mark_delivered_to_payer", "mark_locally_completed")
    ),
    prepare=_prepare,
)
