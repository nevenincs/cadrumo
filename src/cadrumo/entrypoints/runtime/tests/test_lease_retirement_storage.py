"""A retired lease takes profile storage away from an operation still running in its worker.

The runtime retires every lease of a connection when the frontend disconnects,
for example when a command stops waiting for settlement. Worker custody then
releases the key session at once, so storage reads and writes of the operation
body that is still running refuse as not ready from that instant.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from cadrumo.adapters.local_runtime.tests.profile_worker_support import lease, worker_profiles
from cadrumo.adapters.persistence.storage.errors import StorageValidationError
from cadrumo.adapters.persistence.storage.master_key.profile_worker_custody import ProfileWorkerCustody
from cadrumo.adapters.persistence.storage.runtime import inspect_bucket_storage_runtime
from cadrumo.adapters.persistence.storage.runtime_readiness import StorageRuntimeReadinessCode
from cadrumo.adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from cadrumo.core.config import override_settings
from cadrumo.entrypoints.adapter_composition import profile_adapter_composition
from cadrumo.tests.audited_process import run_audited_process

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires Windows profile custody"),
    pytest.mark.usefixtures("authority_operation"),
]


def _exercise(tmp_path: Path) -> None:
    with profile_adapter_composition(), worker_profiles(tmp_path) as profiles:
        root, ((identity, key), _) = profiles
        profile_id = str(identity.binding.profile_id)
        with override_settings(cadrumo_local_storage_root=root, cadrumo_active_profile=profile_id):
            custody = ProfileWorkerCustody(identity, storage_root=root)
            admitted = lease(identity)
            custody.install(admitted, bytearray(key))
            try:
                assert inspect_bucket_storage_runtime(profile_id).readiness.ready
                secure_object_repository_for_active_bucket()

                custody.retire(admitted.session_id)

                readiness = inspect_bucket_storage_runtime(profile_id).readiness
                assert not readiness.ready
                assert readiness.code is StorageRuntimeReadinessCode.NO_ACTIVE_SESSION
                try:
                    secure_object_repository_for_active_bucket()
                except StorageValidationError:
                    pass
                else:
                    raise AssertionError("storage stayed ready after its only lease was retired")
            finally:
                custody.close()


def test_retiring_the_only_lease_makes_profile_storage_not_ready(tmp_path: Path) -> None:
    """A fresh child keeps the process-global worker pin to this case."""
    result = run_audited_process(
        [sys.executable, "-m", "cadrumo.entrypoints.runtime.tests.test_lease_retirement_storage", str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr


if __name__ == "__main__":
    _exercise(Path(sys.argv[1]))
