"""A supervised KDF parent killed mid-unwrap must not strand lease or worker.

The supervised unwrap runs two processes: the caller holds the OS file lease
and supervises a child worker that performs the Argon2id hash. If the caller
is killed while the worker is mid-hash, the lease must be released by the
operating system and the orphaned worker must terminate in bounded time --
on POSIX it lives in its own session and completes the hash, then hits the
closed pipe; on Windows the job object's kill-on-close takes it with the
parent. The next run must then re-acquire the lease and complete a real
unlock, proven against the profile's sentinel.

The envelope is built once through the production registration door (whose
fixed fallback parameters make the unwrap slow enough to kill mid-hash), and
the child drives the substrate lease and worker exactly as the production
unlock path does. No mocks, no skips.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from base64 import b64encode
from pathlib import Path
from secrets import token_bytes
from uuid import UUID

import pytest

from cadrumo.adapters.persistence.storage.custody import (
    ProfileCustodyEnvelope,
    ProfileCustodySentinelRecord,
    unlock_profile_custody,
)
from cadrumo.application.user_profile import create_profile_custody_registration_material
from cadrumo.core import pid_is_alive
from cadrumo.core.config import Settings
from cadrumo.core.hashing import canonical_json_bytes

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_PROFILE_ID = UUID("06648eb9-e60e-46d2-bd35-9aaf55a92e24")
_PASSPHRASE = "orphan-matrix operator passphrase clearing the verifier minimum"  # noqa: S105 - synthetic test credential

_ORPHAN_CHILD = r"""
import sys
import time
from pathlib import Path

from cadrumo.adapters.persistence.storage.custody import parse_profile_custody_envelope
from cadrumo.adapters.persistence.storage.custody._kdf_supervision import (
    _SupervisedKdfWorker,
    profile_kdf_lease,
    profile_password_wrap_aad,
)

root = Path(sys.argv[1])
envelope = parse_profile_custody_envelope(Path(sys.argv[2]).read_bytes())
password = sys.argv[3].encode("utf-8")
aad = profile_password_wrap_aad(
    profile_id=envelope.profile_id,
    password_generation=envelope.password_generation,
    dek_epoch=envelope.dek_epoch,
    kdf=envelope.kdf,
)
with (
    profile_kdf_lease(deadline=time.monotonic() + 30),
    _SupervisedKdfWorker(deadline=time.monotonic() + 30) as worker,
):
    print("supervising", worker._process.pid, flush=True)
    dek = worker.unwrap(
        password=password,
        kdf=envelope.kdf,
        wrapped_dek=envelope.wrapped_dek,
        associated_data=aad,
    )
    print("unwrapped", dek is not None, flush=True)
"""


def test_killed_supervisor_leaves_no_stuck_lease_and_the_next_run_reacquires_and_unlocks(
    tmp_path: Path,
) -> None:
    """The orphaned worker is reaped in bounded time and the lease survives the parent."""
    dek = token_bytes(32)
    dek_epoch = b64encode(token_bytes(16)).decode("ascii")
    material = create_profile_custody_registration_material(
        profile_id=_PROFILE_ID,
        password=_PASSPHRASE,
        dek=dek,
        dek_epoch=dek_epoch,
        salt=token_bytes(16),
    )
    envelope = material.envelope
    sentinel = material.sentinel
    assert isinstance(envelope, ProfileCustodyEnvelope)
    assert isinstance(sentinel, ProfileCustodySentinelRecord)
    envelope_path = tmp_path / "envelope.json"
    envelope_path.write_bytes(canonical_json_bytes(envelope.model_dump(mode="json")))

    child = subprocess.Popen(  # noqa: S603 - fixed test interpreter and module
        [sys.executable, "-c", _ORPHAN_CHILD, str(tmp_path), str(envelope_path), _PASSPHRASE],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, "CADRUMO_LOCAL_STORAGE_ROOT": str(tmp_path)},
    )
    assert child.stdout is not None
    line = child.stdout.readline().strip()
    assert line, "supervised child produced no readiness line"
    supervising, pid_text = line.split()
    assert supervising == "supervising"
    worker_pid = int(pid_text)

    child.kill()
    assert child.wait(timeout=5.0) != 0

    deadline = time.monotonic() + 30.0
    while pid_is_alive(worker_pid) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not pid_is_alive(worker_pid), "orphaned KDF worker outlived its bounded reaping window"

    unlock = unlock_profile_custody(
        envelope,
        _PASSPHRASE,
        sentinel=sentinel,
        settings=Settings(cadrumo_local_storage_root=tmp_path),
    )
    assert unlock.dek == dek
