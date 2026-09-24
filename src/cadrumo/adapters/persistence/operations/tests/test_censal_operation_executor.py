"""Composed durable lifecycle proofs for the production censo executor."""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest

from cadrumo.adapters.outbound.aeat.browser.factory import default_browser_session_factory
from cadrumo.adapters.outbound.aeat.sede.censal_datos import fetch_censal_datos
from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from cadrumo.adapters.persistence.operations.secure_references import operation_secure_reference_repository
from cadrumo.adapters.persistence.storage.custody.capsule import load_committed_profile_password_material
from cadrumo.adapters.persistence.storage.custody.kdf_supervision import unlock_profile_custody
from cadrumo.adapters.persistence.storage.operator_scope import build_operator_scope_ports
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    profile_authority_contexts as _profile_contexts_for_test,
)
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.auth.tests.certificate_secret_fakes import InMemoryCertificateSecretBackendFactory
from cadrumo.application.operations.interactions import (
    OperationApplyResponse,
    OperationRejectResponse,
)
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationRegistry,
    operation_public_schema_reference,
)
from cadrumo.application.operations.supervisor import OperationSupervisor
from cadrumo.application.user_profile.capsule_record import ProfileRecordSession, ProfileRecordStore
from cadrumo.application.user_profile.censal_observation import (
    CensalObservation,
    CensalObservationAddress,
    CensalObservationIdentity,
)
from cadrumo.application.user_profile.censal_operation import (
    CENSAL_PHASE_SETTLEMENT,
    CENSAL_REVIEW_RESPONSE_SCHEMA_BINDING,
    CensalFieldIntent,
    CensalOperationExecutor,
    CensalOperationRequest,
    CensalProfileBaseline,
    CensalReviewedFieldIntent,
    CensalReviewedOperand,
    build_censal_operation_definition,
    build_censal_operation_registration,
)
from cadrumo.application.user_profile.cotejo_apply import apply_cotejo
from cadrumo.application.user_profile.custody_ports import profile_custody_secure_object_repository
from cadrumo.application.user_profile.profile_record_repository import (
    ProfileRecordRepository,
    bound_profile_record_session,
)
from cadrumo.application.user_profile.registration import register_profile_with_credentials
from cadrumo.core.config import override_settings
from cadrumo.core.operations import OperationEffect, OperationLifecycle, OperationTerminalCondition
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.governed_fact_scope import governed_facts_in_scope
from cadrumo.domain.user_profile.values import UserProfileFact
from cadrumo.tests.aeat_literal_fixtures import aeat_url

from .supervision_support import run_to_settlement

_OPERATOR_SCOPE_PORTS = build_operator_scope_ports()


pytestmark = [pytest.mark.integration, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

NOW = datetime(2026, 8, 24, 18, tzinfo=UTC)
_CREDENTIAL_INPUT = "censal-operation-executor-passphrase"
RESPONSE_TOKEN = "a" * 64


def _test_censal_operation_definition() -> OperationDefinition:
    return build_censal_operation_definition(
        certificate_secret_backend_factory=InMemoryCertificateSecretBackendFactory(),
        browser_session_factory=default_browser_session_factory,
        operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        censal_fetch_port=fetch_censal_datos,
    )


def _test_censal_operation_definition_id() -> str:
    return _test_censal_operation_definition().definition_id


@contextmanager
def subject(tmp_path: Path) -> Generator[tuple[str, SecureObjectRepository, ProfileRecordSession]]:
    _profile_create_context_for_test, _profile_decode_context_for_test = _profile_contexts_for_test()
    with isolated_profile_storage_root(tmp_path=tmp_path) as root:
        outcome = register_profile_with_credentials(
            label="Censal operation executor",
            passphrase=_CREDENTIAL_INPUT,
            facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
            profile_create_context=_profile_create_context_for_test,
            profile_decode_context=_profile_decode_context_for_test,
        )
        material = load_committed_profile_password_material(UUID(outcome.profile_id), root=root)
        unlocked = unlock_profile_custody(material.envelope, _CREDENTIAL_INPUT, sentinel=material.sentinel)
        session = ProfileRecordSession.from_envelope(
            envelope=material.envelope, dek=unlocked.dek, profile_decode_context=_profile_decode_context_for_test
        )
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
                assert isinstance(objects, SecureObjectRepository)
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
        captured_at=NOW,
        source_url=aeat_url("sede", "/censo/consulta"),
    )


def censal_request_payload(profile_id: str) -> CensalOperationRequest:
    _profile_create_context_for_test, _profile_decode_context_for_test = _profile_contexts_for_test()
    record = ProfileRecordRepository.for_current_session(
        profile_id, profile_decode_context=_profile_decode_context_for_test
    ).load(profile_id)
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


def _scoped_authority_operation() -> PinnedAuthorityOperation:
    """Return the session lease this module runs under; the executor reads it."""
    scoped = governed_facts_in_scope()
    assert isinstance(scoped, PinnedAuthorityOperation), "censal executor tests run under the authority lease"
    return scoped


def censal_supervisor(
    *,
    root: Path,
    objects: SecureObjectRepository,
    executor: CensalOperationExecutor,
    owner: str,
    token: str,
    now: datetime = NOW,
) -> OperationSupervisor:
    operands = operation_secure_reference_repository(objects=objects)
    definition = _test_censal_operation_definition().model_copy(
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
        authority_operation=_scoped_authority_operation(),
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
        response_token_factory=lambda: RESPONSE_TOKEN,
    )


async def wait_for_phase(supervisor: OperationSupervisor, operation_id: str, phase: str):
    # The continuation commits through real journal and custody I/O, so the
    # wait is bounded by time rather than by a count of scheduler turns.
    deadline = asyncio.get_running_loop().time() + 10
    while asyncio.get_running_loop().time() < deadline:
        snapshot = await supervisor.inspect(operation_id)
        if snapshot.phase_code == phase or snapshot.lifecycle is OperationLifecycle.TERMINAL:
            return snapshot
        await asyncio.sleep(0.01)
    raise AssertionError(f"operation did not reach {phase}")


async def start(supervisor: OperationSupervisor, operation_id: str):
    return await run_to_settlement(supervisor, operation_id)


def test_censal_executor_acquires_once_recovers_review_and_applies_exact_operand(tmp_path: Path) -> None:
    _profile_create_context_for_test, _profile_decode_context_for_test = _profile_contexts_for_test()
    acquisitions = 0

    async def acquire() -> CensalObservation:
        nonlocal acquisitions
        acquisitions += 1
        return _observation()

    with subject(tmp_path) as (profile_id, objects, _session):
        durable_root = tmp_path / "operations"
        executor = CensalOperationExecutor(
            certificate_secret_backend_factory=InMemoryCertificateSecretBackendFactory(),
            browser_session_factory=default_browser_session_factory,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            censal_fetch_port=fetch_censal_datos,
            acquire=acquire,
        )
        owner = censal_supervisor(
            root=durable_root,
            objects=objects,
            executor=executor,
            owner="1" * 64,
            token="2" * 64,
        )
        request = OperationRequest(
            definition_id=_test_censal_operation_definition_id(),
            subject_ref=profile_id,
            payload=censal_request_payload(profile_id),
        )
        assert "response_token" not in request.payload.model_dump()

        async def run() -> None:
            operation_id = await owner.submit(request, operation_id="3" * 64)
            waiting = await start(owner, operation_id)
            assert waiting.lifecycle is OperationLifecycle.WAITING_FOR_INTERACTION
            assert waiting.effect is OperationEffect.NONE
            pending = waiting.pending_interaction
            assert pending is not None
            assert pending.request.revision == waiting.revision
            assert pending.request.response_schema_ref == operation_public_schema_reference(
                CENSAL_REVIEW_RESPONSE_SCHEMA_BINDING.identity
            )
            assert acquisitions == 1

            recovery = censal_supervisor(
                root=durable_root,
                objects=objects,
                executor=executor,
                owner="4" * 64,
                token="5" * 64,
                now=NOW + timedelta(minutes=2),
            )
            recovered = await recovery.reconcile(operation_id)
            assert recovered.lifecycle is OperationLifecycle.WAITING_FOR_INTERACTION
            assert acquisitions == 1
            recovered_pending = recovered.pending_interaction
            assert recovered_pending is not None
            assert recovered_pending.baseline_digest is not None
            assert recovered_pending.proposed_effect_digest is not None

            await recovery.respond(
                OperationApplyResponse(
                    interaction_id=recovered_pending.request.interaction_id,
                    operation_id=operation_id,
                    revision=recovered_pending.request.revision,
                    response_token=RESPONSE_TOKEN,
                    continuation_digest=recovered_pending.request.continuation_digest,
                    reviewed_proposal_digest=recovered_pending.reviewed_proposal_digest,
                    actor_ref="operator:integration",
                    responded_at=NOW + timedelta(minutes=2),
                    baseline_digest=recovered_pending.baseline_digest,
                    proposed_effect_digest=recovered_pending.proposed_effect_digest,
                )
            )
            applied = await wait_for_phase(recovery, operation_id, CENSAL_PHASE_SETTLEMENT)
            assert applied.effect is OperationEffect.UPDATED
            assert acquisitions == 1

        asyncio.run(run())
        assert all(
            RESPONSE_TOKEN.encode() not in path.read_bytes() for path in durable_root.rglob("*") if path.is_file()
        )
        record = ProfileRecordRepository.for_current_session(
            profile_id, profile_decode_context=_profile_decode_context_for_test
        ).load(profile_id)
        assert record.record_revision == request.payload.baseline.record_revision + 1


def test_censal_executor_rejects_none_and_post_commit_failure_stays_unknown(tmp_path: Path) -> None:
    _profile_create_context_for_test, _profile_decode_context_for_test = _profile_contexts_for_test()

    async def acquire() -> CensalObservation:
        return _observation()

    with subject(tmp_path) as (profile_id, objects, session):
        durable_root = tmp_path / "operations"
        before = ProfileRecordRepository.for_current_session(
            profile_id, profile_decode_context=_profile_decode_context_for_test
        ).load(profile_id)

        async def reject_run() -> None:
            supervisor = censal_supervisor(
                root=durable_root,
                objects=objects,
                executor=CensalOperationExecutor(
                    certificate_secret_backend_factory=InMemoryCertificateSecretBackendFactory(),
                    browser_session_factory=default_browser_session_factory,
                    operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                    censal_fetch_port=fetch_censal_datos,
                    acquire=acquire,
                ),
                owner="6" * 64,
                token="7" * 64,
            )
            request = OperationRequest(
                definition_id=_test_censal_operation_definition_id(),
                subject_ref=profile_id,
                payload=censal_request_payload(profile_id),
            )
            operation_id = await supervisor.submit(request, operation_id="8" * 64)
            waiting = await start(supervisor, operation_id)
            pending = waiting.pending_interaction
            assert pending is not None
            await supervisor.respond(
                OperationRejectResponse(
                    interaction_id=pending.request.interaction_id,
                    operation_id=operation_id,
                    revision=pending.request.revision,
                    response_token=RESPONSE_TOKEN,
                    continuation_digest=pending.request.continuation_digest,
                    reviewed_proposal_digest=pending.reviewed_proposal_digest,
                    actor_ref="operator:integration",
                    responded_at=NOW,
                )
            )
            # Awaiting the terminal state, not the settlement phase: returning at
            # the phase tore the loop down while the rejection was still being
            # journalled, which left the outcome to scheduling.
            rejected = await supervisor.await_terminal(operation_id)
            assert rejected.phase_code == CENSAL_PHASE_SETTLEMENT
            assert rejected.terminal_condition is OperationTerminalCondition.SUCCEEDED
            assert rejected.effect is OperationEffect.NONE
            assert rejected.terminal_receipt is not None
            assert rejected.terminal_receipt.result_ref is not None
            assert rejected.terminal_receipt.result_ref.endswith(":rejected")

        asyncio.run(reject_run())
        assert (
            ProfileRecordRepository.for_current_session(
                profile_id, profile_decode_context=_profile_decode_context_for_test
            ).load(profile_id)
            == before
        )

        history_before_race = ProfileRecordStore(session=session).history()

        def competing_write_then_stale(operand: CensalReviewedOperand) -> None:
            apply_cotejo(
                None,
                adopted=(),
                divergences=(),
                profile_decode_context=_profile_decode_context_for_test,
            )
            apply_cotejo(
                None,
                reviewed_proposal=operand,
                profile_decode_context=_profile_decode_context_for_test,
            )

        async def stale_race_run() -> None:
            supervisor = censal_supervisor(
                root=tmp_path / "stale-race-operations",
                objects=objects,
                executor=CensalOperationExecutor(
                    certificate_secret_backend_factory=InMemoryCertificateSecretBackendFactory(),
                    browser_session_factory=default_browser_session_factory,
                    operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                    censal_fetch_port=fetch_censal_datos,
                    acquire=acquire,
                    apply=competing_write_then_stale,
                ),
                owner="d" * 64,
                token="e" * 64,
            )
            request = OperationRequest(
                definition_id=_test_censal_operation_definition_id(),
                subject_ref=profile_id,
                payload=censal_request_payload(profile_id),
            )
            operation_id = await supervisor.submit(request, operation_id="f" * 64)
            waiting = await start(supervisor, operation_id)
            pending = waiting.pending_interaction
            assert pending is not None
            await supervisor.respond(
                OperationApplyResponse(
                    interaction_id=pending.request.interaction_id,
                    operation_id=operation_id,
                    revision=pending.request.revision,
                    response_token=RESPONSE_TOKEN,
                    continuation_digest=pending.request.continuation_digest,
                    reviewed_proposal_digest=pending.reviewed_proposal_digest,
                    actor_ref="operator:integration",
                    responded_at=NOW,
                    baseline_digest=pending.baseline_digest,
                    proposed_effect_digest=pending.proposed_effect_digest,
                )
            )
            terminal = await supervisor.await_terminal(operation_id)
            assert terminal.terminal_condition is OperationTerminalCondition.FAILED
            assert terminal.effect is OperationEffect.NONE

        asyncio.run(stale_race_run())
        after_race = ProfileRecordRepository.for_current_session(
            profile_id, profile_decode_context=_profile_decode_context_for_test
        ).load(profile_id)
        history_after_race = ProfileRecordStore(session=session).history()
        assert after_race.record_revision == before.record_revision + 1
        assert len(history_after_race) == len(history_before_race) + 1

        def commit_then_fail(operand: CensalReviewedOperand) -> None:
            apply_cotejo(
                None,
                reviewed_proposal=operand,
                profile_decode_context=_profile_decode_context_for_test,
            )
            raise RuntimeError("synthetic repository acknowledgement loss")

        async def ambiguous_run() -> None:
            supervisor = censal_supervisor(
                root=tmp_path / "ambiguous-operations",
                objects=objects,
                executor=CensalOperationExecutor(
                    certificate_secret_backend_factory=InMemoryCertificateSecretBackendFactory(),
                    browser_session_factory=default_browser_session_factory,
                    operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                    censal_fetch_port=fetch_censal_datos,
                    acquire=acquire,
                    apply=commit_then_fail,
                ),
                owner="9" * 64,
                token="b" * 64,
            )
            request = OperationRequest(
                definition_id=_test_censal_operation_definition_id(),
                subject_ref=profile_id,
                payload=censal_request_payload(profile_id),
            )
            operation_id = await supervisor.submit(request, operation_id="c" * 64)
            waiting = await start(supervisor, operation_id)
            pending = waiting.pending_interaction
            assert pending is not None
            await supervisor.respond(
                OperationApplyResponse(
                    interaction_id=pending.request.interaction_id,
                    operation_id=operation_id,
                    revision=pending.request.revision,
                    response_token=RESPONSE_TOKEN,
                    continuation_digest=pending.request.continuation_digest,
                    reviewed_proposal_digest=pending.reviewed_proposal_digest,
                    actor_ref="operator:integration",
                    responded_at=NOW,
                    baseline_digest=pending.baseline_digest,
                    proposed_effect_digest=pending.proposed_effect_digest,
                )
            )
            terminal = await supervisor.await_terminal(operation_id)
            assert terminal.terminal_condition is OperationTerminalCondition.FAILED
            assert terminal.effect is OperationEffect.UNKNOWN

        asyncio.run(ambiguous_run())
        after = ProfileRecordRepository.for_current_session(
            profile_id, profile_decode_context=_profile_decode_context_for_test
        ).load(profile_id)
        assert after.record_revision == before.record_revision + 2


def test_censal_executor_cancellation_before_irreversible_entry_keeps_none_and_writes_nothing(
    tmp_path: Path,
) -> None:
    _profile_create_context_for_test, _profile_decode_context_for_test = _profile_contexts_for_test()
    reached_boundary = asyncio.Event()
    release_boundary = asyncio.Event()

    async def acquire() -> CensalObservation:
        return _observation()

    async def hold_before_entry() -> None:
        reached_boundary.set()
        await release_boundary.wait()

    with subject(tmp_path) as (profile_id, objects, session):
        before = ProfileRecordRepository.for_current_session(
            profile_id, profile_decode_context=_profile_decode_context_for_test
        ).load(profile_id)
        history_before = ProfileRecordStore(session=session).history()
        supervisor = censal_supervisor(
            root=tmp_path / "cancel-race-operations",
            objects=objects,
            executor=CensalOperationExecutor(
                certificate_secret_backend_factory=InMemoryCertificateSecretBackendFactory(),
                browser_session_factory=default_browser_session_factory,
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                censal_fetch_port=fetch_censal_datos,
                acquire=acquire,
                before_irreversible_section=hold_before_entry,
            ),
            owner="1" * 64,
            token="2" * 64,
        )
        request = OperationRequest(
            definition_id=_test_censal_operation_definition_id(),
            subject_ref=profile_id,
            payload=censal_request_payload(profile_id),
        )

        async def run() -> None:
            operation_id = await supervisor.submit(request, operation_id="3" * 64)
            waiting = await start(supervisor, operation_id)
            pending = waiting.pending_interaction
            assert pending is not None
            await supervisor.respond(
                OperationApplyResponse(
                    interaction_id=pending.request.interaction_id,
                    operation_id=operation_id,
                    revision=pending.request.revision,
                    response_token=RESPONSE_TOKEN,
                    continuation_digest=pending.request.continuation_digest,
                    reviewed_proposal_digest=pending.reviewed_proposal_digest,
                    actor_ref="operator:integration",
                    responded_at=NOW,
                    baseline_digest=pending.baseline_digest,
                    proposed_effect_digest=pending.proposed_effect_digest,
                )
            )
            await reached_boundary.wait()
            requested = await supervisor.request_cancel(operation_id)
            assert requested.effect is OperationEffect.NONE
            release_boundary.set()
            deadline = asyncio.get_running_loop().time() + 10
            while asyncio.get_running_loop().time() < deadline:
                stopped = await supervisor.inspect(operation_id)
                if stopped.cancellation_acknowledged_at is not None:
                    assert stopped.effect is OperationEffect.NONE
                    break
                await asyncio.sleep(0.01)
            else:
                raise AssertionError("censo executor did not acknowledge pre-entry cancellation")

        asyncio.run(run())
        assert (
            ProfileRecordRepository.for_current_session(
                profile_id, profile_decode_context=_profile_decode_context_for_test
            ).load(profile_id)
            == before
        )
        assert ProfileRecordStore(session=session).history() == history_before
