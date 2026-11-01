"""Real local admission/worker flows with explicit native login and store fault ports."""

from __future__ import annotations

import asyncio
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import (
    PROFILE_INPUT,
    AdministrationSubject,
    administration_subject,
    changed,
)
from cadrumo.adapters.persistence.storage.custody.tests.native_enrollment_recipient import NativeEnrollmentRecipient
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import profile_authority_contexts
from cadrumo.application.operations.frontend_projection import OperationReviewProjectionReferenceV1
from cadrumo.application.operations.frontend_requests import (
    OPERATION_OBSERVATION_PROJECTION_ID,
    OperationCancellationRefusalV1,
    OperationCancellationRequestV1,
    OperationDetachRefusalV1,
    OperationDetachRequestV1,
    OperationDetachSuccessV1,
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResponseControlRequestV1,
    OperationResultProjectionRefusalV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
    OperationReviewProjectionRequestV1,
)
from cadrumo.application.operations.persistence.journal import OperationPersistedSnapshot
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_contracts import LoginEligibility, OsLockState, OsLoginContext
from cadrumo.application.user_profile.automation_lifecycle import AutomationDenial, AutomationDenialKind
from cadrumo.application.user_profile.login_session import authenticate_profile_for_invocation
from cadrumo.application.user_profile.profile_operation_contracts import (
    ProfileFieldMutationOperationRequest,
    ProfileMutationOperationProjection,
)
from cadrumo.application.user_profile.profile_record_repository import (
    ProfileRecordRepository,
    active_profile_record_session,
)
from cadrumo.application.user_profile.projections import record_to_path_values
from cadrumo.core.hashing import content_hash_hex
from cadrumo.core.operations import OperationTerminalCondition
from cadrumo.domain.user_profile.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH
from cadrumo.domain.user_profile.values import UserProfileRecord
from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.access_vocabulary import Availability, DisclosureCategory, DisclosurePermission
from cadrumo_client.contracts.operation_access import (
    OperationAcknowledged,
    OperationContract,
    OperationContractReply,
    OperationControl,
    OperationManage,
    OperationManaged,
    OperationObserve,
    OperationObserved,
    OperationProjected,
    OperationResult,
    OperationReview,
    OperationSubmit,
    OperationSubmitted,
)
from cadrumo_client.contracts.profile_access import (
    AccessRefusal,
    ProfileLogin,
    ProfileStatus,
    SessionRequest,
    SessionsLocked,
)
from cadrumo_client.contracts.sign_in import HumanSignedOut
from cadrumo_client.contracts.view_stream import ViewAttachRequest
from cadrumo_client.transport.frame_io import write_document
from cadrumo_client.transport.framing import VerifiedConnection
from cadrumo_client.transport.installation import installation
from cadrumo_client.transport.windows import WindowsEndpoint

from ...adapters.tests.profile_worker_support import owner_id
from ...adapters.tests.retained_server import RetainedRuntimeTransportServer
from ..profile_connections import RuntimeProfileConnections
from .operation_transport_support import PausedProjectionListener, ProjectionWriteBarrier
from .served_runtime import connect_verified

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]


@dataclass
class LoginObservation:
    owner: str
    login_id: str = "synthetic-native-login"
    active: bool = True
    lock_state: OsLockState = OsLockState.UNLOCKED
    unattended: LoginEligibility | None = None

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=self.owner,
            active=self.active,
            lock_state=self.lock_state,
            unattended=self.unattended or (LoginEligibility.ELIGIBLE if self.active else LoginEligibility.INELIGIBLE),
            credential_facilities=credential_facilities,
        )


def login(client: VerifiedConnection, profile: UUID, method: str, raw: bytes, *, seconds: float = 75):
    buffer = bytearray(raw)
    request = ProfileLogin.model_validate(
        {
            "request_id": uuid4(),
            "profile_id": profile,
            "method": method,
            "frontend": OperationFrontendProjection.TUI if method == "api_key" else OperationFrontendProjection.CLI,
        }
    )
    # Admission now completes the worker's one-time public registry graph
    # before releasing a usable session; the real frontend reserves 75s.
    result = client.login(request, buffer, deadline=time.monotonic() + seconds)
    assert buffer == bytes(len(raw))
    return result


def _session_status(
    client: VerifiedConnection, profile: UUID, session_id: UUID
) -> ProfileStatus | SessionsLocked | HumanSignedOut | AccessRefusal:
    return client.session(
        SessionRequest(action="session_status", request_id=uuid4(), profile_id=profile, session_id=session_id),
        deadline=time.monotonic() + 3,
    )


def _admit_and_describe(
    api: VerifiedConnection, human: VerifiedConnection, profile: UUID, secret: bytes
) -> tuple[UUID, UUID]:
    admitted = login(api, profile, "api_key", secret)
    assert isinstance(admitted, ProfileStatus), admitted
    assert admitted.status.denial is None
    api_id = admitted.status.session_id
    assert api_id is not None
    human_result = login(human, profile, "password", PROFILE_INPUT.encode())
    assert isinstance(human_result, ProfileStatus), human_result
    human_id = human_result.status.session_id
    assert human_id is not None
    for admitted_client, admitted_session in ((api, api_id), (human, human_id)):
        # Both lease installation and human binding finish the
        # worker graph before advertising the admitted session.
        described = admitted_client.operation(
            OperationContract(
                request_id=uuid4(),
                profile_id=profile,
                session_id=admitted_session,
                definition_id="user-profile.field-mutation",
            ),
            deadline=time.monotonic() + 5,
        )
        assert isinstance(described, OperationContractReply), described
        assert content_hash_hex(described.request_json_schema) == described.contract.request_schema.schema_fingerprint
    return api_id, human_id


def _refuse_foreign_and_relock(
    api: VerifiedConnection, other: VerifiedConnection, profile: UUID, secret: bytes, api_id: UUID
) -> UUID:
    stolen = _session_status(other, profile, api_id)
    assert isinstance(stolen, AccessRefusal)
    wrong = login(api, uuid4(), "api_key", secret)
    assert isinstance(wrong, AccessRefusal)
    refreshed = api.session(
        SessionRequest(action="session_refresh", request_id=uuid4(), profile_id=profile, session_id=api_id),
        deadline=time.monotonic() + 3,
    )
    assert isinstance(refreshed, ProfileStatus) and refreshed.status.denial is None
    assert refreshed.status.provider is Availability.NOT_REQUIRED
    assert refreshed.status.published_authority is Availability.NOT_REQUIRED
    locked = api.session(
        SessionRequest(action="session_lock", request_id=uuid4(), profile_id=profile, session_id=api_id),
        deadline=time.monotonic() + 3,
    )
    assert isinstance(locked, SessionsLocked) and locked.session_ids == (api_id,)
    fresh = login(api, profile, "api_key", secret)
    assert isinstance(fresh, ProfileStatus) and fresh.status.session_id != api_id
    assert fresh.status.session_id is not None
    return fresh.status.session_id


def _lose_worker_and_rebind(
    profiles: RuntimeProfileConnections,
    api: VerifiedConnection,
    human: VerifiedConnection,
    profile: UUID,
    secret: bytes,
    api_id: UUID,
    human_id: UUID,
) -> None:
    # Abruptly lose the actual test-owned worker job, leaving both
    # frontend channels connected. Each lease waits, granting nothing,
    # for its own connection to present its proof again.
    host = profiles._profiles[profile]
    lost_worker = host.owner._worker
    assert lost_worker is not None
    lost_worker.close()
    suspended = {api_id, human_id}
    deadline = time.monotonic() + 3
    while not suspended <= host.authority._suspended.keys() and time.monotonic() < deadline:
        profiles.poll()
        time.sleep(0.02)
    assert suspended <= host.authority._suspended.keys()
    assert profiles._profiles[profile] is host and host.owner._worker is not lost_worker
    rebound = login(api, profile, "api_key", secret)
    assert isinstance(rebound, ProfileStatus) and rebound.status.session_id == api_id
    resumed_human = login(human, profile, "password", PROFILE_INPUT.encode())
    assert isinstance(resumed_human, ProfileStatus) and resumed_human.status.session_id == human_id


def _lose_native_dependency(
    enrollment: AdministrationSubject,
    native_login: LoginObservation,
    api: VerifiedConnection,
    human: VerifiedConnection,
    other: VerifiedConnection,
    profile: UUID,
    api_id: UUID,
    human_id: UUID,
) -> None:
    enrollment.native.unavailable = True
    api_lost = _session_status(api, profile, api_id)
    assert isinstance(api_lost, AccessRefusal)
    still_human = _session_status(human, profile, human_id)
    assert isinstance(still_human, ProfileStatus) and still_human.status.denial is None
    independent = login(other, profile, "password", PROFILE_INPUT.encode())
    assert isinstance(independent, ProfileStatus) and independent.status.denial is None
    native_login.lock_state = OsLockState.LOCKED
    retired = _session_status(human, profile, human_id)
    assert isinstance(retired, AccessRefusal) or (
        isinstance(retired, ProfileStatus) and retired.status.denial is not None
    )


def test_real_connection_admission_lock_reconnect_and_native_dependency_loss(tmp_path: Path) -> None:
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsEndpoint(storage_root=root)
    installation_state = installation(
        storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation_state.installation_id
    ) as enrollment:
        request_id = uuid4()
        enrollment.service.request(request_id, enrollment.proposal)
        enrollment.approve(request_id)
        record = enrollment.store.enrollment_state().requests[0]
        secret = enrollment.owner.delivery.endpoint.possession(record)
        assert secret is not None
        profile = enrollment.store.binding.profile_id
        close_active_bucket_session()
        stop, boot, native_login = Event(), uuid4(), LoginObservation(owner_id())
        profiles = RuntimeProfileConnections(
            storage_root=root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: native_login,
            secret_store=lambda: enrollment.native,
        )
        profiles.prepare_registry()
        server = RetainedRuntimeTransportServer(
            endpoint, product_version="test", stop=stop, profiles=profiles, boot_id=boot
        )
        clients: list[VerifiedConnection] = []
        with ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(server.serve)
            try:
                assert server.ready.wait(3)
                api, human, other = (connect_verified(endpoint) for _ in range(3))
                clients.extend((api, human, other))
                proof = secret.get_secret_value()
                api_id, human_id = _admit_and_describe(api, human, profile, proof)
                fresh_id = _refuse_foreign_and_relock(api, other, profile, proof, api_id)
                _lose_worker_and_rebind(profiles, api, human, profile, proof, fresh_id, human_id)
                _lose_native_dependency(enrollment, native_login, api, human, other, profile, fresh_id, human_id)
            finally:
                for client in clients:
                    client.close()
                stop.set()
                running.result(timeout=12)
                endpoint.close()


@dataclass(frozen=True)
class _EffectRig:
    client: VerifiedConnection
    profile: UUID
    secret: bytes
    root: Path
    endpoint: WindowsEndpoint
    profiles: RuntimeProfileConnections
    barrier: ProjectionWriteBarrier
    pool: ThreadPoolExecutor
    clients: list[VerifiedConnection]
    allow_observation: bool


@dataclass(frozen=True)
class _SubmittedEffect:
    session_id: UUID
    contract: OperationContractReply
    submission: OperationSubmit
    submitted: OperationSubmitted


def _grant_observation_disclosures(enrollment: AdministrationSubject) -> None:
    requester = changed(enrollment.owner.requesting, destination_id=enrollment.owner.requesting.client_id)
    enrollment.owner.requesting = requester
    enrollment.owner.delivery.endpoint = NativeEnrollmentRecipient(
        requester=requester, secrets_store=enrollment.client_native
    )
    permissions = frozenset(
        (
            DisclosurePermission(
                destination_id=enrollment.owner.requesting.client_id,
                projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                category=DisclosureCategory.OPERATION_METADATA,
            ),
            DisclosurePermission(
                destination_id=enrollment.owner.requesting.client_id,
                projection_id="user-profile.field-mutation.result",
                category=DisclosureCategory.PROFILE_VALUES,
            ),
        )
    )
    scope = changed(enrollment.proposal.scope, disclosures=permissions)
    facts = enrollment.owner.current
    assert facts.session is not None
    enrollment.owner.current = changed(
        facts, profile=changed(facts.profile, scope=scope), session=changed(facts.session, scope=scope)
    )
    enrollment.proposal = changed(enrollment.proposal, scope=scope)


def _submit_language_mutation(rig: _EffectRig, baseline: UserProfileRecord) -> _SubmittedEffect:
    client, profile = rig.client, rig.profile
    refused = client.operation(
        OperationControl(
            action="operation_start",
            request_id=uuid4(),
            profile_id=profile,
            session_id=uuid4(),
            operation_id="0" * 64,
        ),
        deadline=time.monotonic() + 5,
    )
    assert isinstance(refused, AccessRefusal)
    admitted = login(client, profile, "api_key", rig.secret)
    assert isinstance(admitted, ProfileStatus) and admitted.status.session_id is not None
    session_id = admitted.status.session_id
    contract = client.operation(
        OperationContract(
            request_id=uuid4(),
            profile_id=profile,
            session_id=session_id,
            definition_id="user-profile.field-mutation",
        ),
        deadline=time.monotonic() + 5,
    )
    assert isinstance(contract, OperationContractReply)
    assert content_hash_hex(contract.request_json_schema) == contract.contract.request_schema.schema_fingerprint
    request_properties = contract.request_json_schema.get("properties")
    assert isinstance(request_properties, dict)
    assert {
        "profile_id",
        "expected_revision",
        "expected_content_digest",
        "path",
        "value",
    } <= request_properties.keys()
    submission = OperationSubmit(
        request_id=uuid4(),
        profile_id=profile,
        session_id=session_id,
        definition_id="user-profile.field-mutation",
        subject_ref=f"profile:{profile}",
        payload_json=ProfileFieldMutationOperationRequest(
            profile_id=profile,
            expected_revision=baseline.record_revision,
            expected_content_digest=baseline.content_digest,
            path=PROFILE_OUTPUT_LANGUAGE_PATH,
            value="es",
        ).model_dump_json(),
        idempotency_key="autonomous-language-request",
    )
    submitted = client.operation(submission, deadline=time.monotonic() + 10)
    assert isinstance(submitted, OperationSubmitted), submitted
    return _SubmittedEffect(session_id, contract, submission, submitted)


def _relock_and_replay(rig: _EffectRig, effect: _SubmittedEffect) -> UUID:
    client, profile = rig.client, rig.profile
    locked = client.session(
        SessionRequest(action="session_lock", request_id=uuid4(), profile_id=profile, session_id=effect.session_id),
        deadline=time.monotonic() + 5,
    )
    assert isinstance(locked, SessionsLocked)
    admitted = login(client, profile, "api_key", rig.secret)
    assert isinstance(admitted, ProfileStatus) and admitted.status.session_id is not None
    assert admitted.status.session_id != effect.session_id
    session_id = admitted.status.session_id
    replayed = client.operation(
        changed(effect.submission, request_id=uuid4(), session_id=session_id), deadline=time.monotonic() + 10
    )
    assert isinstance(replayed, OperationSubmitted) and replayed.receipt == effect.submitted.receipt
    return session_id


def _resume_and_settle(
    rig: _EffectRig, effect: _SubmittedEffect, session_id: UUID
) -> tuple[OperationObserve, OperationPersistedSnapshot, OperationJournalRepository]:
    client, profile = rig.client, rig.profile
    resumed = client.operation(
        OperationControl(
            action="operation_resume",
            request_id=uuid4(),
            profile_id=profile,
            session_id=session_id,
            operation_id=effect.submitted.receipt.operation_id,
        ),
        deadline=time.monotonic() + 10,
    )
    assert isinstance(resumed, OperationAcknowledged), resumed
    request = OperationObserve(
        request_id=uuid4(),
        profile_id=profile,
        session_id=session_id,
        observation=OperationObservationRequestV1(
            operation_id=effect.submitted.receipt.operation_id, after_cursor=0, page_limit=32
        ),
    )
    journal = OperationJournalRepository(storage_root=rig.root)
    while True:
        observation = client.operation(changed(request, request_id=uuid4()), deadline=time.monotonic() + 8)
        if rig.allow_observation:
            assert isinstance(observation, OperationObserved), observation
            assert isinstance(observation.observation, OperationObservationSuccessV1)
        else:
            assert isinstance(observation, AccessRefusal), observation
            assert observation.code is AccessDenialCode.DISCLOSURE_DENIED
        snapshot = asyncio.run(journal.load(effect.submitted.receipt.operation_id))
        if snapshot.terminal_condition is not None:
            break
        time.sleep(0.02)
    assert snapshot.terminal_condition is OperationTerminalCondition.SUCCEEDED
    return request, snapshot, journal


def _manage_settled_operation(
    rig: _EffectRig,
    effect: _SubmittedEffect,
    session_id: UUID,
    snapshot: OperationPersistedSnapshot,
    journal: OperationJournalRepository,
) -> None:
    client, operation_id = rig.client, effect.submitted.receipt.operation_id
    control = OperationManage(
        request_id=uuid4(),
        profile_id=rig.profile,
        session_id=session_id,
        management=OperationDetachRequestV1(operation_id=operation_id, expected_revision=snapshot.revision),
    )
    detached = client.operation(control, deadline=time.monotonic() + 5)
    if rig.allow_observation:
        assert isinstance(detached, OperationManaged), detached
        detached_receipt = OperationDetachSuccessV1.model_validate_json(json.dumps(detached.document))
        assert detached_receipt.operation_id == operation_id
        assert detached_receipt.revision == snapshot.revision
        stale = client.operation(
            changed(
                control,
                request_id=uuid4(),
                management=OperationDetachRequestV1(operation_id=operation_id, expected_revision=snapshot.revision - 1),
            ),
            deadline=time.monotonic() + 5,
        )
        assert isinstance(stale, OperationManaged)
        assert OperationDetachRefusalV1.model_validate_json(json.dumps(stale.document)).outcome == "refused"
    else:
        assert isinstance(detached, AccessRefusal), detached
        assert detached.code is AccessDenialCode.DISCLOSURE_DENIED
    cancelled = client.operation(
        changed(
            control,
            request_id=uuid4(),
            management=OperationCancellationRequestV1(operation_id=operation_id, expected_revision=snapshot.revision),
        ),
        deadline=time.monotonic() + 5,
    )
    if rig.allow_observation:
        assert isinstance(cancelled, OperationManaged), cancelled
        assert OperationCancellationRefusalV1.model_validate_json(json.dumps(cancelled.document)).outcome == "refused"
    else:
        assert isinstance(cancelled, AccessRefusal)
        assert cancelled.code is AccessDenialCode.DISCLOSURE_DENIED
    response = client.operation(
        changed(
            control,
            request_id=uuid4(),
            management=OperationResponseControlRequestV1(
                operation_id=operation_id,
                interaction_id="a" * 64,
                revision=snapshot.revision,
                actor_ref=f"session:{session_id}",
            ),
        ),
        deadline=time.monotonic() + 5,
    )
    assert isinstance(response, AccessRefusal)
    assert response.code is AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED
    # Control acknowledgements/refusals do not rewrite settled effects.
    assert asyncio.run(journal.load(operation_id)) == snapshot


def _project_result(
    rig: _EffectRig, effect: _SubmittedEffect, session_id: UUID, snapshot: OperationPersistedSnapshot
) -> int | None:
    client = rig.client
    result_schema = effect.contract.contract.result_schema
    assert result_schema is not None
    result_request = OperationResult(
        request_id=uuid4(),
        profile_id=rig.profile,
        session_id=session_id,
        result=OperationResultProjectionRequestV1(
            operation_id=effect.submitted.receipt.operation_id,
            terminal_revision=snapshot.revision,
            definition_contract_digest=effect.contract.contract.definition_contract_digest,
            result_schema=result_schema,
        ),
    )
    projected = client.operation(result_request, deadline=time.monotonic() + 5)
    if not rig.allow_observation:
        assert isinstance(projected, AccessRefusal), projected
        assert projected.code is AccessDenialCode.DISCLOSURE_DENIED
        return None
    assert isinstance(projected, OperationProjected), projected
    typed_result = OperationResultProjectionSuccessV1[ProfileMutationOperationProjection].model_validate_json(
        json.dumps(projected.document)
    )
    assert typed_result.projection.profile_id == rig.profile
    wrong = client.operation(
        changed(
            result_request,
            request_id=uuid4(),
            result=changed(result_request.result, result_schema=effect.contract.contract.request_schema),
        ),
        deadline=time.monotonic() + 5,
    )
    assert isinstance(wrong, OperationProjected)
    refused_result = OperationResultProjectionRefusalV1.model_validate_json(json.dumps(wrong.document))
    assert refused_result.outcome == "refused"
    return typed_result.projection.record_revision


def _refuse_unsupported_review(
    rig: _EffectRig, effect: _SubmittedEffect, session_id: UUID, snapshot: OperationPersistedSnapshot
) -> None:
    result_schema = effect.contract.contract.result_schema
    assert result_schema is not None
    unsupported_review = rig.client.operation(
        OperationReview(
            request_id=uuid4(),
            profile_id=rig.profile,
            session_id=session_id,
            review=OperationReviewProjectionRequestV1(
                reference=OperationReviewProjectionReferenceV1(
                    operation_id=effect.submitted.receipt.operation_id,
                    interaction_id="a" * 64,
                    revision=snapshot.revision,
                    review_projection_schema=result_schema,
                    definition_contract_digest=effect.contract.contract.definition_contract_digest,
                    expires_at=None,
                )
            ),
        ),
        deadline=time.monotonic() + 5,
    )
    assert isinstance(unsupported_review, AccessRefusal)
    assert unsupported_review.code is AccessDenialCode.OPERATION_DENIED


def _fence_projection_write(rig: _EffectRig, session_id: UUID, request: OperationObserve) -> OperationObserve:
    client, profile, pool, barrier = rig.client, rig.profile, rig.pool, rig.barrier
    host = rig.profiles._profiles[profile]
    human = connect_verified(rig.endpoint)
    rig.clients.append(human)
    human_login = login(human, profile, "password", PROFILE_INPUT.encode())
    assert isinstance(human_login, ProfileStatus) and human_login.status.session_id is not None
    barrier.enabled.set()
    releasing = pool.submit(client.operation, changed(request, request_id=uuid4()), deadline=time.monotonic() + 5)
    assert barrier.entered.wait(3)
    acquired = host.guard.acquire(blocking=False)
    if acquired:
        host.guard.release()
    assert not acquired, "the final native projection write released its authority fence"
    locking = pool.submit(
        human.session,
        SessionRequest(
            action="session_lock",
            request_id=uuid4(),
            profile_id=profile,
            session_id=human_login.status.session_id,
            target_session_id=session_id,
        ),
        deadline=time.monotonic() + 5,
    )
    assert not locking.done()
    barrier.release.set()
    assert isinstance(releasing.result(timeout=5), OperationObserved)
    locked = locking.result(timeout=5)
    assert isinstance(locked, SessionsLocked) and session_id in locked.session_ids
    assert isinstance(
        client.operation(changed(request, request_id=uuid4()), deadline=time.monotonic() + 5),
        AccessRefusal,
    )
    admitted = login(client, profile, "api_key", rig.secret)
    assert isinstance(admitted, ProfileStatus) and admitted.status.session_id is not None
    return changed(request, request_id=uuid4(), session_id=admitted.status.session_id)


def _deny_grant_and_refuse(rig: _EffectRig, request: OperationObserve) -> None:
    host = rig.profiles._profiles[rig.profile]
    grant = host.store.snapshot().grants[0]
    denial = AutomationDenial(
        request_id=uuid4(),
        binding=host.store.binding,
        kind=AutomationDenialKind.GRANT,
        target_id=grant.grant_id,
    )
    with host.guard:
        host.authority.invalidate_automation(denial)
        assert host.store.deny(denial).access_denied
    assert isinstance(
        rig.client.operation(changed(request, request_id=uuid4()), deadline=time.monotonic() + 5),
        AccessRefusal,
    )
    assert isinstance(login(rig.client, rig.profile, "api_key", rig.secret), AccessRefusal)


def _assert_language_persisted(profile: UUID, projected_revision: int | None, *, allow_observation: bool) -> None:
    _, decode = profile_authority_contexts()
    authenticate_profile_for_invocation(
        name=str(profile), passphrase_callback=lambda: PROFILE_INPUT, profile_decode_context=decode
    )
    try:
        persisted = ProfileRecordRepository.for_current_session(profile, profile_decode_context=decode).load(profile)
        assert record_to_path_values(persisted)[PROFILE_OUTPUT_LANGUAGE_PATH] == "es"
        if allow_observation:
            assert persisted.record_revision == projected_revision
    finally:
        close_active_bucket_session()


@pytest.mark.parametrize("allow_observation", [False, True])
def test_api_authority_reaches_real_effects_and_guards_public_output(tmp_path: Path, allow_observation: bool) -> None:
    """Only native login/store facilities are doubled; grant-to-effect admission is real."""
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsEndpoint(storage_root=root)
    installation_state = installation(
        storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation_state.installation_id
    ) as enrollment:
        if allow_observation:
            _grant_observation_disclosures(enrollment)
        enrollment_request = uuid4()
        enrollment.service.request(enrollment_request, enrollment.proposal)
        enrollment.approve(enrollment_request)
        record = enrollment.store.enrollment_state().requests[0]
        secret = enrollment.owner.delivery.endpoint.possession(record)
        assert secret is not None
        profile = enrollment.store.binding.profile_id
        record_session = active_profile_record_session()
        assert record_session is not None
        baseline = ProfileRecordRepository.for_current_session(
            profile, profile_decode_context=record_session.profile_decode_context
        ).load(profile)
        close_active_bucket_session()
        stop, boot, native_login = Event(), uuid4(), LoginObservation(owner_id())
        profiles = RuntimeProfileConnections(
            storage_root=root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: native_login,
            secret_store=lambda: enrollment.native,
        )
        barrier = ProjectionWriteBarrier()
        projected_revision = None
        server = RetainedRuntimeTransportServer(
            PausedProjectionListener(endpoint, barrier),
            product_version="test",
            stop=stop,
            profiles=profiles,
            boot_id=boot,
        )
        with ThreadPoolExecutor(max_workers=3) as pool:
            running = pool.submit(server.serve)
            clients: list[VerifiedConnection] = []
            try:
                assert server.ready.wait(3)
                client = connect_verified(endpoint)
                clients.append(client)
                rig = _EffectRig(
                    client,
                    profile,
                    secret.get_secret_value(),
                    root,
                    endpoint,
                    profiles,
                    barrier,
                    pool,
                    clients,
                    allow_observation,
                )
                effect = _submit_language_mutation(rig, baseline)
                session_id = _relock_and_replay(rig, effect)
                request, snapshot, journal = _resume_and_settle(rig, effect, session_id)
                _manage_settled_operation(rig, effect, session_id, snapshot, journal)
                projected_revision = _project_result(rig, effect, session_id, snapshot)
                _refuse_unsupported_review(rig, effect, session_id, snapshot)
                if allow_observation:
                    request = _fence_projection_write(rig, session_id, request)
                _deny_grant_and_refuse(rig, request)
            finally:
                barrier.release.set()
                for client in clients:
                    client.close()
                stop.set()
                running.result(timeout=12)
                endpoint.close()
        _assert_language_persisted(profile, projected_revision, allow_observation=allow_observation)


def test_fresh_native_host_reconciles_exact_surviving_denial_before_api_admission(tmp_path: Path) -> None:
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsEndpoint(storage_root=root)
    installation_state = installation(
        storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation_state.installation_id
    ) as enrollment:
        request_id = uuid4()
        enrollment.service.request(request_id, enrollment.proposal)
        enrollment.approve(request_id)
        request = enrollment.store.enrollment_state().requests[0]
        secret = enrollment.owner.delivery.endpoint.possession(request)
        assert secret is not None
        before_revision = enrollment.store.enrollment_state().revision
        profile = enrollment.store.binding.profile_id
        change = AutomationDenial(request_id=uuid4(), binding=enrollment.store.binding, kind=AutomationDenialKind.ALL)
        enrollment.native.unavailable = True
        assert enrollment.store.deny(change).cleanup_pending
        enrollment.native.unavailable = False
        close_active_bucket_session()
        stop, boot, native_login = Event(), uuid4(), LoginObservation(owner_id())
        profiles = RuntimeProfileConnections(
            storage_root=root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: native_login,
            secret_store=lambda: enrollment.native,
        )
        profiles.prepare_registry()
        server = RetainedRuntimeTransportServer(
            endpoint, product_version="test", stop=stop, profiles=profiles, boot_id=boot
        )
        clients: list[VerifiedConnection] = []
        with ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(server.serve)
            try:
                assert server.ready.wait(3)
                api = connect_verified(endpoint)
                clients.append(api)
                denied = login(api, profile, "api_key", secret.get_secret_value())
                assert isinstance(denied, AccessRefusal)
                host = profiles._profiles[profile]
                # The actual host recovery retained the original request and
                # advanced protected state instead of merely clearing a marker.
                state = host.store.enrollment_state()
                assert state.revision > before_revision
                completed = host.store.deny(change)
                assert completed.request_id == change.request_id
                assert completed.revision == state.revision
                assert completed.access_denied and not completed.cleanup_pending
                assert host.store.reconcile_denial() is None
            finally:
                for client in clients:
                    client.close()
                stop.set()
                running.result(timeout=12)
                endpoint.close()


def test_uncertain_native_status_recovers_on_same_connection_but_logout_does_not(tmp_path: Path) -> None:
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsEndpoint(storage_root=root)
    installed = installation(storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity)
    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installed.installation_id
    ) as enrollment:
        profile = enrollment.store.binding.profile_id
        close_active_bucket_session()
        stop, boot, native_login = Event(), uuid4(), LoginObservation(owner_id())
        profiles = RuntimeProfileConnections(
            storage_root=root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: native_login,
            secret_store=lambda: enrollment.native,
        )
        profiles.prepare_registry()
        server = RetainedRuntimeTransportServer(
            endpoint, product_version="test", stop=stop, profiles=profiles, boot_id=boot
        )
        clients: list[VerifiedConnection] = []
        with ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(server.serve)
            try:
                assert server.ready.wait(3)
                client = connect_verified(endpoint)
                clients.append(client)
                admitted = login(client, profile, "password", PROFILE_INPUT.encode())
                assert isinstance(admitted, ProfileStatus) and admitted.status.session_id is not None
                session_id = admitted.status.session_id
                native_login.lock_state = OsLockState.UNKNOWN
                native_login.unattended = LoginEligibility.UNKNOWN
                uncertain = client.session(
                    SessionRequest(
                        action="session_status", request_id=uuid4(), profile_id=profile, session_id=session_id
                    ),
                    deadline=time.monotonic() + 5,
                )
                assert isinstance(uncertain, ProfileStatus)
                assert uncertain.status.denial is AccessDenialCode.OS_SESSION_UNAVAILABLE
                connection = profiles._connections[uncertain.connection_id]
                assert connection.frontend is OperationFrontendProjection.CLI

                def attach_refusal() -> AccessRefusal:
                    request = ViewAttachRequest(
                        request_id=uuid4(),
                        profile_id=profile,
                        session_id=session_id,
                        operation_id=content_hash_hex({"view": "synthetic"}),
                    )
                    deadline = time.monotonic() + 5
                    with client._exchange(deadline=deadline):
                        write_document(client._channel, request, deadline=deadline)
                        reply = client._reply(request.request_id, deadline=deadline).root
                    assert isinstance(reply, AccessRefusal)
                    return reply

                # Frontend refusal precedes the uncertain session status. Once
                # the trusted host binding is desktop, that status still stops
                # the request before any view worker leg is opened.
                assert attach_refusal().code is AccessDenialCode.FRONTEND_DENIED
                connection.frontend = OperationFrontendProjection.DESKTOP
                try:
                    assert attach_refusal().code is AccessDenialCode.OS_SESSION_UNAVAILABLE
                finally:
                    connection.frontend = OperationFrontendProjection.CLI
                native_login.lock_state = OsLockState.UNLOCKED
                native_login.unattended = LoginEligibility.ELIGIBLE
                recovered = client.session(
                    SessionRequest(
                        action="session_status", request_id=uuid4(), profile_id=profile, session_id=session_id
                    ),
                    deadline=time.monotonic() + 5,
                )
                assert isinstance(recovered, ProfileStatus)
                assert recovered.status.denial is None
                assert recovered.status.session_id == session_id
                assert recovered.status.credential_authenticated
                signed_out = client.session(
                    SessionRequest(
                        action="human_sign_out", request_id=uuid4(), profile_id=profile, session_id=session_id
                    ),
                    deadline=time.monotonic() + 12,
                )
                assert isinstance(signed_out, HumanSignedOut)
                after_logout = client.session(
                    SessionRequest(
                        action="session_status", request_id=uuid4(), profile_id=profile, session_id=session_id
                    ),
                    deadline=time.monotonic() + 5,
                )
                assert isinstance(after_logout, AccessRefusal)
                assert after_logout.code is AccessDenialCode.CONNECTION_MISMATCH
            finally:
                for client in clients:
                    client.close()
                stop.set()
                running.result(timeout=12)
                endpoint.close()
