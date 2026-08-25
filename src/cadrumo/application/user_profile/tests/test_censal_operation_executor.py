"""Composed durable lifecycle proofs for the production censo executor."""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest

from ....adapters.persistence.operations import (
    OperationJournalRepository,
    OperationLeaseFilesystemRepository,
    operation_secure_reference_repository,
)
from ....adapters.persistence.storage.custody import (
    load_committed_profile_password_material,
    unlock_profile_custody,
)
from ....core import OperationEffect, OperationLifecycle, OperationTerminalCondition
from ....core.config import override_settings
from ....domain.user_profile import UserProfileFact
from ....tests.aeat_literal_fixtures import aeat_url
from ....tests.secure_sql import isolated_profile_storage_root
from ...operations import (
    OperationApplyResponse,
    OperationExecutorFactory,
    OperationRegistry,
    OperationRejectResponse,
    OperationRequest,
    OperationSupervisor,
    operation_public_schema_reference,
)
from .._capsule_record import ProfileRecordSession, ProfileRecordStore
from .._censal_observation import CensalObservation, CensalObservationAddress, CensalObservationIdentity
from .._censal_operation import (
    CENSAL_OPERATION_DEFINITION,
    CENSAL_PHASE_SETTLEMENT,
    CENSAL_REVIEW_RESPONSE_SCHEMA_BINDING,
    CensalFieldIntent,
    CensalOperationExecutor,
    CensalOperationRequest,
    CensalProfileBaseline,
    CensalReviewedFieldIntent,
    CensalReviewedOperand,
    build_censal_operation_registration,
)
from .._cotejo_apply import apply_cotejo
from .._custody_ports import profile_custody_secure_object_repository
from .._profile_record_repository import ProfileRecordRepository, bound_profile_record_session
from .._registration import register_profile_with_credentials

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_NOW = datetime(2026, 8, 24, 18, tzinfo=UTC)
_PASSPHRASE = "censal-operation-executor-passphrase"  # noqa: S105 - synthetic fixture
_RESPONSE_TOKEN = "a" * 64


@contextmanager
def _subject(tmp_path: Path) -> Generator[tuple[str, object, ProfileRecordSession]]:
    with isolated_profile_storage_root(tmp_path=tmp_path) as root:
        outcome = register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
            label="Censal operation executor",
            passphrase=_PASSPHRASE,
            facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
        )
        material = load_committed_profile_password_material(UUID(outcome.profile_id), root=root)
        unlocked = unlock_profile_custody(material.envelope, _PASSPHRASE, sentinel=material.sentinel)
        session = ProfileRecordSession.from_envelope(envelope=material.envelope, dek=unlocked.dek)
        try:
            with (
                bound_profile_record_session(session),
                override_settings(cadrumo_active_profile=outcome.profile_id),
                profile_custody_secure_object_repository(
                    profile_id=session.profile_id,
                    dek=session.encryption_key(),
                    root=root,
                ) as objects,
            ):
                yield outcome.profile_id, objects, session
        finally:
            session.close()


def _observation() -> CensalObservation:
    return CensalObservation(
        identity=CensalObservationIdentity(nif="12345678Z"),
        domicilio_fiscal=CensalObservationAddress(
            tipo_via="CALLE",
            nombre_via="Mayor",
            numero_casa="7",
            codigo_postal="28013",
            referencia_catastral="1234567VK4713C0001AB",
        ),
        domicilio_notificacion=CensalObservationAddress(),
        captured_at=_NOW,
        source_url=aeat_url("sede", "/censo/consulta"),
    )


def _payload(profile_id: str) -> CensalOperationRequest:
    record = ProfileRecordRepository.for_current_session(profile_id).load(profile_id)
    return CensalOperationRequest(
        baseline=CensalProfileBaseline.from_record(record),
        field_intents=tuple(
            CensalReviewedFieldIntent(path=path, intent=CensalFieldIntent.ADOPT)
            for path in (
                "contact.fiscal_address",
                "contact.postcode",
                "contact.fiscal_address_cadastral_reference",
            )
        ),
    )


def _supervisor(
    *,
    root: Path,
    objects: object,
    executor: CensalOperationExecutor,
    owner: str,
    token: str,
    now: datetime = _NOW,
) -> OperationSupervisor:
    operands = operation_secure_reference_repository(objects=objects)  # type: ignore[arg-type]
    definition = CENSAL_OPERATION_DEFINITION.model_copy(
        update={
            "executor_factory": OperationExecutorFactory(
                request_type=CensalOperationRequest,
                executor_type=CensalOperationExecutor,
                build=lambda: executor,
            )
        }
    )
    journal = OperationJournalRepository(storage_root=root)
    return OperationSupervisor(
        registry=OperationRegistry(
            definitions=(definition,),
            public_registrations=(build_censal_operation_registration(definition),),
        ),
        journal=journal,
        event_stream=journal,
        leases=OperationLeaseFilesystemRepository(storage_root=root),
        operands=operands,
        owner_id=owner,
        lease_token_factory=lambda: token,
        clock=lambda: now,
        lease_duration=timedelta(minutes=1),
        execution_timeout=timedelta(minutes=5),
        cleanup_timeout=timedelta(minutes=1),
        response_token_factory=lambda: _RESPONSE_TOKEN,
    )


async def _wait_for_phase(supervisor: OperationSupervisor, operation_id: str, phase: str):
    for _ in range(100):
        snapshot = await supervisor.inspect(operation_id)
        if snapshot.phase_code == phase or snapshot.lifecycle is OperationLifecycle.TERMINAL:
            return snapshot
        await asyncio.sleep(0)
    raise AssertionError(f"operation did not reach {phase}")


async def _start(supervisor: OperationSupervisor, operation_id: str):
    return await supervisor.start(operation_id)


def test_censal_executor_acquires_once_recovers_review_and_applies_exact_operand(tmp_path: Path) -> None:
    acquisitions = 0

    async def acquire() -> CensalObservation:
        nonlocal acquisitions
        acquisitions += 1
        return _observation()

    with _subject(tmp_path) as (profile_id, objects, _session):
        durable_root = tmp_path / "operations"
        executor = CensalOperationExecutor(acquire=acquire)
        owner = _supervisor(
            root=durable_root,
            objects=objects,
            executor=executor,
            owner="1" * 64,
            token="2" * 64,
        )
        request = OperationRequest(
            definition_id=CENSAL_OPERATION_DEFINITION.definition_id,
            subject_ref=profile_id,
            payload=_payload(profile_id),
        )
        assert "response_token" not in request.payload.model_dump()

        async def run() -> None:
            operation_id = await owner.submit(request, operation_id="3" * 64)
            waiting = await _start(owner, operation_id)
            assert waiting.lifecycle is OperationLifecycle.WAITING_FOR_INTERACTION
            assert waiting.effect is OperationEffect.NONE
            pending = waiting.pending_interaction
            assert pending is not None
            assert pending.request.revision == waiting.revision
            assert pending.request.response_schema_ref == operation_public_schema_reference(
                CENSAL_REVIEW_RESPONSE_SCHEMA_BINDING.identity
            )
            assert acquisitions == 1

            recovery = _supervisor(
                root=durable_root,
                objects=objects,
                executor=executor,
                owner="4" * 64,
                token="5" * 64,
                now=_NOW + timedelta(minutes=2),
            )
            recovered = await recovery.reconcile(operation_id)
            assert recovered.lifecycle is OperationLifecycle.WAITING_FOR_INTERACTION
            assert acquisitions == 1
            recovered_pending = recovered.pending_interaction
            assert recovered_pending is not None

            await recovery.respond(
                OperationApplyResponse(
                    interaction_id=recovered_pending.request.interaction_id,
                    operation_id=operation_id,
                    revision=recovered_pending.request.revision,
                    response_token=_RESPONSE_TOKEN,
                    continuation_digest=recovered_pending.request.continuation_digest,
                    reviewed_proposal_digest=recovered_pending.reviewed_proposal_digest,
                    actor_ref="operator:integration",
                    responded_at=_NOW + timedelta(minutes=2),
                    baseline_digest=recovered_pending.baseline_digest,
                    proposed_effect_digest=recovered_pending.proposed_effect_digest,
                )
            )
            applied = await _wait_for_phase(recovery, operation_id, CENSAL_PHASE_SETTLEMENT)
            assert applied.effect is OperationEffect.UPDATED
            assert acquisitions == 1

        asyncio.run(run())
        assert all(
            _RESPONSE_TOKEN.encode() not in path.read_bytes() for path in durable_root.rglob("*") if path.is_file()
        )
        record = ProfileRecordRepository.for_current_session(profile_id).load(profile_id)
        assert record.record_revision == request.payload.baseline.record_revision + 1


def test_censal_executor_rejects_none_and_post_commit_failure_stays_unknown(tmp_path: Path) -> None:
    async def acquire() -> CensalObservation:
        return _observation()

    with _subject(tmp_path) as (profile_id, objects, session):
        durable_root = tmp_path / "operations"
        before = ProfileRecordRepository.for_current_session(profile_id).load(profile_id)

        async def reject_run() -> None:
            supervisor = _supervisor(
                root=durable_root,
                objects=objects,
                executor=CensalOperationExecutor(acquire=acquire),
                owner="6" * 64,
                token="7" * 64,
            )
            request = OperationRequest(
                definition_id=CENSAL_OPERATION_DEFINITION.definition_id,
                subject_ref=profile_id,
                payload=_payload(profile_id),
            )
            operation_id = await supervisor.submit(request, operation_id="8" * 64)
            waiting = await _start(supervisor, operation_id)
            pending = waiting.pending_interaction
            assert pending is not None
            await supervisor.respond(
                OperationRejectResponse(
                    interaction_id=pending.request.interaction_id,
                    operation_id=operation_id,
                    revision=pending.request.revision,
                    response_token=_RESPONSE_TOKEN,
                    continuation_digest=pending.request.continuation_digest,
                    reviewed_proposal_digest=pending.reviewed_proposal_digest,
                    actor_ref="operator:integration",
                    responded_at=_NOW,
                )
            )
            rejected = await _wait_for_phase(supervisor, operation_id, CENSAL_PHASE_SETTLEMENT)
            assert rejected.effect is OperationEffect.NONE

        asyncio.run(reject_run())
        assert ProfileRecordRepository.for_current_session(profile_id).load(profile_id) == before

        history_before_race = ProfileRecordStore(session=session).history()

        def competing_write_then_stale(operand: CensalReviewedOperand) -> None:
            apply_cotejo(None, adopted=(), divergences=())
            apply_cotejo(None, reviewed_proposal=operand)

        async def stale_race_run() -> None:
            supervisor = _supervisor(
                root=tmp_path / "stale-race-operations",
                objects=objects,
                executor=CensalOperationExecutor(acquire=acquire, apply=competing_write_then_stale),
                owner="d" * 64,
                token="e" * 64,
            )
            request = OperationRequest(
                definition_id=CENSAL_OPERATION_DEFINITION.definition_id,
                subject_ref=profile_id,
                payload=_payload(profile_id),
            )
            operation_id = await supervisor.submit(request, operation_id="f" * 64)
            waiting = await _start(supervisor, operation_id)
            pending = waiting.pending_interaction
            assert pending is not None
            await supervisor.respond(
                OperationApplyResponse(
                    interaction_id=pending.request.interaction_id,
                    operation_id=operation_id,
                    revision=pending.request.revision,
                    response_token=_RESPONSE_TOKEN,
                    continuation_digest=pending.request.continuation_digest,
                    reviewed_proposal_digest=pending.reviewed_proposal_digest,
                    actor_ref="operator:integration",
                    responded_at=_NOW,
                    baseline_digest=pending.baseline_digest,
                    proposed_effect_digest=pending.proposed_effect_digest,
                )
            )
            terminal = await supervisor.await_terminal(operation_id)
            assert terminal.terminal_condition is OperationTerminalCondition.FAILED
            assert terminal.effect is OperationEffect.NONE

        asyncio.run(stale_race_run())
        after_race = ProfileRecordRepository.for_current_session(profile_id).load(profile_id)
        history_after_race = ProfileRecordStore(session=session).history()
        assert after_race.record_revision == before.record_revision + 1
        assert len(history_after_race) == len(history_before_race) + 1

        def commit_then_fail(operand: CensalReviewedOperand) -> None:
            apply_cotejo(None, reviewed_proposal=operand)
            raise RuntimeError("synthetic repository acknowledgement loss")

        async def ambiguous_run() -> None:
            supervisor = _supervisor(
                root=tmp_path / "ambiguous-operations",
                objects=objects,
                executor=CensalOperationExecutor(acquire=acquire, apply=commit_then_fail),
                owner="9" * 64,
                token="b" * 64,
            )
            request = OperationRequest(
                definition_id=CENSAL_OPERATION_DEFINITION.definition_id,
                subject_ref=profile_id,
                payload=_payload(profile_id),
            )
            operation_id = await supervisor.submit(request, operation_id="c" * 64)
            waiting = await _start(supervisor, operation_id)
            pending = waiting.pending_interaction
            assert pending is not None
            await supervisor.respond(
                OperationApplyResponse(
                    interaction_id=pending.request.interaction_id,
                    operation_id=operation_id,
                    revision=pending.request.revision,
                    response_token=_RESPONSE_TOKEN,
                    continuation_digest=pending.request.continuation_digest,
                    reviewed_proposal_digest=pending.reviewed_proposal_digest,
                    actor_ref="operator:integration",
                    responded_at=_NOW,
                    baseline_digest=pending.baseline_digest,
                    proposed_effect_digest=pending.proposed_effect_digest,
                )
            )
            terminal = await supervisor.await_terminal(operation_id)
            assert terminal.terminal_condition is OperationTerminalCondition.FAILED
            assert terminal.effect is OperationEffect.UNKNOWN

        asyncio.run(ambiguous_run())
        after = ProfileRecordRepository.for_current_session(profile_id).load(profile_id)
        assert after.record_revision == before.record_revision + 2


def test_censal_executor_cancellation_before_irreversible_entry_keeps_none_and_writes_nothing(
    tmp_path: Path,
) -> None:
    reached_boundary = asyncio.Event()
    release_boundary = asyncio.Event()

    async def acquire() -> CensalObservation:
        return _observation()

    async def hold_before_entry() -> None:
        reached_boundary.set()
        await release_boundary.wait()

    with _subject(tmp_path) as (profile_id, objects, session):
        before = ProfileRecordRepository.for_current_session(profile_id).load(profile_id)
        history_before = ProfileRecordStore(session=session).history()
        supervisor = _supervisor(
            root=tmp_path / "cancel-race-operations",
            objects=objects,
            executor=CensalOperationExecutor(
                acquire=acquire,
                before_irreversible_section=hold_before_entry,
            ),
            owner="1" * 64,
            token="2" * 64,
        )
        request = OperationRequest(
            definition_id=CENSAL_OPERATION_DEFINITION.definition_id,
            subject_ref=profile_id,
            payload=_payload(profile_id),
        )

        async def run() -> None:
            operation_id = await supervisor.submit(request, operation_id="3" * 64)
            waiting = await _start(supervisor, operation_id)
            pending = waiting.pending_interaction
            assert pending is not None
            await supervisor.respond(
                OperationApplyResponse(
                    interaction_id=pending.request.interaction_id,
                    operation_id=operation_id,
                    revision=pending.request.revision,
                    response_token=_RESPONSE_TOKEN,
                    continuation_digest=pending.request.continuation_digest,
                    reviewed_proposal_digest=pending.reviewed_proposal_digest,
                    actor_ref="operator:integration",
                    responded_at=_NOW,
                    baseline_digest=pending.baseline_digest,
                    proposed_effect_digest=pending.proposed_effect_digest,
                )
            )
            await reached_boundary.wait()
            requested = await supervisor.request_cancel(operation_id)
            assert requested.effect is OperationEffect.NONE
            release_boundary.set()
            for _ in range(100):
                stopped = await supervisor.inspect(operation_id)
                if stopped.cancellation_acknowledged_at is not None:
                    assert stopped.effect is OperationEffect.NONE
                    break
                await asyncio.sleep(0)
            else:
                raise AssertionError("censo executor did not acknowledge pre-entry cancellation")

        asyncio.run(run())
        assert ProfileRecordRepository.for_current_session(profile_id).load(profile_id) == before
        assert ProfileRecordStore(session=session).history() == history_before
