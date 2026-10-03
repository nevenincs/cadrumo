"""Registered-executor conformance scenarios for the Modelo 145 communication family."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from ...application.modelo.m145_communication_contracts import (
    M145_COMMUNICATION_CREATE_OPERATION_DEFINITION_ID,
    M145_COMMUNICATION_EXPORT_OPERATION_DEFINITION_ID,
    M145_COMMUNICATION_MARK_COMPLETED_OPERATION_DEFINITION_ID,
    M145_COMMUNICATION_MARK_DELIVERED_OPERATION_DEFINITION_ID,
    M145_COMMUNICATION_OPERATION_IDS,
    M145_COMMUNICATION_VALIDATE_OPERATION_DEFINITION_ID,
    M145CommunicationCreateRequest,
    M145CommunicationErrorContextFact,
    M145CommunicationFieldValueProjection,
    M145CommunicationOperationId,
    M145CommunicationOperationResult,
    M145CommunicationRecordProjection,
    M145CommunicationValidationProjection,
)
from ...application.modelo.m145_communication_period import M145CommunicationPeriod
from ...application.modelo.m145_communication_records import (
    M145CommunicationRecord,
    M145CommunicationRecordState,
    derive_m145_communication_record_id,
    read_m145_communication_record,
)
from ...core.casilla_id import CasillaId
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.time.clock import now
from ...domain.buckets.event import BucketEventObjectType, BucketEventType
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.export import resolve_export_layout
from ...domain.calculations.registry.schema import RegistrySnapshot
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

# The seeding helper records every communication for this year and period.
_COMMUNICATION_YEAR = 2026
_PERIOD = M145CommunicationPeriod.COMMUNICATION
_EXPORT_REFUSAL = "REFUSED_M145_COMMUNICATION_RECORD_EXPORT"
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


def _unrenderable_export_record_id(record: M145CommunicationRecord, snapshot: RegistrySnapshot) -> str:
    """Name the first layout record (in declared order) that requires a casilla the seed never supplied.

    The canonical seed omits ``comunicacion.pagina-complementaria``, which the
    registry's DR-145 layout declares as a required one-character field. The
    fixed-width renderer refuses a required field with no value rather than
    padding it (m145_communication_records.py:905).
    """
    layout = resolve_export_layout(snapshot).layout
    for definition in sorted(layout.records, key=lambda item: item.order):
        for field in definition.fields:
            if field.required and field.casilla_id is not None and field.casilla_id not in record.field_values:
                return definition.id
    raise AssertionError("every required export field is supplied; this scenario expects one to be missing")


def _assert_store(
    case: M145CommunicationOperationConformanceCase,
    *,
    record: M145CommunicationRecord | None,
    event_type: BucketEventType | None,
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
    assert dict(event.payload) == {
        "communication_record_id": record.communication_record_id,
        "modelo": "145",
        "communication_year": str(_COMMUNICATION_YEAR),
        "period": _PERIOD.value,
        "revision_id": record.revision_id,
        "state": record.state.value,
    }


def _verify(
    case: M145CommunicationOperationConformanceCase, *, started: datetime
) -> Callable[[ConformanceOutcome], None]:
    def verify(outcome: ConformanceOutcome) -> None:
        finished = now()
        projection = outcome.resolve_result(M145CommunicationOperationResult)
        snapshot = _snapshot(case.operation)
        if case.definition_id == M145_COMMUNICATION_EXPORT_OPERATION_DEFINITION_ID:
            assert case.record_before is not None
            record_id = _unrenderable_export_record_id(case.record_before, snapshot)
            refusal = projection.refusal
            assert refusal is not None
            assert (
                projection.profile_id,
                projection.operation_id,
                projection.outcome,
                projection.effect,
                projection.result,
            ) == (case.profile_id, case.definition_id, "prewrite_refusal", OperationEffect.NONE, None)
            assert refusal.code == _EXPORT_REFUSAL
            assert refusal.message.startswith(f"Modelo 145 export record {record_id!r} could not be rendered")
            assert refusal.context == (
                M145CommunicationErrorContextFact(key="export_record_id", value=record_id),
                M145CommunicationErrorContextFact(key="reason", value="canonical_fixed_width_encoder"),
            )
            stored = _read(case, case.record_before.communication_record_id)
            _assert_store(case, record=stored, event_type=None)
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


M145_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=(
        _case(M145_COMMUNICATION_CREATE_OPERATION_DEFINITION_ID, OperationEffect.UPDATED),
        # A canonical refusal raised before the write gate opens settles as a
        # pre-write refusal with NONE (m145_communication_execution.py:332-339, :572).
        RegisteredExecutorConformanceCase(
            M145_COMMUNICATION_EXPORT_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            (M145_COMMUNICATION_EXPORT_OPERATION_DEFINITION_ID,),
            expected_refusal_ref=_EXPORT_REFUSAL,
        ),
        _case(M145_COMMUNICATION_MARK_DELIVERED_OPERATION_DEFINITION_ID, OperationEffect.UPDATED),
        _case(M145_COMMUNICATION_MARK_COMPLETED_OPERATION_DEFINITION_ID, OperationEffect.UPDATED),
        # Validation never reaches a repository write (m145_communication_execution.py:345).
        _case(M145_COMMUNICATION_VALIDATE_OPERATION_DEFINITION_ID, OperationEffect.NONE),
    ),
    prepare=_prepare,
)
