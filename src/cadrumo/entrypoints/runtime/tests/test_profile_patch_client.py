"""Native atomic profile patch acceptance through the installed runtime."""

from __future__ import annotations

import asyncio
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.profile_mutations import ProfileMutationRunError, run_profile_mutation
from cadrumo.adapters.local_runtime.server import RuntimeTransportServer
from cadrumo.adapters.local_runtime.startup import RuntimeLaunchDoor
from cadrumo.adapters.local_runtime.tests.profile_worker_support import PROFILE_INPUT, owner_id, worker_profiles
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.storage.custody.tests.automation_support import MemoryNativePort
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import profile_authority_contexts
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeClientHello
from cadrumo.application.user_profile.access_contracts import Availability, LoginEligibility, OsLoginContext
from cadrumo.application.user_profile.capsule_record import ProfileRecordStore
from cadrumo.application.user_profile.login_session import login_profile
from cadrumo.application.user_profile.profile_operation_contracts import (
    ProfilePatchOperationProjection,
    ProfilePatchOperationRequest,
    ProfilePatchValue,
)
from cadrumo.application.user_profile.profile_record_repository import ProfileRecordRepository
from cadrumo.application.user_profile.view_operation import ProfileViewFactItem, ProfileViewPageKind
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition
from cadrumo.domain.buckets.event import BucketEventType
from cadrumo.domain.user_profile.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH
from cadrumo.domain.user_profile.values import UserProfileRecord

from ..profile_connections import RuntimeProfileConnections

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]


class _LoginObservation:
    login_id = "profile-patch-native-login"

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=owner_id(),
            active=True,
            locked=False,
            unattended=LoginEligibility.ELIGIBLE,
            credential_facilities=credential_facilities,
        )


def _snapshot(profile_id: UUID, *, root: Path) -> tuple[UserProfileRecord, int]:
    _, decode = profile_authority_contexts()
    login_profile(
        name=str(profile_id),
        passphrase_callback=lambda: PROFILE_INPUT,
        profile_decode_context=decode,
    )
    try:
        repository = ProfileRecordRepository.for_current_session(str(profile_id), profile_decode_context=decode)
        record = repository.load(str(profile_id))
        changed_events = sum(
            event.event_type is BucketEventType.PROFILE_VALUES_UPDATED
            for event in ProfileRecordStore(session=repository.session, root=root).history()
        )
        return record, changed_events
    finally:
        close_active_bucket_session()


def _patch(
    profile_id: UUID,
    *,
    revision: int,
    digest: str,
    values: tuple[tuple[str, str], ...],
) -> ProfilePatchOperationRequest:
    return ProfilePatchOperationRequest(
        profile_id=profile_id,
        expected_revision=revision,
        expected_content_digest=digest,
        values=tuple(ProfilePatchValue(question_id=question_id, value=value) for question_id, value in values),
    )


def _fact_values(client: RuntimeFrontendClient) -> tuple[int, str, dict[str, str]]:
    viewed = client.read_profile_view((ProfileViewPageKind.FACTS,), timeout=60)
    facts = {
        item.path: item.value
        for item in viewed.items(ProfileViewPageKind.FACTS)
        if isinstance(item, ProfileViewFactItem)
    }
    return viewed.record_revision, viewed.content_digest, facts


def test_native_patch_is_atomic_noop_and_exact_profile_bound(tmp_path: Path) -> None:
    """Two answers publish once; refusals and no-op cannot publish half a patch."""
    with worker_profiles(tmp_path) as (root, targets):
        profile_id = targets[0][0].binding.profile_id
        foreign_id = targets[1][0].binding.profile_id
        initial, initial_events = _snapshot(profile_id, root=root)
        foreign_initial, foreign_initial_events = _snapshot(foreign_id, root=root)
        endpoint = WindowsRuntimeEndpoint(storage_root=root)
        runtime_installation(storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity)
        stop, boot, native = Event(), uuid4(), MemoryNativePort()
        profiles = RuntimeProfileConnections(
            storage_root=root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: _LoginObservation(),
            secret_store=lambda: native,
        )
        profiles.prepare_registry()
        server = RuntimeTransportServer(endpoint, product_version="test", stop=stop, profiles=profiles, boot_id=boot)
        launch = RuntimeLaunchDoor(
            endpoint,
            expected=RuntimeClientHello(product_version="test", storage_identity=endpoint.storage_identity),
        )
        with ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(server.serve)
            try:
                assert server.ready.wait(3)
                client = asyncio.run(
                    RuntimeFrontendClient.open(launch, profile_id=profile_id, frontend=OperationFrontendProjection.TUI)
                )
                with client:
                    client.login_password(bytearray(PROFILE_INPUT.encode()))
                    first = run_profile_mutation(
                        client,
                        _patch(
                            profile_id,
                            revision=initial.record_revision,
                            digest=initial.content_digest,
                            values=(("output-language", "ca"), ("name", "Ada Example")),
                        ),
                        timeout=60,
                    )
                    assert first.effect is OperationEffect.UPDATED
                    assert type(first.projection) is ProfilePatchOperationProjection
                    assert first.projection.changed
                    assert first.projection.record_revision == initial.record_revision + 1
                    revision, digest, facts = _fact_values(client)
                    assert revision == first.projection.record_revision
                    assert facts[PROFILE_OUTPUT_LANGUAGE_PATH] == "ca"
                    assert facts["identity.name"] == "Ada Example"

                    same = run_profile_mutation(
                        client,
                        _patch(
                            profile_id,
                            revision=revision,
                            digest=digest,
                            values=(("output-language", "ca"), ("name", "Ada Example")),
                        ),
                        timeout=60,
                    )
                    assert same.effect is OperationEffect.NONE
                    assert type(same.projection) is ProfilePatchOperationProjection
                    assert not same.projection.changed
                    assert same.projection.record_revision == revision

                    with pytest.raises(ProfileMutationRunError) as invalid:
                        run_profile_mutation(
                            client,
                            _patch(
                                profile_id,
                                revision=revision,
                                digest=digest,
                                values=(("name", "Unpublished"), ("no-such-question", "bad")),
                            ),
                            timeout=60,
                        )
                    assert invalid.value.operation_id
                    assert invalid.value.terminal_condition is OperationTerminalCondition.REFUSED
                    assert invalid.value.effect is not OperationEffect.UPDATED
                    assert _fact_values(client) == (revision, digest, facts)

                    with pytest.raises(ProfileMutationRunError) as stale:
                        run_profile_mutation(
                            client,
                            _patch(
                                profile_id,
                                revision=initial.record_revision,
                                digest=initial.content_digest,
                                values=(("name", "Stale"),),
                            ),
                            timeout=60,
                        )
                    assert stale.value.reason == "FAIL_PROFILE_RECORD_CONFLICT"
                    assert _fact_values(client) == (revision, digest, facts)

                    with pytest.raises(RuntimeFrontendRefusedError):
                        run_profile_mutation(
                            client,
                            _patch(
                                foreign_id,
                                revision=revision,
                                digest=digest,
                                values=(("name", "Wrong profile"),),
                            ),
                            timeout=60,
                        )
                    assert _fact_values(client) == (revision, digest, facts)

                    cleared = run_profile_mutation(
                        client,
                        _patch(profile_id, revision=revision, digest=digest, values=(("name", ""),)),
                        timeout=60,
                    )
                    assert cleared.effect is OperationEffect.UPDATED
                    assert type(cleared.projection) is ProfilePatchOperationProjection
                    assert cleared.projection.changed
                    assert cleared.projection.record_revision == revision + 1
                    final_revision, _, final_facts = _fact_values(client)
                    assert final_revision == cleared.projection.record_revision
                    assert "identity.name" not in final_facts
                    assert final_facts[PROFILE_OUTPUT_LANGUAGE_PATH] == "ca"
            finally:
                stop.set()
                running.result(timeout=15)
                endpoint.close()

        final, final_events = _snapshot(profile_id, root=root)
        assert final.record_revision == initial.record_revision + 2
        assert final_events == initial_events + 2
        assert any(fact.path == PROFILE_OUTPUT_LANGUAGE_PATH and fact.value == "ca" for fact in final.facts)
        assert not any(fact.path == "identity.name" and fact.value is not None for fact in final.facts)
        foreign, foreign_events = _snapshot(foreign_id, root=root)
        assert foreign.record_revision == foreign_initial.record_revision
        assert foreign.content_digest == foreign_initial.content_digest
        assert foreign_events == foreign_initial_events
