"""Fresh-interpreter proof of a worker's password-successor custody boundary."""

from __future__ import annotations

import sys
import time
from datetime import timedelta
from pathlib import Path
from uuid import UUID, uuid4

from cadrumo.adapters.local_runtime.tests.profile_worker_support import PROFILE_INPUT, worker_profiles
from cadrumo.adapters.persistence.storage.custody.automation_profile import current_automation_profile_binding
from cadrumo.adapters.persistence.storage.master_key.active_session import current_active_bucket_session
from cadrumo.adapters.persistence.storage.master_key.profile_worker_custody import ProfileWorkerCustody
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import profile_authority_contexts
from cadrumo.application.auth.operation_definitions import PROFILE_ROTATION_OPERATION_DEFINITION_ID
from cadrumo.application.runtime.profile_worker import ProfileWorkerIdentity
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessScope,
    AccessSession,
    SessionKind,
    SessionState,
)
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from cadrumo.application.user_profile.passphrase_rotation import rotate_profile_passphrase
from cadrumo.core.config import override_settings
from cadrumo.core.time.clock import now
from cadrumo.entrypoints.adapter_composition import profile_adapter_composition

_SUCCESSOR = "synthetic-worker-password-successor"
_SECOND_SUCCESSOR = "synthetic-worker-password-second-successor"


def _lease(identity: ProfileWorkerIdentity) -> AccessSession:
    instant = now()
    return AccessSession(
        session_id=uuid4(),
        binding=identity.binding,
        profile_lock_generation=0,
        runtime_boot_id=identity.runtime_boot_id,
        connection_id=uuid4(),
        client_id=uuid4(),
        kind=SessionKind.HUMAN,
        originating_login_id="synthetic-live-owner-login",
        state=SessionState.ACTIVE,
        scope=AccessScope(
            operations=frozenset({PROFILE_ROTATION_OPERATION_DEFINITION_ID}),
            actions=frozenset(AccessAction),
            disclosures=frozenset(),
            periods=None,
            allow_period_independent=True,
            allow_delegation=False,
        ),
        issued_at=instant,
        issued_monotonic=time.monotonic(),
        expires_at=instant + timedelta(minutes=2),
    )


def _rotate(profile_id: UUID, root: Path, current: str, successor: str) -> int:
    _, decode = profile_authority_contexts()
    result = rotate_profile_passphrase(
        profile_id=profile_id,
        current_passphrase=current,
        new_passphrase=successor,
        new_passphrase_confirmation=successor,
        root=root,
        profile_decode_context=decode,
    )
    assert result.dek_epoch_preserved
    return result.password_generation


def _refuses(custody: ProfileWorkerCustody, generation: int, code: AutomationCustodyCode) -> None:
    try:
        custody.retire_password_successor(password_generation=generation)
    except AutomationCustodyError as exc:
        assert exc.reason is code
    else:
        raise AssertionError("custody accepted an invalid password successor")


def exercise(tmp_path: Path, mode: str) -> None:
    with profile_adapter_composition(), worker_profiles(tmp_path) as profiles:
        root, ((identity, key), _) = profiles
        with override_settings(
            cadrumo_local_storage_root=root, cadrumo_active_profile=str(identity.binding.profile_id)
        ):
            custody = ProfileWorkerCustody(identity, storage_root=root)
            lease = _lease(identity)
            custody.install(lease, bytearray(key))
            worker_identity = custody.identity
            original_session = current_active_bucket_session()
            assert original_session is not None and original_session.dek == key
            generation = identity.binding.custody_generation
            try:
                if mode == "success":
                    with custody.section(lease.session_id):
                        with custody.section(lease.session_id):
                            successor = _rotate(identity.binding.profile_id, root, PROFILE_INPUT, _SUCCESSOR)
                            assert successor == generation + 1
                            custody.expire()
                            assert current_active_bucket_session() is original_session
                            assert original_session.dek == key
                            try:
                                custody.require(lease.session_id)
                            except AutomationCustodyError as exc:
                                assert exc.reason is AutomationCustodyCode.INVALID
                            else:
                                raise AssertionError("old binding remained valid after committed rotation")
                            assert current_active_bucket_session() is original_session
                            assert not original_session.sealed
                            custody.retire_password_successor(password_generation=successor)
                            assert custody.identity is worker_identity
                            assert custody.live_sessions() == ()
                            assert current_active_bucket_session() is original_session
                            assert original_session.dek == key
                            try:
                                custody.require(lease.session_id)
                            except AutomationCustodyError as exc:
                                assert exc.reason is AutomationCustodyCode.CREDENTIAL_REJECTED
                            else:
                                raise AssertionError("retired lease remained usable")
                        assert current_active_bucket_session() is original_session
                        assert not original_session.sealed
                    assert original_session.sealed
                    assert current_active_bucket_session() is None
                    successor_binding = current_automation_profile_binding(
                        profile_id=identity.binding.profile_id,
                        installation_id=identity.binding.installation_id,
                        os_owner_id=identity.binding.os_owner_id,
                        root=root,
                    )
                    assert successor_binding.custody_generation == successor
                    assert successor_binding.dek_epoch == identity.binding.dek_epoch
                    successor_lease = lease.model_copy(update={"session_id": uuid4(), "binding": successor_binding})
                    for candidate in (lease, successor_lease):
                        try:
                            custody.install(candidate, bytearray(key))
                        except AutomationCustodyError as exc:
                            assert exc.reason is AutomationCustodyCode.CREDENTIAL_REJECTED
                        else:
                            raise AssertionError("old worker accepted a lease after rotation")
                elif mode == "uncommitted":
                    with custody.section(lease.session_id):
                        _refuses(custody, generation + 1, AutomationCustodyCode.INVALID)
                        assert custody.require(lease.session_id) == lease
                        assert original_session.dek == key
                    assert custody.require(lease.session_id) == lease
                elif mode == "outside":
                    _refuses(custody, generation + 1, AutomationCustodyCode.CONFLICT)
                    assert custody.require(lease.session_id) == lease
                elif mode == "jump":
                    try:
                        with custody.section(lease.session_id):
                            assert (
                                _rotate(identity.binding.profile_id, root, PROFILE_INPUT, _SUCCESSOR) == generation + 1
                            )
                            assert (
                                _rotate(identity.binding.profile_id, root, _SUCCESSOR, _SECOND_SUCCESSOR)
                                == generation + 2
                            )
                            _refuses(custody, generation + 2, AutomationCustodyCode.CONFLICT)
                            assert original_session.dek == key
                    except AutomationCustodyError as exc:
                        assert exc.reason is AutomationCustodyCode.INVALID
                    else:
                        raise AssertionError("stale section exited without binding validation")
                    assert original_session.sealed
                    assert current_active_bucket_session() is None
                    assert custody.live_sessions() == ()
                elif mode == "unretired":
                    try:
                        with custody.section(lease.session_id):
                            assert (
                                _rotate(identity.binding.profile_id, root, PROFILE_INPUT, _SUCCESSOR) == generation + 1
                            )
                            custody.expire()
                            assert original_session.dek == key
                    except AutomationCustodyError as exc:
                        assert exc.reason is AutomationCustodyCode.INVALID
                    else:
                        raise AssertionError("unretired changed binding passed section finalization")
                    assert original_session.sealed
                    assert current_active_bucket_session() is None
                    assert custody.live_sessions() == ()
                else:
                    raise AssertionError("unknown fixture mode")
            finally:
                custody.close()


if __name__ == "__main__":
    exercise(Path(sys.argv[1]), sys.argv[2])
