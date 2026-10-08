"""Actual key admission and installed workers with explicit native-store/login doubles."""

from __future__ import annotations

import asyncio
import sys
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.local_runtime.tests.profile_worker_support import owner_id
from cadrumo.adapters.persistence.storage.custody.automation_crypto import CustodyAutomationKeyIssuer
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import (
    PROFILE_INPUT,
    administration_subject,
    changed,
)
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.application.runtime.profile_access import RuntimeHumanProof
from cadrumo.application.runtime.profile_worker import ProfileWorkerIdentity
from cadrumo.application.user_profile.access_contracts import AccessDenied, AccessSession
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyError
from cadrumo.application.user_profile.session_authority import ProfileSessionAuthority
from cadrumo.application.user_profile.session_authority_contracts import SessionAuthorityFacts
from cadrumo.core.time.clock import now

from ..session_owner import ProfileWorkerSessionOwner

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]


def test_real_key_admission_refresh_and_human_lock_share_the_installed_worker(tmp_path: Path) -> None:
    # Only OS login observations and native credential storage are doubled.
    # The enrollment, protected files, verifier, unwrap, transport and worker are real.
    with administration_subject(tmp_path, os_owner_id=owner_id()) as enrollment:
        request_id = uuid4()
        enrollment.service.request(request_id, enrollment.proposal)
        enrollment.approve(request_id)
        record = enrollment.store.enrollment_state().requests[0]
        credential = enrollment.owner.delivery.endpoint.possession(record)
        assert credential is not None
        close_active_bucket_session()
        current = enrollment.owner.current
        identity = ProfileWorkerIdentity(
            worker_id=uuid4(),
            runtime_boot_id=current.context.runtime_boot_id,
            binding=current.profile.binding,
        )
        connection = current.context.connection_id
        human_connection = uuid4()
        clients = {connection: current.context.authenticated_client_id, human_connection: uuid4()}

        def observe(connected: UUID) -> SessionAuthorityFacts:
            return SessionAuthorityFacts(
                current.profile,
                changed(
                    current.context,
                    connection_id=connected,
                    authenticated_client_id=clients[connected],
                    now=now(),
                    monotonic_now=time.monotonic(),
                ),
            )

        @contextmanager
        def password(connected: UUID) -> Generator[RuntimeHumanProof]:
            assert connected == human_connection
            buffer = bytearray(PROFILE_INPUT.encode())
            try:
                yield RuntimeHumanProof(method="password", secret=buffer, originating_login_id="test-login")
            finally:
                buffer[:] = bytes(len(buffer))

        owner = ProfileWorkerSessionOwner(
            identity,
            storage_root=enrollment.store.root,
            observe=observe,
            human_secret=password,
            guard=enrollment.owner.guard,
        )
        authority = ProfileSessionAuthority(
            binding=identity.binding,
            runtime_boot_id=identity.runtime_boot_id,
            owner=owner,
            custody=enrollment.store,
            issuer=CustodyAutomationKeyIssuer(),
        )
        try:
            api = authority.admit_api_key(
                connection_id=connection,
                target=identity.binding,
                credential=credential,
                scope=current.profile.scope,
            )
            assert isinstance(api, AccessSession)
            human = authority.admit_human(connection_id=human_connection)
            assert isinstance(human, AccessSession)
            retired = authority.lock_session(
                connection_id=human_connection,
                session_id=human.session_id,
                target_session_id=human.session_id,
            )
            assert retired == (human.session_id,)
            assert isinstance(
                authority.refresh_api_key(connection_id=connection, session_id=api.session_id), AccessSession
            )
            assert isinstance(
                authority.refresh_api_key(connection_id=human_connection, session_id=api.session_id), AccessDenied
            )
            authority.disconnect(connection)
            assert isinstance(
                authority.refresh_api_key(connection_id=connection, session_id=api.session_id), AccessDenied
            )
            fresh = authority.admit_api_key(
                connection_id=connection,
                target=identity.binding,
                credential=credential,
                scope=current.profile.scope,
            )
            assert isinstance(fresh, AccessSession) and fresh.session_id != api.session_id
            owner.close()
            with pytest.raises(AutomationCustodyError):
                authority.refresh_api_key(connection_id=connection, session_id=fresh.session_id)
        finally:
            asyncio.run(authority.close())
            owner.close()
