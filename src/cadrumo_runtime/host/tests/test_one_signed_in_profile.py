"""One profile is signed in at a time: the person's sign-in to one profile signs every other one out.

Cadrumo is a GUI application with one active, signed-in profile. A sign-in to
profile B while profile A is signed in ends A's sign-in everywhere: every
human session of A on every frontend, an automation's session resumed from A's
sign-in included. Signing in to A again ends B's in turn.

The installed runtime server, its connection service, the profile workers and
both profiles' custody are real. The native login the runtime observes and the
native secret store are ports held by the test.
"""

from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from contextvars import copy_context
from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

import pytest
from keyring.errors import KeyringError, PasswordDeleteError

from cadrumo.adapters.persistence.storage.custody import acceleration_receipt
from cadrumo.adapters.persistence.storage.custody.sign_in_generation import SignInGenerationCustody
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import profile_authority_contexts
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_contracts import AccessDenied, AccessSession
from cadrumo.application.user_profile.login_session import ProfileReceiptRefusedError, authenticate_profile_candidate
from cadrumo.tests.in_memory_keyring import InMemoryKeyring
from cadrumo_client.contracts.profile_access import ProfileLogin, ProfileStatus
from cadrumo_client.contracts.transport import ConnectionContext
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo_client.transport.installation import read_runtime_installation

from ...adapters.tests.profile_worker_support import PROFILE_INPUT, owner_id
from ..profile_connections import RuntimeProfileConnections
from ..profile_host import ProfileConnection, RuntimeProfileHost
from ..sign_in_sweep import revoke_other_saved_sign_ins
from .stored_sign_in_runtime import stored_sign_in_runtime
from .test_runtime_password_rotation import _fresh_client, _native_runtime

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]


def test_signing_in_to_another_profile_signs_the_first_out_everywhere_and_back_again(tmp_path: Path) -> None:
    with (
        _native_runtime(tmp_path) as (first_id, second_id, launch, _installation_id, _root),
        _fresh_client(launch, first_id) as person,
        _fresh_client(launch, first_id) as sibling,
    ):
        person.login_password(bytearray(PROFILE_INPUT.encode()))
        sibling.login_password(bytearray(PROFILE_INPUT.encode()))
        assert person.status().status.connected and sibling.status().status.connected

        with _fresh_client(launch, second_id) as other:
            other.login_password(bytearray(PROFILE_INPUT.encode()))

            # Every session of the first profile ended; the profile signed in to is the only one.
            for ended in (person, sibling):
                with pytest.raises(FrontendRefusedError):
                    ended.status()
            assert other.status().status.connected
            assert other.status().status.profile_id == second_id

            with _fresh_client(launch, first_id) as returning:
                returning.login_password(bytearray(PROFILE_INPUT.encode()))

                with pytest.raises(FrontendRefusedError):
                    other.status()
                assert returning.status().status.profile_id == first_id


def test_a_stored_sign_in_of_another_profile_is_revoked_and_the_one_kept_stays(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A profile no runtime host holds has no live session, so its stored sign-in alone is revoked."""
    with stored_sign_in_runtime(tmp_path, monkeypatch) as runtime:
        installation = read_runtime_installation(
            storage_root=runtime.root, os_owner_id=owner_id(), storage_identity=runtime.endpoint.storage_identity
        )
        stored = runtime.stored_sign_in()
        assert stored is not None

        kept = revoke_other_saved_sign_ins(root=runtime.root, installation=installation, keep=runtime.profile_id)
        assert kept == () and runtime.stored_sign_in() == stored

        hosted = revoke_other_saved_sign_ins(
            root=runtime.root,
            installation=installation,
            keep=uuid4(),
            hosted_profiles=frozenset({runtime.profile_id}),
        )
        assert hosted == () and runtime.stored_sign_in() == stored

        revoked = revoke_other_saved_sign_ins(root=runtime.root, installation=installation, keep=uuid4())
        assert revoked == (runtime.profile_id,)
        assert runtime.stored_sign_in() is None
        # The proof left the keychain with the receipt, so no frontend can present it to resume.
        with pytest.raises(ProfileReceiptRefusedError):
            runtime.resume(runtime.connect(), OperationFrontendProjection.CLI)


def test_a_delayed_resume_cannot_sign_out_a_newly_selected_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Finish A's receipt proof after B's handover, without letting A revoke B."""
    store = InMemoryKeyring()
    monkeypatch.setattr(acceleration_receipt, "_keyring", lambda: (store, KeyringError, PasswordDeleteError))
    entered, release = Event(), Event()
    owners: list[RuntimeProfileConnections] = []
    original = RuntimeProfileConnections._finish_login

    def finish(
        self: RuntimeProfileConnections,
        connection: ProfileConnection,
        host: RuntimeProfileHost,
        context: ConnectionContext,
        request: ProfileLogin,
        admitted: AccessSession | AccessDenied,
    ) -> ProfileStatus | AccessDenied:
        result = original(self, connection, host, context, request, admitted)
        if not owners:
            owners.append(self)
        if request.method == "receipt" and not release.is_set():
            entered.set()
            assert release.wait(90), "new profile handover did not complete"
        return result

    monkeypatch.setattr(RuntimeProfileConnections, "_finish_login", finish)
    with _native_runtime(tmp_path) as (first_id, second_id, launch, _installation_id, root):

        def store_receipt(profile_id: UUID) -> None:
            binding = owners[0]._profiles[profile_id].store.binding
            generation = SignInGenerationCustody(root=root, binding=binding).establish().current
            with authenticate_profile_candidate(
                bucket_id=profile_id,
                passphrase_callback=lambda: PROFILE_INPUT,
                profile_decode_context=profile_authority_contexts()[1],
            ) as candidate:
                assert candidate.persist_acceleration_receipt(
                    login_id="profile-rotation-native-login",
                    binding=binding,
                    sign_in=generation,
                )

        with (
            _fresh_client(launch, first_id) as person,
            _fresh_client(launch, first_id) as activity,
            _fresh_client(launch, second_id) as other,
        ):
            person.login_password(bytearray(PROFILE_INPUT.encode()))
            store_receipt(first_id)
            with ThreadPoolExecutor(max_workers=1) as pool:
                pending = pool.submit(copy_context().run, activity.resume_receipt)
                try:
                    if not entered.wait(30):
                        pending.result(timeout=1)
                        pytest.fail("old resume did not reach the publication boundary")
                    other.login_password(bytearray(PROFILE_INPUT.encode()))
                    store_receipt(second_id)
                    assert other.status().status.connected
                finally:
                    release.set()
                with suppress(ProfileReceiptRefusedError, FrontendRefusedError):
                    pending.result(timeout=30)
            with pytest.raises(FrontendRefusedError):
                activity.note_activity()
            assert other.status().status.connected
            # B's durable receipt also remains valid after the stale helper completes.
            with _fresh_client(launch, second_id) as returning:
                assert returning.resume_receipt().status.connected
            assert other.status().status.connected


def test_overlapping_password_handovers_do_not_revoke_each_other(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A second admission cannot sweep after the first handover retired it."""
    first_finished, second_admitted, release = Event(), Event(), Event()
    with _native_runtime(tmp_path) as (first_id, second_id, launch, _installation_id, _root):
        original_finish = RuntimeProfileConnections._finish_login
        original_admit = RuntimeProfileConnections._admit_human_login

        def finish(
            self: RuntimeProfileConnections,
            connection: ProfileConnection,
            host: RuntimeProfileHost,
            context: ConnectionContext,
            request: ProfileLogin,
            admitted: AccessSession | AccessDenied,
        ) -> ProfileStatus | AccessDenied:
            result = original_finish(self, connection, host, context, request, admitted)
            if request.profile_id == first_id:
                first_finished.set()
                assert release.wait(90), "overlapping second admission did not arrive"
            return result

        def admit(
            self: RuntimeProfileConnections,
            connection: ProfileConnection,
            host: RuntimeProfileHost,
            context: ConnectionContext,
            secret: bytearray,
        ) -> AccessSession | AccessDenied:
            result = original_admit(self, connection, host, context, secret)
            if host.store.binding.profile_id == second_id:
                assert isinstance(result, AccessSession)
                second_admitted.set()
            return result

        monkeypatch.setattr(RuntimeProfileConnections, "_finish_login", finish)
        monkeypatch.setattr(RuntimeProfileConnections, "_admit_human_login", admit)
        with (
            _fresh_client(launch, first_id) as first,
            _fresh_client(launch, second_id) as second,
            ThreadPoolExecutor(max_workers=2) as pool,
        ):
            first_result = pool.submit(first.login_password, bytearray(PROFILE_INPUT.encode()))
            try:
                assert first_finished.wait(30)
                second_result = pool.submit(second.login_password, bytearray(PROFILE_INPUT.encode()))
                assert second_admitted.wait(30)
            finally:
                release.set()
            assert first_result.result(timeout=30).status.connected
            with pytest.raises(FrontendRefusedError):
                second_result.result(timeout=30)
            assert first.status().status.connected
