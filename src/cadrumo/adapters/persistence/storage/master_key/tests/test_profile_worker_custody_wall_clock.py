"""Worker custody admits a lease the runtime minted on real time while the worker's document clock is frozen.

The runtime host mints every lease on the wall clock. A worker that runs tax
work under a fixed past instant must still admit that lease, and expire it on
real time, so custody's production clock is never the frozen document clock.
The storage reads that work performs judge the key session custody opened on
the same real time: a past instant neither ends a live session nor revives an
ended one.
"""

from __future__ import annotations

import sys
import time
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from cadrumo.application.user_profile.access_contracts import AccessSession
from cadrumo.core.config import override_settings
from cadrumo.core.secure_object_write import SecureObjectWrite
from cadrumo.core.time.clock import frozen_clock, wall_now
from cadrumo.tests.audited_process import run_audited_process
from cadrumo_client.contracts.automation_codes import AutomationCustodyCode, AutomationCustodyError

from ...bucket.errors import BucketLockedError
from ...errors import SessionExpiredError, StorageSessionUnavailableError
from ...profile_persistence_composition import composed_profile_persistence_ports
from ...runtime_readiness import StorageRuntimeReadinessCode
from ...runtime_repository import secure_object_repository_for_active_bucket
from ...secure_object_namespaces import WORKFLOW_STATE_NAMESPACE
from ...tests.profile_capsule_runtime import derive_test_bucket_key, publish_test_profile_capsule
from ...tests.secure_sql import isolated_profile_storage_root
from ..active_session import current_active_bucket_session, require_fresh_active_session
from ..profile_worker_custody import ProfileWorkerCustody
from .profile_worker_identity_support import published_capsule_identity, worker_lease

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

_MODULE = "cadrumo.adapters.persistence.storage.master_key.tests.test_profile_worker_custody_wall_clock"


def _ended_on_wall_time(lease: AccessSession) -> AccessSession:
    """The lease issued ten minutes ago for five, its monotonic half still one minute old."""
    issued = wall_now() - timedelta(minutes=10)
    return lease.model_copy(
        update={
            "issued_at": issued,
            "expires_at": issued + timedelta(minutes=5),
            "issued_monotonic": time.monotonic() - 60,
        }
    )


def _write_and_read_workflow_state(payload: bytes) -> bytes | None:
    repo = secure_object_repository_for_active_bucket()
    repo.save_many(
        (
            SecureObjectWrite(
                namespace=WORKFLOW_STATE_NAMESPACE.namespace,
                object_key=WORKFLOW_STATE_NAMESPACE.require_default_object_key(),
                classification=WORKFLOW_STATE_NAMESPACE.sensitivity,
                schema_version=WORKFLOW_STATE_NAMESPACE.schema_version,
                written_at=wall_now(),
                payload=payload,
            ),
        )
    )
    loaded = repo.load(
        WORKFLOW_STATE_NAMESPACE.namespace,
        WORKFLOW_STATE_NAMESPACE.require_default_object_key(),
        expected_class=WORKFLOW_STATE_NAMESPACE.sensitivity,
        max_supported_version=WORKFLOW_STATE_NAMESPACE.schema_version,
    )
    return None if loaded is None else loaded.payload


def _storage_case(custody: ProfileWorkerCustody, live: AccessSession, key: bytes, case: str) -> None:
    custody.install(live, bytearray(key))
    if case == "storage_past":
        with frozen_clock((wall_now() - timedelta(days=400)).replace(microsecond=0)):
            assert require_fresh_active_session() is current_active_bucket_session()
            assert _write_and_read_workflow_state(b"past-instant") == b"past-instant"
        session = current_active_bucket_session()
        assert session is not None
        assert not session.is_expired(wall_now())
        custody.require(live.session_id)
        assert _write_and_read_workflow_state(b"real-time") == b"real-time"
        return
    # The key session takes the window of a lease that ended on real time, as
    # custody retargets it when the leases sharing its key change.
    session = current_active_bucket_session()
    assert session is not None
    assert _write_and_read_workflow_state(b"while-live") == b"while-live"
    resolved = secure_object_repository_for_active_bucket()
    ended = _ended_on_wall_time(live)
    session.retarget_lifetime(opened_at=ended.issued_at, idle_minutes=5, deadline=ended.expires_at)
    with frozen_clock(ended.issued_at + timedelta(minutes=1)):
        with pytest.raises(StorageSessionUnavailableError) as refused:
            secure_object_repository_for_active_bucket()
        assert refused.value.context is not None
        assert refused.value.context["readiness_code"] == StorageRuntimeReadinessCode.SESSION_EXPIRED.value
        with pytest.raises(SessionExpiredError):
            resolved.load(
                WORKFLOW_STATE_NAMESPACE.namespace,
                WORKFLOW_STATE_NAMESPACE.require_default_object_key(),
                expected_class=WORKFLOW_STATE_NAMESPACE.sensitivity,
                max_supported_version=WORKFLOW_STATE_NAMESPACE.schema_version,
            )
        with pytest.raises(BucketLockedError):
            require_fresh_active_session()


def _exercise(tmp_path: Path, case: str) -> None:
    # A spawned interpreter has none of the ports the test session composes.
    with composed_profile_persistence_ports(), isolated_profile_storage_root(tmp_path=tmp_path) as root:
        root.mkdir(parents=True, exist_ok=True)
        profile_id = uuid4()
        publish_test_profile_capsule(profile_id, label="Wall clock subject", root=root)
        identity = published_capsule_identity(profile_id, root)
        key = derive_test_bucket_key(str(profile_id), purpose="dek")
        with override_settings(cadrumo_storage_root=root, cadrumo_active_profile=str(profile_id)):
            custody = ProfileWorkerCustody(identity, storage_root=root)
            try:
                live = worker_lease(identity, minutes=15, issued_monotonic=time.monotonic())
                if case.startswith("storage_"):
                    _storage_case(custody, live, key, case)
                elif case == "past":
                    with frozen_clock((wall_now() - timedelta(days=400)).replace(microsecond=0)):
                        custody.install(live, bytearray(key))
                        assert custody.live_sessions() == (live.session_id,)
                        custody.require(live.session_id)
                else:
                    ended = _ended_on_wall_time(live)
                    with (
                        frozen_clock(ended.issued_at + timedelta(minutes=1)),
                        pytest.raises(AutomationCustodyError) as refused,
                    ):
                        custody.install(ended, bytearray(key))
                    assert refused.value.reason is AutomationCustodyCode.CREDENTIAL_REJECTED
                    assert custody.live_sessions() == ()
            finally:
                custody.close()


@pytest.mark.parametrize("case", ("past", "inside_an_ended_lease"))
def test_custody_judges_leases_on_real_time_under_a_frozen_document_clock(tmp_path: Path, case: str) -> None:
    """A wall-minted lease is live under a past instant, and an ended one stays ended under an instant inside it."""
    result = run_audited_process(
        [sys.executable, "-m", _MODULE, str(tmp_path), case],
        capture_output=True,
        text=True,
        timeout=None,
        check=False,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("case", ("storage_past", "storage_inside_an_ended_lease"))
def test_worker_storage_judges_the_key_session_on_real_time_under_a_frozen_document_clock(
    tmp_path: Path,
    case: str,
) -> None:
    """Storage access under a past instant keeps a live key session live and refuses an ended one.

    DISCRIMINATING against judging bucket-session expiry on the document clock:
    a past instant would admit a key session whose lease ended, and rolling the
    idle window from that instant would leave the live session expired on
    real time once the scope closed.
    """
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
