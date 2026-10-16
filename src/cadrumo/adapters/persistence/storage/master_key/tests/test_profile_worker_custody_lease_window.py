"""The worker's key session stays usable for exactly as long as a lease admits work.

Worker custody admits each request against its own lease and shares one key
session between every lease of the profile. Storage refuses once that session's
idle deadline passes, so the deadline has to follow the leases: sooner than a
live lease, and an admitted request is refused by storage; later than the last
lease, and key material outlives every authority to use it.

Lease admission and storage freshness read the wall clock separately. Custody
is therefore left on its production clock and every step runs inside one frozen
instant, so both readers observe the same controlled time; only the monotonic
half of a lease lifetime is injected. Storage is read through the real
secure-object repository, whose freshness check is the reader that refuses.
"""

from __future__ import annotations

import base64
import sys
from collections.abc import Callable, Generator
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    AccessScope,
    AccessSession,
    ProfileAccessBinding,
    SessionKind,
    SessionState,
)
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.core.config import override_settings
from cadrumo.core.time.clock import frozen_clock, now
from cadrumo.tests.audited_process import run_audited_process
from cadrumo_client.contracts.worker_identity import ProfileWorkerIdentity

from ...bucket.errors import BucketLockedError
from ...custody.capsule import load_committed_profile_password_material
from ...errors import SessionExpiredError
from ...profile_persistence_composition import composed_profile_persistence_ports
from ...runtime_repository import secure_object_repository_for_active_bucket
from ...tests.profile_capsule_runtime import derive_test_bucket_key, publish_test_profile_capsule
from ...tests.secure_sql import isolated_profile_storage_root
from .. import profile_worker_custody
from ..active_session import current_active_bucket_session, get_active_master_key
from ..bucket_session import BucketSession
from ..profile_worker_custody import ProfileWorkerCustody

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

_MODULE = "cadrumo.adapters.persistence.storage.master_key.tests.test_profile_worker_custody_lease_window"


class _Clock:
    """One controlled timeline for the wall clock and the lease's monotonic clock."""

    def __init__(self, start: datetime) -> None:
        self._start = start
        self._elapsed = timedelta()

    def monotonic(self) -> float:
        return self._elapsed.total_seconds()

    @contextmanager
    def at(self, *, minutes: float) -> Generator[None]:
        self._elapsed = timedelta(minutes=minutes)
        with frozen_clock(self._start + self._elapsed):
            yield


def _lease(identity: ProfileWorkerIdentity, clock: _Clock, kind: SessionKind, *, minutes: int) -> AccessSession:
    human = kind is SessionKind.HUMAN
    issued = now()
    return AccessSession(
        session_id=uuid4(),
        binding=identity.binding,
        runtime_boot_id=identity.runtime_boot_id,
        profile_lock_generation=0,
        connection_id=uuid4(),
        client_id=uuid4(),
        kind=kind,
        originating_login_id="synthetic-os-login" if human else None,
        state=SessionState.ACTIVE,
        scope=AccessScope(
            operations=frozenset(),
            actions=frozenset(AccessAction),
            disclosures=frozenset(),
            periods=None,
            allow_period_independent=True,
            allow_delegation=False,
        ),
        grant_id=None if human else uuid4(),
        grant_generation=None if human else 1,
        key_id=None if human else uuid4(),
        key_generation=None if human else 1,
        issued_at=issued,
        issued_monotonic=clock.monotonic(),
        expires_at=issued + timedelta(minutes=minutes),
    )


def _reissued(lease: AccessSession, clock: _Clock, *, minutes: int) -> AccessSession:
    issued = now()
    return AccessSession.model_validate(
        {
            **{name: getattr(lease, name) for name in AccessSession.model_fields},
            "issued_at": issued,
            "issued_monotonic": clock.monotonic(),
            "expires_at": issued + timedelta(minutes=minutes),
        }
    )


def _assert_expired(custody: ProfileWorkerCustody, session_id: UUID) -> None:
    with pytest.raises(ProfileAccessRefusedError) as expired:
        custody.require(session_id)
    assert expired.value.reason is AccessDenialCode.SESSION_EXPIRED


def _assert_retired(custody: ProfileWorkerCustody, session_id: UUID) -> None:
    with pytest.raises(ProfileAccessRefusedError) as retired:
        custody.require(session_id)
    assert retired.value.reason is AccessDenialCode.AUTHENTICATION_REQUIRED


def _child(parent: AccessSession, clock: _Clock, *, minutes: int) -> AccessSession:
    issued = now()
    return AccessSession.model_validate(
        {
            **{name: getattr(parent, name) for name in AccessSession.model_fields},
            "session_id": uuid4(),
            "connection_id": uuid4(),
            "kind": SessionKind.ATTENDED,
            "parent_session_id": parent.session_id,
            "issued_at": issued,
            "issued_monotonic": clock.monotonic(),
            "expires_at": issued + timedelta(minutes=minutes),
        }
    )


def _key_session() -> BucketSession:
    session = current_active_bucket_session()
    assert session is not None
    return session


def _read_storage() -> None:
    secure_object_repository_for_active_bucket().list_namespaces()


def _sign_in_lease(custody: ProfileWorkerCustody, clock: _Clock, key: bytes) -> None:
    with clock.at(minutes=0):
        human = _lease(custody.identity, clock, SessionKind.HUMAN, minutes=15)
        custody.install(human, bytearray(key))
        session = _key_session()
        assert session.idle_deadline == session.absolute_deadline == human.expires_at
    with clock.at(minutes=1):
        repository = secure_object_repository_for_active_bucket()
        repository.list_namespaces()
        # The read slid the idle deadline; it must still end with the lease.
        assert session.idle_deadline == human.expires_at
    with clock.at(minutes=9):
        assert custody.require(human.session_id) == human
        _read_storage()
        assert _key_session() is session
    with clock.at(minutes=14.5):
        assert custody.require(human.session_id) == human
        repository.list_namespaces()
        assert session.idle_deadline == human.expires_at
    with clock.at(minutes=15):
        with pytest.raises(SessionExpiredError):
            repository.list_namespaces()
        _assert_expired(custody, human.session_id)
        assert custody.live_sessions() == ()
        assert current_active_bucket_session() is None
        assert session.sealed


def _api_key_lease(custody: ProfileWorkerCustody, clock: _Clock, key: bytes) -> None:
    with clock.at(minutes=0):
        first = _lease(custody.identity, clock, SessionKind.API_KEY, minutes=5)
        custody.install(first, bytearray(key))
        opened = _key_session()
        assert opened.idle_deadline == opened.absolute_deadline == first.expires_at
    with clock.at(minutes=3):
        _read_storage()
        assert opened.idle_deadline == first.expires_at
    with clock.at(minutes=4):
        refreshed = _reissued(first, clock, minutes=5)
        custody.refresh(refreshed)
        session = _key_session()
        assert session is not opened and opened.sealed
        assert session.idle_deadline == session.absolute_deadline == refreshed.expires_at
    with clock.at(minutes=8):
        assert custody.require(refreshed.session_id) == refreshed
        repository = secure_object_repository_for_active_bucket()
        repository.list_namespaces()
        assert session.idle_deadline == refreshed.expires_at
    with clock.at(minutes=9):
        with pytest.raises(SessionExpiredError):
            repository.list_namespaces()
        _assert_expired(custody, refreshed.session_id)
        assert current_active_bucket_session() is None


def _mixed_leases(custody: ProfileWorkerCustody, clock: _Clock, key: bytes) -> None:
    with clock.at(minutes=0):
        api_key = _lease(custody.identity, clock, SessionKind.API_KEY, minutes=5)
        custody.install(api_key, bytearray(key))
        assert _key_session().absolute_deadline == api_key.expires_at
    with clock.at(minutes=1):
        human = _lease(custody.identity, clock, SessionKind.HUMAN, minutes=15)
        custody.install(human, bytearray(key))
        shared = _key_session()
        assert shared.idle_deadline == shared.absolute_deadline == human.expires_at
    with clock.at(minutes=2):
        _read_storage()
        # A read under either lease keeps the session open for the longer one.
        assert shared.idle_deadline == human.expires_at
    with clock.at(minutes=3):
        custody.retire(human.session_id)
        # A retired lease did not run out: it needs a fresh sign-in, and is never refused as expired.
        _assert_retired(custody, human.session_id)
        assert custody.require(api_key.session_id) == api_key
        remaining = _key_session()
        assert remaining is not shared and shared.sealed
        assert remaining.idle_deadline == remaining.absolute_deadline == api_key.expires_at
    with clock.at(minutes=4):
        repository = secure_object_repository_for_active_bucket()
        repository.list_namespaces()
        assert remaining.idle_deadline == api_key.expires_at
    with clock.at(minutes=5):
        with pytest.raises(SessionExpiredError):
            repository.list_namespaces()
        assert custody.live_sessions() == ()
        assert current_active_bucket_session() is None


def _latest_lease_expiry(custody: ProfileWorkerCustody, clock: _Clock, key: bytes) -> None:
    with clock.at(minutes=0):
        api_key = _lease(custody.identity, clock, SessionKind.API_KEY, minutes=5)
        human = _lease(custody.identity, clock, SessionKind.HUMAN, minutes=15)
        custody.install(api_key, bytearray(key))
        custody.install(human, bytearray(key))
    with clock.at(minutes=6):
        # The shorter lease ends alone; the session keeps the longer deadline.
        assert custody.live_sessions() == (human.session_id,)
        session = _key_session()
        assert session.idle_deadline == session.absolute_deadline == human.expires_at
    with clock.at(minutes=12):
        repository = secure_object_repository_for_active_bucket()
        repository.list_namespaces()
    with clock.at(minutes=20):
        # No poll has retired the lease yet: storage must refuse on its own.
        with pytest.raises(SessionExpiredError):
            repository.list_namespaces()
        assert session.idle_deadline == human.expires_at
        with pytest.raises(BucketLockedError):
            get_active_master_key()
        assert session.sealed and current_active_bucket_session() is None
        assert custody.live_sessions() == ()


def _attended_child_lapse(custody: ProfileWorkerCustody, clock: _Clock, key: bytes) -> None:
    with clock.at(minutes=0):
        human = _lease(custody.identity, clock, SessionKind.HUMAN, minutes=15)
        custody.install(human, bytearray(key))
        child = _child(human, clock, minutes=5)
        custody.share(child)
        assert custody.require(child.session_id) == child
    with clock.at(minutes=5):
        # The short child ran out under a live parent: a request on it hears that its session ended.
        _assert_expired(custody, child.session_id)
        assert custody.require(human.session_id) == human
        _read_storage()
    with clock.at(minutes=6):
        second = _child(human, clock, minutes=5)
        custody.share(second)
        custody.retire(human.session_id)
        # Retiring the parent ends its child with it; neither ran out.
        for retired in (human.session_id, second.session_id):
            _assert_retired(custody, retired)
        _assert_expired(custody, child.session_id)


def _human_activity(custody: ProfileWorkerCustody, clock: _Clock, key: bytes) -> None:
    with clock.at(minutes=0):
        human = _lease(custody.identity, clock, SessionKind.HUMAN, minutes=15)
        custody.install(human, bytearray(key))
    for minutes in range(10, 301, 10):
        with clock.at(minutes=minutes):
            human = human.model_copy(update={"expires_at": now() + timedelta(minutes=15)})
            custody.refresh(human)
            assert custody.require(human.session_id) == human
            _read_storage()
    with clock.at(minutes=316):
        with pytest.raises(ProfileAccessRefusedError):
            custody.refresh(_reissued(human, clock, minutes=15))
        assert current_active_bucket_session() is None


def _require_binding_once(custody: ProfileWorkerCustody, clock: _Clock, key: bytes) -> None:
    with clock.at(minutes=0):
        human = _lease(custody.identity, clock, SessionKind.HUMAN, minutes=15)
        custody.install(human, bytearray(key))
        validate = profile_worker_custody.validate_automation_profile_binding
        calls = 0

        def counted(binding: ProfileAccessBinding, *, root: Path, dek: bytes | None = None) -> None:
            nonlocal calls
            calls += 1
            validate(binding, root=root, dek=dek)

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(profile_worker_custody, "validate_automation_profile_binding", counted)
            assert custody.require(human.session_id) == human
            assert calls == 1
            assert custody.require(human.session_id) == human
            assert calls == 2
            with custody.section(human.session_id):
                assert calls == 3
                assert custody.require(human.session_id) == human
                assert calls == 4
                _read_storage()
            assert calls == 5  # final exit remains an independent currentness boundary
            custody.expire()
            assert calls == 6  # idle expiry also revalidates


def _expiry_deadline(custody: ProfileWorkerCustody, clock: _Clock, key: bytes) -> None:
    with clock.at(minutes=0):
        # With no lease there is nothing to expire, so idle expiry has nothing to wait for.
        assert custody.seconds_until_expiry() is None
        api_key = _lease(custody.identity, clock, SessionKind.API_KEY, minutes=5)
        human = _lease(custody.identity, clock, SessionKind.HUMAN, minutes=15)
        custody.install(api_key, bytearray(key))
        custody.install(human, bytearray(key))
        assert custody.seconds_until_expiry() == 300
    with clock.at(minutes=4):
        assert custody.seconds_until_expiry() == 60
    with clock.at(minutes=6):
        assert custody.live_sessions() == (human.session_id,)
        assert custody.seconds_until_expiry() == 540
    with clock.at(minutes=15):
        assert custody.seconds_until_expiry() == 0
        assert custody.live_sessions() == ()
        assert custody.seconds_until_expiry() is None


_CASES: dict[str, Callable[[ProfileWorkerCustody, _Clock, bytes], None]] = {
    "expiry_deadline": _expiry_deadline,
    "require_binding_once": _require_binding_once,
    "human_activity": _human_activity,
    "attended_child_lapse": _attended_child_lapse,
    "sign_in_lease": _sign_in_lease,
    "api_key_lease": _api_key_lease,
    "mixed_leases": _mixed_leases,
    "latest_lease_expiry": _latest_lease_expiry,
}


def _exercise(tmp_path: Path, case: str) -> None:
    # A spawned interpreter has none of the ports the test session composes.
    with composed_profile_persistence_ports(), isolated_profile_storage_root(tmp_path=tmp_path) as root:
        root.mkdir(parents=True, exist_ok=True)
        profile_id = uuid4()
        publish_test_profile_capsule(profile_id, label="Lease window subject", root=root)
        envelope = load_committed_profile_password_material(profile_id, root=root).envelope
        identity = ProfileWorkerIdentity(
            worker_id=uuid4(),
            runtime_boot_id=uuid4(),
            binding=ProfileAccessBinding(
                profile_id=profile_id,
                installation_id=uuid4(),
                os_owner_id="synthetic-owner",
                custody_generation=envelope.password_generation,
                dek_epoch=UUID(bytes=base64.b64decode(envelope.dek_epoch)),
            ),
        )
        clock = _Clock(now())
        with override_settings(cadrumo_local_storage_root=root, cadrumo_active_profile=str(profile_id)):
            custody = ProfileWorkerCustody(identity, storage_root=root, monotonic=clock.monotonic)
            try:
                _CASES[case](custody, clock, derive_test_bucket_key(str(profile_id), purpose="dek"))
            finally:
                custody.close()


@pytest.mark.parametrize("case", sorted(_CASES))
def test_key_session_follows_the_leases_that_admit_work(tmp_path: Path, case: str) -> None:
    """A fresh child keeps the process-wide worker pin to this case."""
    result = run_audited_process(
        [sys.executable, "-m", _MODULE, str(tmp_path), case],
        capture_output=True,
        text=True,
        timeout=None,
        check=False,
    )
    assert result.returncode == 0, result.stderr


if __name__ == "__main__":
    _exercise(Path(sys.argv[1]), sys.argv[2])
