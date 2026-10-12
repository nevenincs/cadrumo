"""One profile is signed in at a time: the person's sign-in to one profile signs every other one out.

Cadrumo is a GUI application with one active, signed-in profile. A sign-in to
profile B while profile A is signed in ends A's sign-in everywhere: every
human session of A on every frontend, an agent's session resumed from A's
sign-in included. Signing in to A again ends B's in turn.

The installed runtime server, its connection service, the profile workers and
both profiles' custody are real. The native login the runtime observes and the
native secret store are ports held by the test.
"""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

import pytest

from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.adapters.local_runtime.installation import read_runtime_installation
from cadrumo.adapters.local_runtime.tests.profile_worker_support import PROFILE_INPUT, owner_id
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.login_session import ProfileReceiptRefusedError

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
                with pytest.raises(RuntimeFrontendRefusedError):
                    ended.status()
            assert other.status().status.connected
            assert other.status().status.profile_id == second_id

            with _fresh_client(launch, first_id) as returning:
                returning.login_password(bytearray(PROFILE_INPUT.encode()))

                with pytest.raises(RuntimeFrontendRefusedError):
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
