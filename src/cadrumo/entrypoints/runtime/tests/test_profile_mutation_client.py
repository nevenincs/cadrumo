"""Native profile mutation runner preserves exact CAS and settled-result truth."""

from __future__ import annotations

import asyncio
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from uuid import uuid4

import pytest

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.profile_mutations import ProfileMutationRunError, run_profile_mutation
from cadrumo.adapters.local_runtime.startup import RuntimeLaunchDoor
from cadrumo.adapters.local_runtime.tests.profile_worker_support import PROFILE_INPUT, owner_id, worker_profiles
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.storage.custody.tests.automation_support import MemoryNativePort
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import profile_authority_contexts
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeClientHello
from cadrumo.application.user_profile.access_contracts import Availability, LoginEligibility, OsLoginContext
from cadrumo.application.user_profile.login_session import login_profile
from cadrumo.application.user_profile.profile_operation_contracts import (
    ProfileFieldMutationOperationRequest,
    ProfileMutationOperationProjection,
)
from cadrumo.application.user_profile.profile_record_repository import ProfileRecordRepository
from cadrumo.application.user_profile.view_operation import ProfileViewFactItem, ProfileViewPageKind
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition
from cadrumo.domain.user_profile.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH

from ....adapters.local_runtime.tests.retained_server import RetainedRuntimeTransportServer
from ..profile_connections import RuntimeProfileConnections

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]


class _LoginObservation:
    login_id = "profile-mutation-native-login"

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        """Supply only test-owned login facts; custody and writes remain real."""
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=owner_id(),
            active=True,
            locked=False,
            unattended=LoginEligibility.ELIGIBLE,
            credential_facilities=credential_facilities,
        )


def _baseline(profile_id: object) -> tuple[int, str]:
    _, decode = profile_authority_contexts()
    login_profile(
        name=str(profile_id),
        passphrase_callback=lambda: PROFILE_INPUT,
        profile_decode_context=decode,
    )
    try:
        record = ProfileRecordRepository.for_current_session(str(profile_id), profile_decode_context=decode).load(
            str(profile_id)
        )
        return record.record_revision, record.content_digest
    finally:
        close_active_bucket_session()


def test_tui_mutation_runner_projects_success_and_preserves_stale_conflict(tmp_path: Path) -> None:
    """A second intent pinned to the old encrypted revision cannot overwrite the first."""
    with worker_profiles(tmp_path) as (root, targets):
        profile_id = targets[0][0].binding.profile_id
        revision, digest = _baseline(profile_id)
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
        server = RetainedRuntimeTransportServer(
            endpoint, product_version="test", stop=stop, profiles=profiles, boot_id=boot
        )
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
                        ProfileFieldMutationOperationRequest(
                            profile_id=profile_id,
                            expected_revision=revision,
                            expected_content_digest=digest,
                            path=PROFILE_OUTPUT_LANGUAGE_PATH,
                            value="ca",
                        ),
                        timeout=60,
                    )
                    assert first.operation_id
                    assert first.effect is OperationEffect.UPDATED
                    assert type(first.projection) is ProfileMutationOperationProjection
                    assert first.projection.profile_id == profile_id and first.projection.record_revision > revision
                    with pytest.raises(ProfileMutationRunError) as failure:
                        run_profile_mutation(
                            client,
                            ProfileFieldMutationOperationRequest(
                                profile_id=profile_id,
                                expected_revision=revision,
                                expected_content_digest=digest,
                                path=PROFILE_OUTPUT_LANGUAGE_PATH,
                                value="hu",
                            ),
                            timeout=60,
                        )
                    assert failure.value.operation_id
                    assert failure.value.reason == "FAIL_PROFILE_RECORD_CONFLICT"
                    assert failure.value.terminal_condition is OperationTerminalCondition.FAILED
                    assert failure.value.effect is not OperationEffect.UPDATED
                    viewed = client.read_profile_view((ProfileViewPageKind.FACTS,), timeout=60)
                    facts = viewed.items(ProfileViewPageKind.FACTS)
                    assert viewed.record_revision == first.projection.record_revision
                    unchanged = run_profile_mutation(
                        client,
                        ProfileFieldMutationOperationRequest(
                            profile_id=profile_id,
                            expected_revision=viewed.record_revision,
                            expected_content_digest=viewed.content_digest,
                            path=PROFILE_OUTPUT_LANGUAGE_PATH,
                            value="ca",
                        ),
                        timeout=60,
                    )
                    assert unchanged.effect is OperationEffect.NONE
                    assert unchanged.projection.record_revision == viewed.record_revision
                    assert any(
                        isinstance(item, ProfileViewFactItem)
                        and item.path == PROFILE_OUTPUT_LANGUAGE_PATH
                        and item.value == "ca"
                        for item in facts
                    )
            finally:
                stop.set()
                running.result(timeout=15)
                endpoint.close()
