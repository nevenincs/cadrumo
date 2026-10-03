"""Native STATUS pages preserve exact canonical profile readiness judgments."""

from __future__ import annotations

import asyncio
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient, RuntimeFrontendRefusedError
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.server import RuntimeTransportServer
from cadrumo.adapters.local_runtime.startup import RuntimeLaunchDoor
from cadrumo.adapters.local_runtime.tests.profile_worker_support import PROFILE_INPUT, owner_id, worker_profiles
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.storage.custody.tests.automation_support import MemoryNativePort
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    bound_test_profile_record,
    load_test_profile_record,
    profile_authority_contexts,
    upsert_test_profile_facts,
)
from cadrumo.application.modelo.profile_readiness_gate import modelo_work_profile_baseline_missing_paths
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeClientHello
from cadrumo.application.user_profile.access_contracts import Availability, LoginEligibility, OsLoginContext
from cadrumo.application.user_profile.login_session import login_profile
from cadrumo.application.user_profile.projections import record_to_path_values
from cadrumo.application.user_profile.tests.profile_values import complete_profile_facts
from cadrumo.application.user_profile.view_operation import (
    ProfileViewOperationRequest,
    ProfileViewPageKind,
    ProfileViewPreconditionVerdict,
    ProfileViewStatusItem,
)
from cadrumo.application.workflow.profile_health import ProfileHealthStatus, assess_profile_record_health
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord

from ..profile_connections import RuntimeProfileConnections

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real native Windows profile workers"),
]

_STATUS_FACT_PATHS = frozenset({"identity.tax_id", "activities.description", "iva.regime", "tax_residence.ccaa"})


class _LoginObservation:
    login_id = "profile-status-native-login"

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        """Supply explicit synthetic OS-login facts, never a private profile answer."""
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=owner_id(),
            active=True,
            locked=False,
            unattended=LoginEligibility.ELIGIBLE,
            credential_facilities=credential_facilities,
        )


def _status(client: RuntimeFrontendClient, *, revision: int | None = None, digest: str | None = None):
    collection = client.read_profile_view(
        (ProfileViewPageKind.STATUS,),
        expected_revision=revision,
        expected_content_digest=digest,
        timeout=90,
    )
    items = collection.items(ProfileViewPageKind.STATUS)
    assert len(collection.pages) == len(items) == 1
    assert len(items) == 1 and isinstance(items[0], ProfileViewStatusItem)
    assert collection.pages[0].cursor == 0 and collection.pages[0].next_cursor is None
    assert collection.pages[0].total_items == 1
    assert collection.pages[0].record_revision == collection.record_revision
    assert collection.pages[0].content_digest == collection.content_digest
    return collection, items[0]


def _assert_canonical_status(
    status: ProfileViewStatusItem,
    *,
    profile_id: UUID,
    label: str,
    record: UserProfileRecord,
    operation: PinnedAuthorityOperation,
) -> None:
    canonical = assess_profile_record_health(record, source="env_override", label=label, operation=operation)
    assert status.display_name == label
    assert status.health.active_profile == str(profile_id)
    assert status.health.status is canonical.status
    assert status.health.missing_required == canonical.missing_required
    verdict = status.health.precondition_verdict
    if canonical.precondition_verdict is None:
        assert verdict is None
    else:
        assert isinstance(verdict, ProfileViewPreconditionVerdict)
        assert verdict.to_verdict() == canonical.precondition_verdict
    assert status.baseline_ready == (not modelo_work_profile_baseline_missing_paths(record))
    expected_facts = {
        path: str(value) for path, value in record_to_path_values(record).items() if path in _STATUS_FACT_PATHS
    }
    assert {item.path: item.value for item in status.facts} == expected_facts


def test_native_status_reports_incomplete_and_ready_profiles_with_exact_page_pins(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """STATUS is one typed page from each real encrypted worker and current record."""
    with worker_profiles(tmp_path) as (root, targets):
        incomplete_id = targets[0][0].binding.profile_id
        ready_id = targets[1][0].binding.profile_id
        _, decode = profile_authority_contexts()
        login_profile(name=str(incomplete_id), passphrase_callback=lambda: PROFILE_INPUT, profile_decode_context=decode)
        try:
            incomplete = load_test_profile_record(incomplete_id, root=root)
        finally:
            close_active_bucket_session()
        login_profile(name=str(ready_id), passphrase_callback=lambda: PROFILE_INPUT, profile_decode_context=decode)
        try:
            facts = complete_profile_facts(
                authority_operation.profile_schema(),
                facts=(UserProfileFact(path="activities.description", value="Spanish rental income"),),
            )
            populated = upsert_test_profile_facts(ready_id, facts, root=root)
            assert populated.setup_state is ProfileSetupState.INCOMPLETE
            with bound_test_profile_record(ready_id, root=root) as repository:
                ready = repository.complete_setup(
                    ready_id,
                    expected_revision=populated.record_revision,
                    expected_content_digest=populated.content_digest,
                )
        finally:
            close_active_bucket_session()
        assert ready.setup_state is ProfileSetupState.COMPLETE
        assert modelo_work_profile_baseline_missing_paths(ready) == ()

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
                for profile_id, label, expected_status, record in (
                    (incomplete_id, "Worker profile 0", ProfileHealthStatus.INCOMPLETE, incomplete),
                    (ready_id, "Worker profile 1", ProfileHealthStatus.READY, ready),
                ):
                    client = asyncio.run(
                        RuntimeFrontendClient.open(
                            launch, profile_id=profile_id, frontend=OperationFrontendProjection.CLI
                        )
                    )
                    with client:
                        password = bytearray(PROFILE_INPUT.encode())
                        client.login_password(password)
                        assert password == bytearray(len(password))
                        collection, status = _status(client)
                        assert collection.profile_id == profile_id
                        assert (collection.record_revision, collection.content_digest) == (
                            record.record_revision,
                            record.content_digest,
                        )
                        assert collection.setup_state is (
                            ProfileSetupState.INCOMPLETE
                            if expected_status is ProfileHealthStatus.INCOMPLETE
                            else ProfileSetupState.COMPLETE
                        )
                        assert status.health.status is expected_status
                        _assert_canonical_status(
                            status, profile_id=profile_id, label=label, record=record, operation=authority_operation
                        )
                        assert status.projection_valid is (expected_status is ProfileHealthStatus.READY)
                        again, repeated = _status(
                            client, revision=collection.record_revision, digest=collection.content_digest
                        )
                        assert repeated == status
                        assert (again.record_revision, again.content_digest) == (
                            collection.record_revision,
                            collection.content_digest,
                        )
                        with pytest.raises(RuntimeFrontendRefusedError, match="stale_revision"):
                            client.read_profile_view(
                                (ProfileViewPageKind.STATUS,),
                                expected_revision=collection.record_revision + 1,
                                expected_content_digest=collection.content_digest,
                                timeout=60,
                            )
                        foreign_id = ready_id if profile_id == incomplete_id else incomplete_id
                        with pytest.raises(RuntimeFrontendRefusedError, match="profile_mismatch"):
                            client.submit(
                                ProfileViewOperationRequest(
                                    profile_id=foreign_id, page_kind=ProfileViewPageKind.STATUS
                                ),
                                deadline=time.monotonic() + 5,
                            )
                        client.lock()
            finally:
                stop.set()
                running.result(timeout=15)
                endpoint.close()
