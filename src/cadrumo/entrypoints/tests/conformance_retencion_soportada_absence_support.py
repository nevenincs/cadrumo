"""Suffered-withholding absence attestations through the real supervisor matrix."""

from __future__ import annotations

from datetime import UTC, datetime

from ...application.aggregation.retencion_soportada_absence_repository import attest_retencion_soportada_absence
from ...application.retencion_soportada_absence.contracts import (
    RETENCION_SOPORTADA_ABSENCE_ATTEST_OPERATION_DEFINITION_ID,
    RETENCION_SOPORTADA_ABSENCE_LIST_OPERATION_DEFINITION_ID,
    RETENCION_SOPORTADA_ABSENCE_WITHDRAW_OPERATION_DEFINITION_ID,
)
from ...application.retencion_soportada_absence.requests import (
    RetencionSoportadaAbsenceAttestRequest,
    RetencionSoportadaAbsenceListRequest,
    RetencionSoportadaAbsenceWithdrawRequest,
)
from ...application.retencion_soportada_absence.results import (
    RetencionSoportadaAbsenceListProjection,
    RetencionSoportadaAbsenceMutationProjection,
)
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.retencion_soportada import RetencionSoportadaClase
from ...core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from ...domain.renta.retencion_soportada_absence import RetencionSoportadaAbsence, RetencionSoportadaAbsenceState
from ..retencion_soportada_absence_composition import build_retencion_soportada_absence_ports
from .conformance_family_contract import (
    ConformanceFamily,
    ConformanceFamilyContext,
    ConformanceOutcome,
    ConformancePreparation,
    RegisteredExecutorConformanceCase,
)

_EJERCICIO = 2025
_CLASS = RetencionSoportadaClase.TRABAJO
_NOTE = "No payer withheld on this class in the ejercicio."


def _prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
    definition_id = context.definition.definition_id
    subject = profile_operation_subject(str(context.profile_id))
    ports = build_retencion_soportada_absence_ports(profile_id=context.profile_id, operation=context.operation)
    identity = (_EJERCICIO, _CLASS)
    attestation = RetencionSoportadaAbsence(
        ejercicio=_EJERCICIO,
        income_class=_CLASS,
        note=_NOTE,
        attested_at=datetime(2026, 4, 2, 9, 0, tzinfo=UTC),
    )

    def seed() -> str:
        return attest_retencion_soportada_absence(
            attestation, ports=ports, expected_revision_id=ABSENT_SECURE_OBJECT_REVISION_ID
        )

    if definition_id == RETENCION_SOPORTADA_ABSENCE_ATTEST_OPERATION_DEFINITION_ID:

        def verify_attest(outcome: ConformanceOutcome) -> None:
            result = outcome.resolve_result(RetencionSoportadaAbsenceMutationProjection)
            assert result.outcome == "attested"
            assert result.profile_id == context.profile_id
            assert result.refusal is None
            assert result.attestation is not None
            stored, revision_id = ports.attestations.load_revisioned(identity)
            assert stored is not None
            assert stored.state is RetencionSoportadaAbsenceState.ACTIVE
            assert stored.note == _NOTE
            assert result.attestation.revision_id == revision_id
            assert result.attestation.note == _NOTE
            assert result.attestation.state is RetencionSoportadaAbsenceState.ACTIVE
            assert ports.records.load_records(_EJERCICIO) == ()

        return ConformancePreparation(
            subject,
            RetencionSoportadaAbsenceAttestRequest(
                profile_id=context.profile_id, ejercicio=_EJERCICIO, income_class=_CLASS, note=_NOTE
            ),
            verify=verify_attest,
        )

    if definition_id == RETENCION_SOPORTADA_ABSENCE_WITHDRAW_OPERATION_DEFINITION_ID:
        revision_id = seed()

        def verify_withdraw(outcome: ConformanceOutcome) -> None:
            result = outcome.resolve_result(RetencionSoportadaAbsenceMutationProjection)
            assert result.outcome == "withdrawn"
            assert result.profile_id == context.profile_id
            assert result.refusal is None
            assert result.attestation is not None
            stored, stored_revision_id = ports.attestations.load_revisioned(identity)
            assert stored is not None
            assert stored.state is RetencionSoportadaAbsenceState.WITHDRAWN
            assert stored.withdrawn_at is not None
            assert stored.attested_at == attestation.attested_at
            assert stored_revision_id != revision_id
            assert result.attestation.revision_id == stored_revision_id
            assert result.attestation.state is RetencionSoportadaAbsenceState.WITHDRAWN
            assert result.attestation.withdrawn_at == stored.withdrawn_at

        return ConformancePreparation(
            subject,
            RetencionSoportadaAbsenceWithdrawRequest(
                profile_id=context.profile_id,
                ejercicio=_EJERCICIO,
                income_class=_CLASS,
                expected_revision_id=revision_id,
            ),
            verify=verify_withdraw,
        )

    if definition_id == RETENCION_SOPORTADA_ABSENCE_LIST_OPERATION_DEFINITION_ID:
        revision_id = seed()

        def verify_list(outcome: ConformanceOutcome) -> None:
            result = outcome.resolve_result(RetencionSoportadaAbsenceListProjection)
            assert result.profile_id == context.profile_id
            assert result.ejercicio == _EJERCICIO
            (row,) = result.attestations
            assert row.income_class is _CLASS
            assert row.income_class_label
            assert row.note == _NOTE
            assert row.revision_id == revision_id
            assert row.state is RetencionSoportadaAbsenceState.ACTIVE
            assert ports.attestations.load_revisioned(identity)[1] == revision_id

        return ConformancePreparation(
            subject,
            RetencionSoportadaAbsenceListRequest(profile_id=context.profile_id, ejercicio=_EJERCICIO),
            verify=verify_list,
        )

    raise AssertionError(f"unsupported suffered-withholding absence conformance definition: {definition_id}")


RETENCION_SOPORTADA_ABSENCE_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=(
        RegisteredExecutorConformanceCase(
            RETENCION_SOPORTADA_ABSENCE_ATTEST_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
        ),
        RegisteredExecutorConformanceCase(
            RETENCION_SOPORTADA_ABSENCE_WITHDRAW_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
        ),
        RegisteredExecutorConformanceCase(
            RETENCION_SOPORTADA_ABSENCE_LIST_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
        ),
    ),
    prepare=_prepare,
)
