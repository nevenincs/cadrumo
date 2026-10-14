"""Native frontend client reads only complete registered profile-view streams."""

from __future__ import annotations

import asyncio
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from threading import Event
from uuid import uuid4

import pytest

from cadrumo.adapters.persistence.storage.custody.tests.automation_support import MemoryNativePort
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_contracts import (
    AccessDenialCode,
    Availability,
    LoginEligibility,
    OsLockState,
    OsLoginContext,
)
from cadrumo.application.user_profile.profile_operation_contracts import (
    PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID,
    ProfileFieldMutationOperationRequest,
)
from cadrumo.application.user_profile.view_operation import (
    PROFILE_VIEW_OPERATION_DEFINITION_ID,
    ProfileViewOperationRequest,
    ProfileViewPageKind,
)
from cadrumo.core.operations import profile_operation_subject
from cadrumo.core.storage_taxonomy import StorageCategory
from cadrumo.core.storage_taxonomy_locations import storage_location
from cadrumo.domain.user_profile.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH
from cadrumo_client.contracts.contracts import ClientHello
from cadrumo_client.contracts.operation_access import OperationSubmit, OperationSubmitted
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo_client.transport.installation import installation
from cadrumo_client.transport.startup import LaunchDoor
from cadrumo_client.transport.windows import WindowsEndpoint

from ...adapters.tests.profile_worker_support import PROFILE_INPUT, owner_id, worker_profiles
from ...adapters.tests.retained_server import RetainedRuntimeTransportServer
from ..profile_connections import RuntimeProfileConnections

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
    login_id: str = "frontend-view-native-login"

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        """Provide only test-owned native login facts; the channel remains native."""
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=self.owner,
            active=True,
            lock_state=OsLockState.UNLOCKED,
            unattended=LoginEligibility.ELIGIBLE,
            credential_facilities=credential_facilities,
        )


def test_verified_frontend_clients_collect_complete_profile_view_streams(tmp_path: Path) -> None:
    """CLI and TUI peers receive typed pages from a real encrypted worker."""
    with worker_profiles(tmp_path) as (root, targets):
        profile_id = targets[0][0].binding.profile_id
        foreign_id = targets[1][0].binding.profile_id
        endpoint = WindowsEndpoint(storage_root=root)
        installation(storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity)
        stop, boot, native = Event(), uuid4(), MemoryNativePort()
        profiles = RuntimeProfileConnections(
            storage_root=root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: LoginObservation(owner_id()),
            secret_store=lambda: native,
        )
        profiles.prepare_registry()
        server = RetainedRuntimeTransportServer(
            endpoint, product_version="test", stop=stop, profiles=profiles, boot_id=boot
        )
        launch = LaunchDoor(
            endpoint,
            expected=ClientHello(product_version="test", storage_identity=endpoint.storage_identity),
        )
        with ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(server.serve)
            try:
                assert server.ready.wait(3)
                recorded_id: str | None = None
                for frontend, streams in (
                    (OperationFrontendProjection.CLI, (ProfileViewPageKind.FACTS, ProfileViewPageKind.ISSUES)),
                    (OperationFrontendProjection.TUI, (ProfileViewPageKind.OVERVIEW,)),
                ):
                    client = asyncio.run(FrontendClient.open(launch, profile_id=profile_id, frontend=frontend))
                    with client:
                        password = bytearray(PROFILE_INPUT.encode())
                        login = client.login_password(password)
                        assert password == bytes(len(password))
                        assert login.status.profile_id == profile_id
                        with pytest.raises(FrontendRefusedError) as refresh_refusal:
                            client.refresh_api_key()
                        assert refresh_refusal.value.reason == AccessDenialCode.PARENT_INVALID.value
                        assert client.session_id == login.status.session_id
                        assert client.status().status.session_id == login.status.session_id
                        with pytest.raises(FrontendRefusedError, match="profile_mismatch"):
                            client.submit(
                                ProfileViewOperationRequest(profile_id=foreign_id, page_kind=streams[0]),
                                deadline=time.monotonic() + 5,
                            )
                        collection = client.read_profile_view(streams, timeout=90)
                        assert collection.profile_id == profile_id
                        assert tuple(dict.fromkeys(page.page_kind for page in collection.pages)) == streams
                        assert all(
                            (page.record_revision, page.content_digest)
                            == (collection.record_revision, collection.content_digest)
                            for page in collection.pages
                        )
                        for kind in streams:
                            pages = tuple(page for page in collection.pages if page.page_kind is kind)
                            assert pages and pages[0].cursor == 0 and pages[-1].next_cursor is None
                            assert tuple(item for page in pages for item in page.items) == collection.items(kind)
                            assert all(page.next_cursor == following.cursor for page, following in pairwise(pages))
                        if frontend is OperationFrontendProjection.TUI:
                            assert len(collection.items(ProfileViewPageKind.OVERVIEW)) > 0
                        else:
                            # Positive control: a recorded operation admitted in the same run is journaled.
                            recorded = client.operation(
                                OperationSubmit(
                                    request_id=uuid4(),
                                    profile_id=profile_id,
                                    session_id=client.session_id,
                                    definition_id=PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID,
                                    subject_ref=profile_operation_subject(str(profile_id)),
                                    payload_json=ProfileFieldMutationOperationRequest(
                                        profile_id=profile_id,
                                        expected_revision=collection.record_revision,
                                        expected_content_digest=collection.content_digest,
                                        path=PROFILE_OUTPUT_LANGUAGE_PATH,
                                        value="es",
                                    ).model_dump_json(),
                                ),
                                deadline=time.monotonic() + 30,
                            )
                            assert isinstance(recorded, OperationSubmitted)
                            recorded_id = recorded.receipt.operation_id
                        client.lock()
                # Every page read is ephemeral: none of them left a row in the profile's operation journal,
                # while the recorded operation from the same run did.
                journal = root / storage_location(StorageCategory.OPERATION_JOURNAL).subpath
                rows = {path.name: path.read_text("utf-8") for path in journal.glob("*.json")}
                assert recorded_id is not None and f"{recorded_id}.json" in rows
                assert PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID in rows[f"{recorded_id}.json"]
                assert not [name for name, text in rows.items() if PROFILE_VIEW_OPERATION_DEFINITION_ID in text]
            finally:
                stop.set()
                running.result(timeout=15)
                endpoint.close()
