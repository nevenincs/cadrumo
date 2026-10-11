"""A real in-process runtime over one registered profile, with a stored sign-in when asked for.

The profile, its password custody, the stored sign-in, the native transport,
the connection service and the profile worker are the real ones. The native
login the runtime observes, the keychain the proof is kept in and the runtime's
wall clock are explicit ports the test holds.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from importlib.metadata import version
from pathlib import Path
from threading import Event
from typing import override
from uuid import UUID, uuid4

import keyring
import pytest
from keyring.errors import KeyringError, PasswordDeleteError

from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.tests.profile_worker_support import owner_id
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.storage.custody import acceleration_receipt as receipt_custody
from cadrumo.adapters.persistence.storage.custody.acceleration_receipt import profile_session_path
from cadrumo.adapters.persistence.storage.custody.sign_in_generation import SignInGenerationCustody
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import (
    PROFILE_INPUT,
    AdministrationSubject,
    administration_subject,
)
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import profile_authority_contexts
from cadrumo.application.operations.mcp_surfaces import McpSurfaceName
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeByteChannel, RuntimeClientHello
from cadrumo.application.runtime.profile_access import (
    RuntimeAccessRefusal,
    RuntimeProfileLogin,
    RuntimeProfileStatus,
    RuntimeSessionRequest,
    RuntimeSessionsLocked,
)
from cadrumo.application.runtime.sign_in import (
    RuntimeHumanSignedOut,
    RuntimeSignInStatusReply,
    RuntimeSignInStatusRequest,
    SignInStatus,
)
from cadrumo.application.runtime.transport import RuntimeConnectionContext
from cadrumo.application.user_profile import login_session
from cadrumo.application.user_profile.access_contracts import AccessSession, ProfileAccessBinding
from cadrumo.application.user_profile.login_session import authenticate_profile_candidate, borrow_profile_receipt_key
from cadrumo.core.time.clock import now
from cadrumo.tests.in_memory_keyring import IN_MEMORY_KEYRING, InMemoryKeyring

from ....adapters.local_runtime.tests.retained_server import RetainedRuntimeTransportServer
from ..profile_connections import RuntimeProfileConnections
from .test_profile_connections import LoginObservation

type SessionReply = RuntimeProfileStatus | RuntimeSessionsLocked | RuntimeHumanSignedOut | RuntimeAccessRefusal


@dataclass
class RuntimeWallClock:
    """The runtime's wall clock port; moving it ahead takes the runtime past a deadline.

    Only the runtime process reads it. The profile worker, which checks a
    presented sign-in against its own record, keeps real time.
    """

    ahead: timedelta = field(default_factory=timedelta)

    def __call__(self) -> datetime:
        return now() + self.ahead


class RecordingProfileConnections(RuntimeProfileConnections):
    """The real connection service, keeping every login it was asked to admit."""

    logins: list[RuntimeProfileLogin]

    @override
    def handle(
        self,
        context: RuntimeConnectionContext,
        channel: RuntimeByteChannel,
        request: RuntimeProfileLogin | RuntimeSessionRequest | RuntimeSignInStatusRequest,
    ) -> (
        RuntimeProfileStatus
        | RuntimeSessionsLocked
        | RuntimeSignInStatusReply
        | RuntimeHumanSignedOut
        | RuntimeAccessRefusal
    ):
        if isinstance(request, RuntimeProfileLogin):
            self.logins.append(request)
        return super().handle(context, channel, request)


@dataclass
class StoredSignInRuntime:
    """The running runtime, its one profile and the ports the test holds."""

    root: Path
    endpoint: WindowsRuntimeEndpoint
    profiles: RecordingProfileConnections
    binding: ProfileAccessBinding
    native_login: LoginObservation
    clock: RuntimeWallClock
    enrollment: AdministrationSubject
    connections: list[VerifiedRuntimeConnection] = field(default_factory=list)

    @property
    def profile_id(self) -> UUID:
        return self.binding.profile_id

    def connect(self) -> VerifiedRuntimeConnection:
        """Open one verified connection; the runtime learns its frontend at login."""
        connection = VerifiedRuntimeConnection(
            self.endpoint.connect(timeout=3),
            expected=RuntimeClientHello(
                product_version=version("cadrumo"), storage_identity=self.endpoint.storage_identity
            ),
            deadline=time.monotonic() + 3,
        )
        self.connections.append(connection)
        return connection

    def login(
        self,
        connection: VerifiedRuntimeConnection,
        method: str,
        secret: bytearray,
        *,
        frontend: OperationFrontendProjection,
        persist_receipt: bool = False,
        surface: McpSurfaceName | None = None,
    ) -> RuntimeProfileStatus | RuntimeAccessRefusal:
        """Send one login exactly as written; the runtime decides."""
        document: dict[str, object] = {
            "request_id": uuid4(),
            "profile_id": self.profile_id,
            "method": method,
            "frontend": frontend,
            "persist_receipt": persist_receipt,
        }
        if surface is not None:
            document["surface"] = surface.value
        # The first login launches the profile worker, so it shares the cold admission budget.
        reply = connection.login(RuntimeProfileLogin.model_validate(document), secret, deadline=time.monotonic() + 75)
        assert secret == bytes(len(secret))
        return reply

    def resume(
        self,
        connection: VerifiedRuntimeConnection,
        frontend: OperationFrontendProjection,
        *,
        surface: McpSurfaceName | None = None,
    ) -> RuntimeProfileStatus | RuntimeAccessRefusal:
        """Present the stored sign-in's proof from this process's keychain."""
        with borrow_profile_receipt_key(bucket_id=self.profile_id) as proof:
            return self.login(connection, "receipt", proof, frontend=frontend, surface=surface)

    def session(
        self,
        connection: VerifiedRuntimeConnection,
        session_id: UUID,
        action: str,
        *,
        target_session_id: UUID | None = None,
    ) -> SessionReply:
        """Ask one session action of the runtime on the connection that holds the session."""
        document: dict[str, object] = {
            "action": action,
            "request_id": uuid4(),
            "profile_id": self.profile_id,
            "session_id": session_id,
        }
        if target_session_id is not None:
            document["target_session_id"] = target_session_id
        return connection.session(RuntimeSessionRequest.model_validate(document), deadline=time.monotonic() + 10)

    def sign_in(self, connection: VerifiedRuntimeConnection) -> SignInStatus:
        """Read the stored sign-in's presence and deadlines as the runtime reports them."""
        reply = connection.sign_in_status(
            RuntimeSignInStatusRequest(request_id=uuid4(), profile_id=self.profile_id), deadline=time.monotonic() + 5
        )
        assert isinstance(reply, RuntimeSignInStatusReply), reply
        return reply.status

    def store_sign_in(self, *, age: timedelta = timedelta()) -> None:
        """Store a new sign-in for the person, as the worker's publication step does after a password login.

        It runs in this process so that the proof lands in this process's
        keychain, and it binds the sign-in to the native login the runtime
        observes. With an ``age`` the person signed in that long ago: the
        sign-in carries the deadlines it would have had then.
        """
        _, decode = profile_authority_contexts()
        with pytest.MonkeyPatch.context() as patched:
            # The login session module stamps the sign-in with its clock.
            patched.setattr(login_session, "_now", lambda: self.clock() - age)
            with authenticate_profile_candidate(
                bucket_id=self.profile_id, passphrase_callback=lambda: PROFILE_INPUT, profile_decode_context=decode
            ) as candidate:
                assert candidate.persist_acceleration_receipt(
                    login_id=self.native_login.login_id,
                    binding=self.binding,
                    sign_in=SignInGenerationCustody(root=self.root, binding=self.binding).establish().current,
                )

    def stored_sign_in(self) -> bytes | None:
        """Return the stored sign-in's bytes, deadlines included, or ``None`` when none is stored."""
        path = profile_session_path(storage_root=self.root, profile_id=self.profile_id)
        return path.read_bytes() if path.exists() else None

    def lease(self, session_id: UUID) -> AccessSession:
        """Return the lease the runtime's authority holds for one admitted session."""
        return self.profiles._profiles[self.profile_id].authority._sessions[session_id]

    def leases(self) -> tuple[AccessSession, ...]:
        """Return every lease the runtime holds for the profile, if it hosts the profile at all."""
        host = self.profiles._profiles.get(self.profile_id)
        return () if host is None else tuple(host.authority._sessions.values())


@contextmanager
def stored_sign_in_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, signed_in: bool = True
) -> Iterator[StoredSignInRuntime]:
    """Serve one profile from a real runtime, with the person's sign-in stored when ``signed_in``."""
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    installation = runtime_installation(
        storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    prior_keyring = keyring.get_keyring()
    monkeypatch.setenv("PYTHON_KEYRING_BACKEND", IN_MEMORY_KEYRING)
    store = InMemoryKeyring()
    keyring.set_keyring(store)
    # The backend's priority was fixed when collection imported it, before the
    # selection above, so the sign-in writer's usability probe would refuse it.
    # Hand the writer the same selected store directly.
    monkeypatch.setattr(receipt_custody, "_keyring", lambda: (store, KeyringError, PasswordDeleteError))
    try:
        with administration_subject(
            tmp_path, os_owner_id=owner_id(), installation_id=installation.installation_id
        ) as enrollment:
            binding = enrollment.store.binding
            close_active_bucket_session()
            native_login = LoginObservation(owner_id())
            stop, boot, clock = Event(), uuid4(), RuntimeWallClock()
            profiles = RecordingProfileConnections(
                storage_root=root,
                storage_identity=endpoint.storage_identity,
                runtime_boot_id=boot,
                stop=stop,
                capture_login=lambda _channel: native_login,
                secret_store=lambda: enrollment.native,
                wall_clock=clock,
            )
            profiles.logins = []
            profiles.prepare_registry()
            server = RetainedRuntimeTransportServer(
                endpoint, product_version=version("cadrumo"), stop=stop, profiles=profiles, boot_id=boot
            )
            runtime = StoredSignInRuntime(root, endpoint, profiles, binding, native_login, clock, enrollment)
            if signed_in:
                runtime.store_sign_in()
            with ThreadPoolExecutor(max_workers=1) as pool:
                running = pool.submit(server.serve)
                try:
                    assert server.ready.wait(3)
                    yield runtime
                finally:
                    for connection in runtime.connections:
                        connection.close()
                    stop.set()
                    running.result(timeout=15)
                    endpoint.close()
    finally:
        keyring.set_keyring(prior_keyring)
