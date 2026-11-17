"""Worker custody admits a lease the runtime minted on real time while the worker's document clock is frozen.

The runtime host mints every lease on the wall clock. A worker that runs tax
work under a fixed past instant must still admit that lease, and expire it on
real time, so custody's production clock is never the frozen document clock.
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
from cadrumo.core.time.clock import frozen_clock, wall_now
from cadrumo.tests.audited_process import run_audited_process
from cadrumo_client.contracts.automation_codes import AutomationCustodyCode, AutomationCustodyError

from ...profile_persistence_composition import composed_profile_persistence_ports
from ...tests.profile_capsule_runtime import derive_test_bucket_key, publish_test_profile_capsule
from ...tests.secure_sql import isolated_profile_storage_root
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
                if case == "past":
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


if __name__ == "__main__":
    _exercise(Path(sys.argv[1]), sys.argv[2])
