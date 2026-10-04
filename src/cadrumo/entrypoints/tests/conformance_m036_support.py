"""Registered-executor conformance scenarios for the local Modelo 036 recording family."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from uuid import UUID

from ...adapters.persistence.profile.m036_lifecycle import build_m036_lifecycle_ports
from ...application.modelo.m036_lifecycle import (
    M036DeclarationCommand,
    M036DeclarationResult,
    derive_m036_declaration_id,
    list_m036_declarations,
    record_m036_declaration,
)
from ...application.modelo.m036_operation import (
    M036_QUERY_OPERATION_DEFINITION_ID,
    M036_READ_OPERATION_DEFINITION_ID,
    M036_RECORD_OPERATION_DEFINITION_ID,
    M036DeclarationSnapshot,
    M036QueryDeclaration,
    M036QueryProjection,
    M036ReadProjection,
    M036ReadRequest,
    M036RecordProjection,
    M036RecordRequest,
)
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.time.clock import now
from ...domain.buckets.event import BucketEventObjectType, BucketEventType
from ...domain.calculations.registry.censo_modelos import CensoModeloEventKind
from .conformance_family_contract import (
    ConformanceFamily,
    ConformanceFamilyContext,
    ConformanceOutcome,
    ConformancePreparation,
    RegisteredExecutorConformanceCase,
)

_ALTA_ON = date(2026, 1, 12)
_ALTA_JUSTIFICANTE = "CONFORMANCE-036-ALTA-0001"
_ALTA_NOTE = "Conformance alta filed at the sede"
_MODIFICACION_ON = date(2026, 3, 2)
_MODIFICACION_NOTE = "Conformance activity change filed in person"


def _seed(
    profile_id: UUID, *, event_kind: CensoModeloEventKind, declared_on: date, **optional: str
) -> M036DeclarationResult:
    """Record one prior external filing through the canonical lifecycle service and its encrypted ports."""
    return record_m036_declaration(
        M036DeclarationCommand(
            profile_id=str(profile_id),
            event_kind=event_kind,
            declared_on=declared_on,
            sede_justificante=optional.get("sede_justificante"),
            note=optional.get("note"),
        ),
        bucket_id=str(profile_id),
        ports=build_m036_lifecycle_ports(bucket_id=str(profile_id)),
    )


def _seed_alta(profile_id: UUID) -> M036DeclarationResult:
    return _seed(
        profile_id,
        event_kind=CensoModeloEventKind.ALTA,
        declared_on=_ALTA_ON,
        sede_justificante=_ALTA_JUSTIFICANTE,
        note=_ALTA_NOTE,
    )


def _query_row(profile_id: UUID, row: M036DeclarationResult) -> M036QueryDeclaration:
    return M036QueryDeclaration(
        profile_id=profile_id,
        declaration_id=row.declaration_id,
        event_kind=row.event_kind,
        declared_on=row.declared_on,
        recorded_at=row.recorded_at,
        justificante_present=row.sede_justificante is not None,
        note_present=row.note is not None,
    )


def _prepare_read(context: ConformanceFamilyContext) -> ConformancePreparation:
    alta = _seed_alta(context.profile_id)
    return ConformancePreparation(
        subject_ref=profile_operation_subject(str(context.profile_id)),
        request=M036ReadRequest(profile_id=context.profile_id, kind="view", declaration_id=alta.declaration_id[:12]),
        expected_result=M036ReadProjection(
            profile_id=context.profile_id,
            kind="view",
            declarations=(M036DeclarationSnapshot.model_validate(alta.model_dump()),),
        ),
    )


def _prepare_query(context: ConformanceFamilyContext) -> ConformancePreparation:
    profile_id = context.profile_id
    alta = _seed_alta(profile_id)
    modificacion = _seed(profile_id, event_kind=CensoModeloEventKind.MODIFICACION, declared_on=_MODIFICACION_ON)
    expected_rows = {row.declaration_id: _query_row(profile_id, row) for row in (alta, modificacion)}

    def verify(outcome: ConformanceOutcome) -> None:
        projection = outcome.resolve_result(M036QueryProjection)
        assert projection.profile_id == profile_id
        assert projection.kind == "list"
        assert len(projection.declarations) == len(expected_rows)
        assert {row.declaration_id: row for row in projection.declarations} == expected_rows

    return ConformancePreparation(
        subject_ref=profile_operation_subject(str(profile_id)),
        request=M036ReadRequest(profile_id=profile_id, kind="list"),
        verify=verify,
    )


def _prepare_record(context: ConformanceFamilyContext) -> ConformancePreparation:
    profile_id = context.profile_id
    bucket_id = str(profile_id)
    alta = _seed_alta(profile_id)
    ports = build_m036_lifecycle_ports(bucket_id=bucket_id)
    events_before = ports.bucket_event_repository.load().events
    started = now()
    request = M036RecordRequest(
        profile_id=profile_id,
        event_kind=CensoModeloEventKind.MODIFICACION,
        declared_on=_MODIFICACION_ON,
        note=_MODIFICACION_NOTE,
    )
    declaration_id = derive_m036_declaration_id(
        profile_id=bucket_id,
        event_kind=CensoModeloEventKind.MODIFICACION,
        declared_on=_MODIFICACION_ON,
        sede_justificante=None,
    )

    def verify(outcome: ConformanceOutcome) -> None:
        finished = now()
        projection = outcome.resolve_result(M036RecordProjection)
        recorded_at = projection.declaration.recorded_at
        assert started <= recorded_at <= finished, (started, recorded_at, finished)
        expected = M036DeclarationResult(
            declaration_id=declaration_id,
            bucket_id=bucket_id,
            profile_id=bucket_id,
            event_kind=CensoModeloEventKind.MODIFICACION,
            declared_on=_MODIFICACION_ON,
            sede_justificante=None,
            note=_MODIFICACION_NOTE,
            recorded_at=recorded_at,
        )
        assert projection == M036RecordProjection(
            profile_id=profile_id, declaration=M036DeclarationSnapshot.model_validate(expected.model_dump())
        )
        after = build_m036_lifecycle_ports(bucket_id=bucket_id)
        stored = {row.declaration_id: row for row in after.declaration_repository.list_snapshots()}
        assert stored == {alta.declaration_id: alta, declaration_id: expected}
        events = after.bucket_event_repository.load().events
        assert all((events.get(event_id) == event for event_id, event in events_before.items()))
        added = tuple((event for event_id, event in events.items() if event_id not in events_before))
        assert len(added) == 1
        event = added[0]
        assert event.event_type is BucketEventType.CENSO_DECLARATION_MODIFICACION
        assert event.object_type is BucketEventObjectType.PROFILE
        assert event.object_id == declaration_id
        assert event.actor == "operator"
        assert event.payload_version == 1
        assert dict(event.payload) == {
            "profile_id": bucket_id,
            "declared_on": _MODIFICACION_ON.isoformat(),
            "note": _MODIFICACION_NOTE,
        }

    return ConformancePreparation(subject_ref=profile_operation_subject(bucket_id), request=request, verify=verify)


_PREPARERS: dict[str, Callable[[ConformanceFamilyContext], ConformancePreparation]] = {
    M036_READ_OPERATION_DEFINITION_ID: _prepare_read,
    M036_QUERY_OPERATION_DEFINITION_ID: _prepare_query,
    M036_RECORD_OPERATION_DEFINITION_ID: _prepare_record,
}


def _prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
    preparer = _PREPARERS.get(context.definition.definition_id)
    if preparer is None:
        raise AssertionError(f"no Modelo 036 conformance scenario for {context.definition.definition_id}")
    return preparer(context)


M036_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=(
        RegisteredExecutorConformanceCase(
            M036_QUERY_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            (M036_QUERY_OPERATION_DEFINITION_ID,),
        ),
        RegisteredExecutorConformanceCase(
            M036_READ_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            (M036_READ_OPERATION_DEFINITION_ID,),
        ),
        RegisteredExecutorConformanceCase(
            M036_RECORD_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            (M036_RECORD_OPERATION_DEFINITION_ID,),
        ),
    ),
    prepare=_prepare,
)


def _retained_m036_prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
    profile = str(context.profile_id)
    ports = build_m036_lifecycle_ports(bucket_id=profile)
    kind = context.definition.definition_id
    declared_on = date(2026, 4, 1)
    if kind == "modelo.036.record":
        request = M036RecordRequest(
            profile_id=context.profile_id,
            event_kind=CensoModeloEventKind.ALTA,
            declared_on=declared_on,
            sede_justificante="synthetic-receipt",
            note="synthetic local declaration",
        )

        def verify(outcome: ConformanceOutcome) -> None:
            result = outcome.resolve_result(M036RecordProjection)
            persisted = list_m036_declarations(bucket_id=profile, ports=ports)
            assert len(persisted) == 1 and persisted[0] == result.declaration.to_declaration()
            assert persisted[0].event_kind is CensoModeloEventKind.ALTA
            assert persisted[0].declared_on == declared_on and persisted[0].sede_justificante == "synthetic-receipt"
            assert persisted[0].note == "synthetic local declaration"

        return ConformancePreparation(profile_operation_subject(profile), request, verify=verify)
    seeded = record_m036_declaration(
        M036DeclarationCommand(
            profile_id=profile,
            event_kind=CensoModeloEventKind.ALTA,
            declared_on=declared_on,
            sede_justificante="synthetic-receipt",
            note="private conformance note",
        ),
        bucket_id=profile,
        ports=ports,
    )
    request = M036ReadRequest(profile_id=context.profile_id, kind="view", declaration_id=seeded.declaration_id[:16])
    if kind == "modelo.036.read":
        expected = M036ReadProjection(
            profile_id=context.profile_id,
            kind="view",
            declarations=(M036DeclarationSnapshot.model_validate(seeded.model_dump()),),
        )
    elif kind == "modelo.036.query":
        expected = M036QueryProjection(
            profile_id=context.profile_id,
            kind="view",
            declarations=(
                M036QueryDeclaration(
                    profile_id=context.profile_id,
                    declaration_id=seeded.declaration_id,
                    event_kind=CensoModeloEventKind.ALTA,
                    declared_on=declared_on,
                    recorded_at=seeded.recorded_at,
                    justificante_present=True,
                    note_present=True,
                ),
            ),
        )
    else:
        raise AssertionError(kind)
    return ConformancePreparation(profile_operation_subject(profile), request, expected_result=expected)


M036_MATERIAL_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=tuple(
        RegisteredExecutorConformanceCase(
            "modelo.036." + suffix,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED if suffix == "record" else OperationEffect.NONE,
            ("modelo.036." + suffix,),
        )
        for suffix in ("query", "read", "record")
    ),
    prepare=_retained_m036_prepare,
)
