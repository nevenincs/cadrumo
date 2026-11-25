"""The registered absence operations run against the real composed ports, encrypted store and authority.

Only the operation host's event and operand plumbing is a minimal stand-in. The
retained result is what the CLI bridge reads back, so its outcome, effect and
refusal code are asserted here. All identifiers and notes are synthetic.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from decimal import Decimal
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from pydantic import BaseModel

from cadrumo.adapters.persistence.profile.tests.retencion_soportada_seed import seed_payer_certificate
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.aggregation.retencion_soportada_absence_repository import RetencionSoportadaAbsenceWritePorts
from cadrumo.application.aggregation.retencion_soportada_repository import PinnedRetencionSoportadaWriteAuthority
from cadrumo.application.operations.models import OperationIdentity, OperationRequest
from cadrumo.application.operations.owner import OperationExecutorContext
from cadrumo.application.operations.refusal_evidence import OperationRefusalEvidence
from cadrumo.application.retencion_soportada_absence.contracts import (
    RETENCION_SOPORTADA_ABSENCE_ATTEST_OPERATION_DEFINITION_ID,
    RETENCION_SOPORTADA_ABSENCE_LIST_OPERATION_DEFINITION_ID,
    RETENCION_SOPORTADA_ABSENCE_WITHDRAW_OPERATION_DEFINITION_ID,
)
from cadrumo.application.retencion_soportada_absence.executor import RetencionSoportadaAbsenceExecutor
from cadrumo.application.retencion_soportada_absence.requests import (
    RetencionSoportadaAbsenceAttestRequest,
    RetencionSoportadaAbsenceListRequest,
    RetencionSoportadaAbsenceWithdrawRequest,
)
from cadrumo.application.retencion_soportada_absence.results import RetencionSoportadaAbsenceExecutionResult
from cadrumo.application.tests.operation_host_fakes import RecordingEvents
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.core.config import override_settings
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.i18n.render import tr
from cadrumo.core.operations import OperationEffect, profile_operation_subject
from cadrumo.core.retencion_soportada import RetencionSoportadaClase
from cadrumo.core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
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
    def __init__(self, cancellation: _Cancellation, *, writes: bool) -> None:
        self._cancellation = cancellation
        self._writes = writes
        self.value: BaseModel | None = None

    async def put(self, value: BaseModel, *, written_at: object) -> str:
        del written_at
        assert self._cancellation.inside == self._writes
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
        self.operands = _Operands(
            self.cancellation, writes=definition_id != RETENCION_SOPORTADA_ABSENCE_LIST_OPERATION_DEFINITION_ID
        )


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


def _attest(
    authority_operation: PinnedAuthorityOperation,
    *,
    expected: str | None = None,
    income_class: RetencionSoportadaClase = RetencionSoportadaClase.CAPITAL_MOBILIARIO,
):
    return _run(
        authority_operation,
        RETENCION_SOPORTADA_ABSENCE_ATTEST_OPERATION_DEFINITION_ID,
        RetencionSoportadaAbsenceAttestRequest(
            profile_id=UUID(_PROFILE),
            ejercicio=_EJERCICIO,
            income_class=income_class,
            note=_NOTE,
            expected_revision_id=expected,
        ),
    )


def _withdraw(
    authority_operation: PinnedAuthorityOperation,
    expected: str,
    *,
    income_class: RetencionSoportadaClase = RetencionSoportadaClase.CAPITAL_MOBILIARIO,
):
    return _run(
        authority_operation,
        RETENCION_SOPORTADA_ABSENCE_WITHDRAW_OPERATION_DEFINITION_ID,
        RetencionSoportadaAbsenceWithdrawRequest(
            profile_id=UUID(_PROFILE),
            ejercicio=_EJERCICIO,
            income_class=income_class,
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


def _list(authority_operation: PinnedAuthorityOperation, ejercicio: int = _EJERCICIO):
    return _run(
        authority_operation,
        RETENCION_SOPORTADA_ABSENCE_LIST_OPERATION_DEFINITION_ID,
        RetencionSoportadaAbsenceListRequest(profile_id=UUID(_PROFILE), ejercicio=ejercicio),
    )


def test_list_shows_every_stored_attestation_with_the_revision_a_withdrawal_needs(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE):
        # A year with no attestations lists as empty: success, no change, no refusal.
        outcome, empty, empty_effects = _list(operation)
        assert not isinstance(outcome, OperationRefusalEvidence)
        assert empty.outcome == "success"
        assert empty.attestations == ()
        assert empty_effects == [OperationEffect.NONE]

        _, first, _ = _attest(operation)
        assert first.attestation is not None
        _, withdrawn, _ = _withdraw(operation, first.attestation.revision_id)
        assert withdrawn.attestation is not None
        _, second, _ = _attest(operation, income_class=RetencionSoportadaClase.GANANCIA_PATRIMONIAL)
        assert second.attestation is not None

        _, listed, effects = _list(operation)
        assert effects == [OperationEffect.NONE]
        assert listed.attestations is not None
        rows = {row.income_class: row for row in listed.attestations}
        assert set(rows) == {RetencionSoportadaClase.CAPITAL_MOBILIARIO, RetencionSoportadaClase.GANANCIA_PATRIMONIAL}
        stored_withdrawn = rows[RetencionSoportadaClase.CAPITAL_MOBILIARIO]
        assert stored_withdrawn.state is RetencionSoportadaAbsenceState.WITHDRAWN
        assert stored_withdrawn.revision_id == withdrawn.attestation.revision_id
        assert stored_withdrawn.withdrawn_at == withdrawn.attestation.withdrawn_at
        stored_active = rows[RetencionSoportadaClase.GANANCIA_PATRIMONIAL]
        assert stored_active.state is RetencionSoportadaAbsenceState.ACTIVE
        assert stored_active.revision_id == second.attestation.revision_id
        assert stored_active.note == _NOTE
        assert stored_active.income_class_label.strip()
        assert stored_withdrawn.income_class_label != stored_active.income_class_label
        assert "retencion_soportada" not in stored_active.income_class_label

        # The listed revision is the one the guarded write accepts.
        _, again, _ = _withdraw(
            operation, stored_active.revision_id, income_class=RetencionSoportadaClase.GANANCIA_PATRIMONIAL
        )
        assert again.outcome == "success"
        assert again.attestation is not None
        assert again.attestation.state is RetencionSoportadaAbsenceState.WITHDRAWN

        # Only the requested ejercicio is listed.
        assert _list(operation, _EJERCICIO - 1)[1].attestations == ()


def test_the_composed_ports_refuse_a_profile_other_than_the_active_one(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE), pytest.raises(ProfileAccessRefusedError):
        build_retencion_soportada_absence_ports(
            profile_id=UUID("22222222-2222-4222-8222-222222222222"), operation=operation
        )


class _UndeclaredFamilyAuthority:
    """A generation whose Modelo 100 declares no member of the family for any ejercicio."""

    def __init__(self, operation: PinnedAuthorityOperation) -> None:
        self._pinned = PinnedRetencionSoportadaWriteAuthority(operation)

    def admits_ejercicio(self, ejercicio: int) -> bool:
        return self._pinned.admits_ejercicio(ejercicio)

    def declares_family(self, ejercicio: int) -> bool:
        del ejercicio
        return False


def _attest_without_a_declared_family(
    authority_operation: PinnedAuthorityOperation,
) -> RetencionSoportadaAbsenceExecutionResult:
    def factory(*, profile_id: UUID, operation: PinnedAuthorityOperation) -> RetencionSoportadaAbsenceWritePorts:
        ports = build_retencion_soportada_absence_ports(profile_id=profile_id, operation=operation)
        return RetencionSoportadaAbsenceWritePorts(
            attestations=ports.attestations, records=ports.records, authority=_UndeclaredFamilyAuthority(operation)
        )

    definition_id = RETENCION_SOPORTADA_ABSENCE_ATTEST_OPERATION_DEFINITION_ID
    context = _Context(authority_operation, definition_id)
    request = OperationRequest(
        definition_id=definition_id,
        subject_ref=profile_operation_subject(_PROFILE),
        payload=RetencionSoportadaAbsenceAttestRequest(
            profile_id=UUID(_PROFILE),
            ejercicio=_EJERCICIO,
            income_class=RetencionSoportadaClase.CAPITAL_MOBILIARIO,
            note=_NOTE,
        ),
    )
    executor = RetencionSoportadaAbsenceExecutor(factory, definition_id=definition_id)
    asyncio.run(executor.execute(request, cast(OperationExecutorContext, context)))
    retained = context.operands.value
    assert isinstance(retained, RetencionSoportadaAbsenceExecutionResult)
    return retained


@pytest.mark.parametrize("language", list(OutputLanguage))
def test_every_refusal_reason_serves_its_own_sentence_in_the_workers_language(
    tmp_path: Path, operation: PinnedAuthorityOperation, language: OutputLanguage
) -> None:
    refusals: dict[str, RetencionSoportadaAbsenceExecutionResult] = {}
    with (
        override_settings(cadrumo_output_language=language.value),
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE),
    ):
        _, attested, _ = _attest(operation)
        assert attested.attestation is not None
        revision_id = attested.attestation.revision_id
        refusals["already_attested"] = _attest(operation, expected=revision_id)[1]
        refusals["stale_revision"] = _withdraw(operation, "f" * 64)[1]
        refusals["not_attested"] = _withdraw(
            operation, ABSENT_SECURE_OBJECT_REVISION_ID, income_class=RetencionSoportadaClase.GANANCIA_PATRIMONIAL
        )[1]
        refusals["ejercicio_unsupported"] = _run(
            operation,
            RETENCION_SOPORTADA_ABSENCE_ATTEST_OPERATION_DEFINITION_ID,
            RetencionSoportadaAbsenceAttestRequest(
                profile_id=UUID(_PROFILE),
                ejercicio=2000,
                income_class=RetencionSoportadaClase.CAPITAL_MOBILIARIO,
                note=_NOTE,
            ),
        )[1]
        refusals["family_not_declared"] = _attest_without_a_declared_family(operation)
        seed_payer_certificate(
            operation=operation,
            taxpayer_tax_id="00000000T",
            ejercicio=_EJERCICIO,
            payer_tax_id="B00000001",
            income_class=RetencionSoportadaClase.TRABAJO,
            retencion=Decimal("1200.00"),
        )
        refusals["records_present"] = _attest(operation, income_class=RetencionSoportadaClase.TRABAJO)[1]

    assert set(refusals) == {
        "already_attested",
        "stale_revision",
        "not_attested",
        "ejercicio_unsupported",
        "family_not_declared",
        "records_present",
    }
    for reason, result in refusals.items():
        assert result.refusal is not None
        assert result.refusal.reason == reason
        words = result.refusal.refusal_words
        assert words == tr(f"aggregation.retencion_soportada_absence.served.{reason}", locale=language.value)
        assert result.refusal.refusal_words_language is language
        assert words is not None
        assert "--" not in words
        assert not words.startswith("aggregation.")
        assert _NOTE not in words
        assert "B00000001" not in words
