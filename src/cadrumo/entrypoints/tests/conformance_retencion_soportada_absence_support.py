"""Suffered-withholding absence attestation operations through the real supervisor matrix."""

from __future__ import annotations

from datetime import UTC, datetime

from ...application.aggregation.retencion_soportada_absence_repository import (
    attest_retencion_soportada_absence,
)
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
_CLASS = RetencionSoportadaClase.CAPITAL_MOBILIARIO
_NOTE = "Synthetic note: no payer withheld."


def _prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
    definition_id = context.definition.definition_id
    subject = profile_operation_subject(str(context.profile_id))
    ports = build_retencion_soportada_absence_ports(profile_id=context.profile_id, operation=context.operation)
    attestations = ports.attestations

    def seed() -> str:
        return attest_retencion_soportada_absence(
            RetencionSoportadaAbsence(
                ejercicio=_EJERCICIO,
                income_class=_CLASS,
                note=_NOTE,
                attested_at=datetime(2026, 4, 2, 9, 0, tzinfo=UTC),
            ),
            ports=ports,
            expected_revision_id=ABSENT_SECURE_OBJECT_REVISION_ID,
        )

    if definition_id == RETENCION_SOPORTADA_ABSENCE_ATTEST_OPERATION_DEFINITION_ID:

        def verify_attest(outcome: ConformanceOutcome) -> None:
            result = outcome.resolve_result(RetencionSoportadaAbsenceMutationProjection)
            assert result.outcome == "attested"
            assert result.attestation is not None
            ((stored, revision_id),) = attestations.list_revisioned(_EJERCICIO)
            assert stored.note == _NOTE
            assert stored.state is RetencionSoportadaAbsenceState.ACTIVE
            assert result.attestation.revision_id == revision_id

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
            assert result.attestation is not None
            ((stored, stored_revision),) = attestations.list_revisioned(_EJERCICIO)
            assert stored.state is RetencionSoportadaAbsenceState.WITHDRAWN
            assert stored_revision != revision_id
            assert result.attestation.revision_id == stored_revision

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
            (row,) = result.attestations
            assert row.income_class is _CLASS
            assert row.income_class_label
            assert row.revision_id == revision_id
            assert row.state is RetencionSoportadaAbsenceState.ACTIVE
            assert attestations.list_revisioned(_EJERCICIO)[0][1] == revision_id

        return ConformancePreparation(
            subject,
            RetencionSoportadaAbsenceListRequest(profile_id=context.profile_id, ejercicio=_EJERCICIO),
            verify=verify_list,
        )

    raise AssertionError(f"unsupported absence attestation conformance definition: {definition_id}")


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
