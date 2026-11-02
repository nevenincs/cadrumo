"""The registered absence operations run against the real composed ports, encrypted store and authority.

Only the operation host's event and operand plumbing is a minimal stand-in. The
retained result is what the CLI bridge reads back, so its outcome, effect and
refusal code are asserted here. All identifiers and notes are synthetic.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from pydantic import BaseModel

from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.operations.models import OperationIdentity, OperationRequest
from cadrumo.application.operations.owner import OperationExecutorContext
from cadrumo.application.operations.refusal_evidence import OperationRefusalEvidence
from cadrumo.application.retencion_soportada_absence.contracts import (
    RETENCION_SOPORTADA_ABSENCE_ATTEST_OPERATION_DEFINITION_ID,
    RETENCION_SOPORTADA_ABSENCE_WITHDRAW_OPERATION_DEFINITION_ID,
)
from cadrumo.application.retencion_soportada_absence.executor import RetencionSoportadaAbsenceExecutor
from cadrumo.application.retencion_soportada_absence.requests import (
    RetencionSoportadaAbsenceAttestRequest,
    RetencionSoportadaAbsenceWithdrawRequest,
)
from cadrumo.application.retencion_soportada_absence.results import RetencionSoportadaAbsenceExecutionResult
from cadrumo.application.tests.operation_host_fakes import RecordingEvents
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.core.operations import OperationEffect, profile_operation_subject
from cadrumo.core.retencion_soportada import RetencionSoportadaClase
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.renta.retencion_soportada_absence import RetencionSoportadaAbsenceState
from cadrumo.entrypoints.retencion_soportada_absence_composition import build_retencion_soportada_absence_ports

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]

_PROFILE = "3f1c8b2e-5d4a-4e6b-9c7d-0a1b2c3d4e5f"
_EJERCICIO = 2025
_NOTE = "Synthetic note: no payer withheld on this income."


class _Cancellation:
    def __init__(self) -> None:
        self.inside = False

    @asynccontextmanager
    async def irreversible_section(self):
        self.inside = True
        try:
            yield
        finally:
            self.inside = False


class _Operands:
    def __init__(self, cancellation: _Cancellation) -> None:
        self._cancellation = cancellation
        self.value: BaseModel | None = None

    async def put(self, value: BaseModel, *, written_at: object) -> str:
        del written_at
        assert self._cancellation.inside
        self.value = value
        return "d" * 64


class _Context:
    def __init__(self, authority_operation: PinnedAuthorityOperation, definition_id: str) -> None:
        self.identity = OperationIdentity(
            operation_id="c" * 64,
            definition_id=definition_id,
            subject_ref=profile_operation_subject(_PROFILE),
        )
        self.authority_operation = authority_operation
        self.events = RecordingEvents()
        self.cancellation = _Cancellation()
        self.operands = _Operands(self.cancellation)


def _run(
    authority_operation: PinnedAuthorityOperation, definition_id: str, payload: BaseModel
) -> tuple[str | OperationRefusalEvidence, RetencionSoportadaAbsenceExecutionResult, list[OperationEffect]]:
    context = _Context(authority_operation, definition_id)
    request = OperationRequest(
        definition_id=definition_id, subject_ref=profile_operation_subject(_PROFILE), payload=payload
    )
    executor = RetencionSoportadaAbsenceExecutor(build_retencion_soportada_absence_ports, definition_id=definition_id)
    outcome = asyncio.run(executor.execute(request, cast(OperationExecutorContext, context)))
    retained = context.operands.value
    assert isinstance(retained, RetencionSoportadaAbsenceExecutionResult)
    return outcome, retained, context.events.effects


def _attest(authority_operation: PinnedAuthorityOperation, *, expected: str | None = None):
    return _run(
        authority_operation,
        RETENCION_SOPORTADA_ABSENCE_ATTEST_OPERATION_DEFINITION_ID,
        RetencionSoportadaAbsenceAttestRequest(
            profile_id=UUID(_PROFILE),
            ejercicio=_EJERCICIO,
            income_class=RetencionSoportadaClase.CAPITAL_MOBILIARIO,
            note=_NOTE,
            expected_revision_id=expected,
        ),
    )


def _withdraw(authority_operation: PinnedAuthorityOperation, expected: str):
    return _run(
        authority_operation,
        RETENCION_SOPORTADA_ABSENCE_WITHDRAW_OPERATION_DEFINITION_ID,
        RetencionSoportadaAbsenceWithdrawRequest(
            profile_id=UUID(_PROFILE),
            ejercicio=_EJERCICIO,
            income_class=RetencionSoportadaClase.CAPITAL_MOBILIARIO,
            expected_revision_id=expected,
        ),
    )


def test_attest_refuse_and_withdraw_through_the_registered_executor(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE):
        outcome, attested, effects = _attest(operation)
        assert not isinstance(outcome, OperationRefusalEvidence)
        assert effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]
        assert attested.outcome == "success"
        assert attested.attestation is not None
        assert attested.attestation.state is RetencionSoportadaAbsenceState.ACTIVE
        assert attested.attestation.note == _NOTE
        revision_id = attested.attestation.revision_id

        refused, repeated, refused_effects = _attest(operation, expected=revision_id)
        assert isinstance(refused, OperationRefusalEvidence)
        assert refused.refusal_code == "REFUSED_RETENCION_SOPORTADA_ABSENCE"
        assert refused_effects == [OperationEffect.UNKNOWN, OperationEffect.NONE]
        assert repeated.outcome == "refused"
        assert repeated.refusal is not None
        assert repeated.refusal.reason == "already_attested"

        stale, stale_result, _ = _withdraw(operation, "f" * 64)
        assert isinstance(stale, OperationRefusalEvidence)
        assert stale.refusal_code == "REFUSED_RETENCION_SOPORTADA_REVISION_CONFLICT"
        assert stale_result.refusal is not None
        assert stale_result.refusal.reason == "stale_revision"

        _, withdrawn, _ = _withdraw(operation, revision_id)
        assert withdrawn.outcome == "success"
        assert withdrawn.attestation is not None
        assert withdrawn.attestation.state is RetencionSoportadaAbsenceState.WITHDRAWN
        assert withdrawn.attestation.revision_id != revision_id


def test_the_composed_ports_refuse_a_profile_other_than_the_active_one(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE), pytest.raises(ProfileAccessRefusedError):
        build_retencion_soportada_absence_ports(
            profile_id=UUID("22222222-2222-4222-8222-222222222222"), operation=operation
        )
