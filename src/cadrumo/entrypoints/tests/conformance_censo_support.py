"""Local Modelo 036 filing record and provenance-restricted query conformance."""

from __future__ import annotations

from datetime import date

from ...adapters.persistence.profile.m036_lifecycle import build_m036_lifecycle_ports
from ...application.modelo.m036_lifecycle import M036DeclarationCommand, list_m036_declarations, record_m036_declaration
from ...application.modelo.m036_operation import (
    M036DeclarationSnapshot,
    M036QueryDeclaration,
    M036QueryProjection,
    M036ReadProjection,
    M036ReadRequest,
    M036RecordProjection,
    M036RecordRequest,
)
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.calculations.registry.censo_modelos import CensoModeloEventKind
from .conformance_family_contract import (
    ConformanceFamily,
    ConformanceFamilyContext,
    ConformanceOutcome,
    ConformancePreparation,
    RegisteredExecutorConformanceCase,
)


def _prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
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


CENSO_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=tuple(
        RegisteredExecutorConformanceCase(
            "modelo.036." + suffix,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED if suffix == "record" else OperationEffect.NONE,
            ("modelo.036." + suffix,),
        )
        for suffix in ("query", "read", "record")
    ),
    prepare=_prepare,
)
