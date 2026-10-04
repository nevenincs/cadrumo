"""Registered-executor conformance scenarios for the Modelo 145 communication family."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime

# The seeding helper records every communication for this year and period.
from ...adapters.persistence.profile.m145_communication_records import build_m145_communication_records_ports
from ...application.modelo.m145_communication_contracts import (
    M145_COMMUNICATION_CREATE_OPERATION_DEFINITION_ID,
    M145_COMMUNICATION_EXPORT_OPERATION_DEFINITION_ID,
    M145_COMMUNICATION_MARK_COMPLETED_OPERATION_DEFINITION_ID,
    M145_COMMUNICATION_MARK_DELIVERED_OPERATION_DEFINITION_ID,
    M145_COMMUNICATION_OPERATION_IDS,
    M145_COMMUNICATION_VALIDATE_OPERATION_DEFINITION_ID,
    M145CommunicationCreateRequest,
    M145CommunicationExportProjection,
    M145CommunicationExportRequest,
    M145CommunicationFieldValueProjection,
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
    derive_m145_communication_record_id,
    mark_m145_communication_record_delivered_to_payer,
    read_m145_communication_record,
)
from ...core.casilla_id import CasillaId
from ...core.hashing import sha256_hex
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.time.clock import now
from ...domain.buckets.event import BucketEventObjectType, BucketEventType
from ...domain.calculations.export_field_kind import CasillaFieldKind
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.export import resolve_export_layout
from ...domain.calculations.registry.fixed_width_codec import ExportEncoding
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.calculations.registry.schema_exports import ExportFieldDefinition
from .conformance_family_contract import (
    ConformanceFamily,
    ConformanceFamilyContext,
    ConformanceOutcome,
    ConformancePreparation,
    RegisteredExecutorConformanceCase,
)
from .m145_communication_operation_test_support import (
    M145CommunicationOperationConformanceCase,
    prepare_m145_communication_operation_conformance_case,
)

_COMMUNICATION_YEAR = 2026
_PERIOD = M145CommunicationPeriod.COMMUNICATION
# Modelo bucket events persist the modelo-wide payload version (revision_persistence.py:144).
_MODELO_EVENT_PAYLOAD_VERSION = 2
_TRANSITION_EVENT: dict[str, BucketEventType] = {
    M145_COMMUNICATION_CREATE_OPERATION_DEFINITION_ID: BucketEventType.MODELO_145_COMMUNICATION_CREATED,
    M145_COMMUNICATION_MARK_DELIVERED_OPERATION_DEFINITION_ID: (
        BucketEventType.MODELO_145_COMMUNICATION_DELIVERED_TO_PAYER
    ),
    M145_COMMUNICATION_MARK_COMPLETED_OPERATION_DEFINITION_ID: (
        BucketEventType.MODELO_145_COMMUNICATION_LOCALLY_COMPLETED
    ),
}


def _snapshot(operation: PinnedAuthorityOperation) -> RegistrySnapshot:
    return operation.snapshot("145", filing_year=_COMMUNICATION_YEAR, period=_PERIOD.value)


def _field_values(values: dict[CasillaId, str]) -> tuple[M145CommunicationFieldValueProjection, ...]:
    # Canonical order is by casilla id (m145_communication_contracts.py:253).
    return tuple(
        M145CommunicationFieldValueProjection(casilla_id=key, value=value)
        for key, value in sorted(values.items(), key=lambda pair: str(pair[0]))
    )


def _within(moment: datetime | None, *, started: datetime, finished: datetime) -> datetime:
    assert moment is not None
    assert started <= moment <= finished, (started, moment, finished)
    return moment


def _expected_record(
    case: M145CommunicationOperationConformanceCase,
    snapshot: RegistrySnapshot,
    actual: M145CommunicationRecordProjection,
    *,
    started: datetime,
    finished: datetime,
) -> M145CommunicationRecordProjection:
    """Build the record a lifecycle step must leave, from the seed and the registry revision.

    Only the transition instants are taken from the result, after they are
    proven to fall inside the operation's own run.
    """
    revision = snapshot.revision
    before = case.record_before
    if case.definition_id == M145_COMMUNICATION_CREATE_OPERATION_DEFINITION_ID:
        request = case.request
        assert isinstance(request, M145CommunicationCreateRequest)
        values = {item.casilla_id: item.value for item in request.field_values}
        record_id = derive_m145_communication_record_id(
            bucket_id=str(case.profile_id),
            communication_year=request.communication_year,
            period_token=request.period_token,
            revision_id=revision.id,
            field_values=values,
        )
        note = request.note
        state = M145CommunicationRecordState.CREATED
        created_at = _within(actual.created_at, started=started, finished=finished)
        delivered_at = None
        completed_at = None
    else:
        assert before is not None
        values = dict(before.field_values)
        record_id = before.communication_record_id
        note = before.note
        created_at = before.created_at
        if case.definition_id == M145_COMMUNICATION_MARK_DELIVERED_OPERATION_DEFINITION_ID:
            # Delivery stamps its own instant (m145_communication_records.py:1072).
            state = M145CommunicationRecordState.DELIVERED_TO_PAYER
            delivered_at = _within(actual.delivered_to_payer_at, started=started, finished=finished)
            completed_at = None
        else:
            # Completion keeps the seeded delivery and stamps its own (m145_communication_records.py:1128).
            state = M145CommunicationRecordState.LOCALLY_COMPLETED
            delivered_at = before.delivered_to_payer_at
            completed_at = _within(actual.locally_completed_at, started=started, finished=finished)
    return M145CommunicationRecordProjection(
        communication_record_id=record_id,
        bucket_id=str(case.profile_id),
        service_owner="cadrumo.application.modelo",
        modelo="145",
        communication_year=_COMMUNICATION_YEAR,
        period_token=_PERIOD,
        revision_id=revision.id,
        state=state,
        field_values=_field_values(values),
        # Records carry the revision's authority refs, sorted (m145_communication_records.py:1203).
        legal_refs=tuple(sorted(str(ref) for ref in revision.legal_refs)),
        source_refs=tuple(sorted(str(ref) for ref in revision.source_refs)),
        created_at=created_at,
        delivered_to_payer_at=delivered_at,
        locally_completed_at=completed_at,
        note=note,
    )


def _expected_validation(
    case: M145CommunicationOperationConformanceCase, snapshot: RegistrySnapshot
) -> M145CommunicationValidationProjection:
    """The seed supplies every required casilla with a well-formed value, so validation finds nothing."""
    assert case.record_before is not None
    revision = snapshot.revision
    return M145CommunicationValidationProjection(
        communication_record_id=case.record_before.communication_record_id,
        bucket_id=str(case.profile_id),
        service_owner="cadrumo.application.modelo",
        modelo="145",
        communication_year=_COMMUNICATION_YEAR,
        period_token=_PERIOD,
        revision_id=revision.id,
        valid=True,
        issue_count=0,
        issues=(),
        legal_refs=tuple(sorted(str(ref) for ref in revision.legal_refs)),
        source_refs=tuple(sorted(str(ref) for ref in revision.source_refs)),
    )


def _expected_wire_text(field: ExportFieldDefinition, values: Mapping[CasillaId, str]) -> str:
    """Write one seed slot from the DR-145 conventions, not through the export codec.

    Text is left-justified and space-filled, numbers are right-justified and
    zero-filled, and an absent slot is spaces or zeros by the same rule. The
    seed leaves ``comunicacion.pagina-complementaria`` absent, which DR-145
    row 2 declares as blank for the principal page.
    """
    assert field.length is not None
    if field.kind is CasillaFieldKind.LITERAL:
        assert field.literal is not None and len(field.literal) == field.length
        return field.literal
    if field.kind is CasillaFieldKind.FILLER:
        return " " * field.length
    assert field.kind is CasillaFieldKind.CASILLA and field.casilla_id is not None, field.id
    value = values.get(field.casilla_id)
    if field.data_type == "text":
        return (value or "").ljust(field.length)
    assert field.data_type in {"integer", "money"}, (field.id, field.data_type)
    assert value is None or value.isdecimal(), (field.id, value)
    return (value or "").rjust(field.length, "0")


def _expected_export(
    case: M145CommunicationOperationConformanceCase, snapshot: RegistrySnapshot
) -> M145CommunicationExportProjection:
    """Build the export the seed must produce from the registry layout and the seed values alone."""
    record = case.record_before
    assert record is not None
    layout = resolve_export_layout(snapshot).layout
    (definition,) = layout.records
    # DR-145 is one 610-character record with no terminator (dr145v20.pdf rows 1-59).
    assert definition.line_ending == "none"
    fields = sorted(definition.fields, key=lambda item: item.offset or 0)
    payload_text = "".join(_expected_wire_text(field, record.field_values) for field in fields)
    assert len(payload_text) == 610
    assert payload_text.startswith("<T145010> 12345678ZGarcia")
    assert payload_text.endswith("</T145010>")
    payload = payload_text.encode(definition.encoding)
    return M145CommunicationExportProjection(
        communication_record_id=record.communication_record_id,
        bucket_id=str(case.profile_id),
        service_owner="cadrumo.application.modelo",
        modelo="145",
        communication_year=_COMMUNICATION_YEAR,
        period_token=_PERIOD,
        revision_id=snapshot.revision.id,
        export_layout_id=layout.id,
        encoding=ExportEncoding(definition.encoding),
        record_count=1,
        byte_length=len(payload),
        payload_sha256=sha256_hex(payload),
        payload_text=payload_text,
        legal_refs=tuple(sorted(str(ref) for ref in layout.legal_refs)),
        source_refs=tuple(sorted(str(ref) for ref in layout.source_refs)),
    )


def _assert_store(
    case: M145CommunicationOperationConformanceCase,
    *,
    record: M145CommunicationRecord | None,
    event_type: BucketEventType | None,
    export: M145CommunicationExportProjection | None = None,
) -> None:
    """Prove the record now stored and exactly the audit events the command appended."""
    history = case.ports.bucket_event_repository.load()
    before = case.history_before.events
    assert all(history.events.get(event_id) == event for event_id, event in before.items())
    added = tuple(event for event_id, event in history.events.items() if event_id not in before)
    if event_type is None:
        assert added == ()
        assert record == case.record_before
        return
    assert record is not None
    assert len(added) == 1
    event = added[0]
    # One event co-committed with the record write (m145_communication_records.py:487-501).
    assert event.bucket_id == str(case.profile_id)
    assert event.event_type is event_type
    assert event.object_type is BucketEventObjectType.COMMUNICATION_RECORD
    assert event.object_id == record.communication_record_id
    assert event.actor == case.request.model_dump()["actor"]
    assert event.payload_version == _MODELO_EVENT_PAYLOAD_VERSION
    expected_payload = {
        "communication_record_id": record.communication_record_id,
        "modelo": "145",
        "communication_year": str(_COMMUNICATION_YEAR),
        "period": _PERIOD.value,
        "revision_id": record.revision_id,
        "state": record.state.value,
    }
    if export is not None:
        # The export receipt joins the event payload (m145_communication_records.py:996-1008, :499-500).
        expected_payload |= {
            "export_layout_id": export.export_layout_id,
            "payload_sha256": export.payload_sha256,
            "byte_length": str(export.byte_length),
            "record_count": str(export.record_count),
        }
    assert dict(event.payload) == expected_payload


def _verify(
    case: M145CommunicationOperationConformanceCase, *, started: datetime
) -> Callable[[ConformanceOutcome], None]:
    def verify(outcome: ConformanceOutcome) -> None:
        finished = now()
        projection = outcome.resolve_result(M145CommunicationOperationResult)
        snapshot = _snapshot(case.operation)
        if case.definition_id == M145_COMMUNICATION_EXPORT_OPERATION_DEFINITION_ID:
            assert case.record_before is not None
            expected_export = _expected_export(case, snapshot)
            assert projection == M145CommunicationOperationResult(
                profile_id=case.profile_id,
                operation_id=case.definition_id,
                outcome="completed",
                effect=OperationEffect.UPDATED,
                result=expected_export,
            )
            # Export derives a receipt; the record itself is left exactly as seeded.
            stored = _read(case, case.record_before.communication_record_id)
            assert stored == case.record_before
            _assert_store(
                case,
                record=stored,
                event_type=BucketEventType.MODELO_145_COMMUNICATION_EXPORTED,
                export=expected_export,
            )
            return
        if case.definition_id == M145_COMMUNICATION_VALIDATE_OPERATION_DEFINITION_ID:
            assert case.record_before is not None
            assert projection == M145CommunicationOperationResult(
                profile_id=case.profile_id,
                operation_id=case.definition_id,
                outcome="completed",
                effect=OperationEffect.NONE,
                result=_expected_validation(case, snapshot),
            )
            _assert_store(case, record=_read(case, case.record_before.communication_record_id), event_type=None)
            return
        actual = projection.result
        assert isinstance(actual, M145CommunicationRecordProjection)
        expected_record = _expected_record(case, snapshot, actual, started=started, finished=finished)
        assert projection == M145CommunicationOperationResult(
            profile_id=case.profile_id,
            operation_id=case.definition_id,
            outcome="completed",
            effect=OperationEffect.UPDATED,
            result=expected_record,
        )
        stored = _read(case, expected_record.communication_record_id)
        assert M145CommunicationRecordProjection.from_record(stored) == expected_record
        _assert_store(case, record=stored, event_type=_TRANSITION_EVENT[case.definition_id])

    return verify


def _read(case: M145CommunicationOperationConformanceCase, record_id: str) -> M145CommunicationRecord:
    return read_m145_communication_record(
        record_id, bucket_id=str(case.profile_id), ports=case.ports, operation=case.operation
    )


def _prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
    definition_id = context.definition.definition_id
    operation_id: M145CommunicationOperationId | None = next(
        (candidate for candidate in M145_COMMUNICATION_OPERATION_IDS if candidate == definition_id), None
    )
    if operation_id is None:
        raise AssertionError(f"no Modelo 145 conformance scenario for {definition_id}")
    started = now()
    # Every command but create first creates (and, for completion, delivers)
    # the record through the canonical service and its encrypted ports.
    case = prepare_m145_communication_operation_conformance_case(
        operation_id, context.profile_id, operation=context.operation
    )
    return ConformancePreparation(
        subject_ref=profile_operation_subject(str(context.profile_id)),
        request=case.request,
        verify=_verify(case, started=started),
    )


def _case(definition_id: str, effect: OperationEffect) -> RegisteredExecutorConformanceCase:
    # One phase named after the command (m145_communication_execution.py:226); a
    # command that writes publishes UPDATED once its fenced save returns (:370).
    return RegisteredExecutorConformanceCase(
        definition_id, OperationTerminalCondition.SUCCEEDED, effect, (definition_id,)
    )


M145_WIRE_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=(
        _case(M145_COMMUNICATION_CREATE_OPERATION_DEFINITION_ID, OperationEffect.UPDATED),
        # Export appends its receipt event, so it settles as an update.
        _case(M145_COMMUNICATION_EXPORT_OPERATION_DEFINITION_ID, OperationEffect.UPDATED),
        _case(M145_COMMUNICATION_MARK_DELIVERED_OPERATION_DEFINITION_ID, OperationEffect.UPDATED),
        _case(M145_COMMUNICATION_MARK_COMPLETED_OPERATION_DEFINITION_ID, OperationEffect.UPDATED),
        # Validation never reaches a repository write (m145_communication_execution.py:345).
        _case(M145_COMMUNICATION_VALIDATE_OPERATION_DEFINITION_ID, OperationEffect.NONE),
    ),
    prepare=_prepare,
)


_RETAINED_M145_VALUES = {
    "perceptor.nif": "12345678Z",
    "perceptor.primer-apellido": "Garcia",
    "perceptor.segundo-apellido": "Lopez",
    "perceptor.nombre": "Ana",
    "perceptor.anio-nacimiento": "1981",
}


def _retained_m145_prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
    profile = str(context.profile_id)
    operation_id = context.definition.definition_id
    command = M145CommunicationCreateCommand(
        communication_year=2026, field_values=_RETAINED_M145_VALUES, note="conformance local communication"
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
        assert persisted.field_values == _RETAINED_M145_VALUES and persisted.note == command.note
        if isinstance(result, M145CommunicationValidationProjection):
            assert result.valid and result.issue_count == 0 and (result.issues == ())
            assert persisted.state is M145CommunicationRecordState.CREATED
        elif isinstance(result, M145CommunicationExportProjection):
            payload = result.payload_text.encode(result.encoding.value)
            assert payload.startswith(b"<T145010>") and payload.endswith(b"</T145010>")
            assert payload[9:10] == b" "
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
    prepare=_retained_m145_prepare,
)
