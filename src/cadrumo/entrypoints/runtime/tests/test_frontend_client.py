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

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.startup import RuntimeLaunchDoor
from cadrumo.adapters.local_runtime.tests.profile_worker_support import PROFILE_INPUT, owner_id, worker_profiles
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.storage.custody.tests.automation_support import MemoryNativePort
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeClientHello
from cadrumo.application.user_profile.access_contracts import (
    AccessDenialCode,
    Availability,
    LoginEligibility,
    OsLoginContext,
)
from cadrumo.application.user_profile.view_operation import ProfileViewOperationRequest, ProfileViewPageKind

from ....adapters.local_runtime.tests.retained_server import RetainedRuntimeTransportServer
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
            locked=False,
            unattended=LoginEligibility.ELIGIBLE,
            credential_facilities=credential_facilities,
        )


def test_verified_frontend_clients_collect_complete_profile_view_streams(tmp_path: Path) -> None:
    """CLI and TUI peers receive typed pages from a real encrypted worker."""
    with worker_profiles(tmp_path) as (root, targets):
        profile_id = targets[0][0].binding.profile_id
        foreign_id = targets[1][0].binding.profile_id
        endpoint = WindowsRuntimeEndpoint(storage_root=root)
        runtime_installation(storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity)
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
        launch = RuntimeLaunchDoor(
            endpoint,
            expected=RuntimeClientHello(product_version="test", storage_identity=endpoint.storage_identity),
        )
        with ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(server.serve)
            try:
                assert server.ready.wait(3)
                for frontend, streams in (
                    (OperationFrontendProjection.CLI, (ProfileViewPageKind.FACTS, ProfileViewPageKind.ISSUES)),
                    (OperationFrontendProjection.TUI, (ProfileViewPageKind.OVERVIEW,)),
                ):
                    client = asyncio.run(RuntimeFrontendClient.open(launch, profile_id=profile_id, frontend=frontend))
                    with client:
                        password = bytearray(PROFILE_INPUT.encode())
                        login = client.login_password(password)
                        assert password == bytes(len(password))
                        assert login.status.profile_id == profile_id
                        with pytest.raises(RuntimeFrontendRefusedError) as refresh_refusal:
                            client.refresh_api_key()
                        assert refresh_refusal.value.reason == AccessDenialCode.PARENT_INVALID.value
                        assert client.session_id == login.status.session_id
                        assert client.status().status.session_id == login.status.session_id
                        with pytest.raises(RuntimeFrontendRefusedError, match="profile_mismatch"):
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
                        client.lock()
            finally:
                stop.set()
                running.result(timeout=15)
                endpoint.close()
