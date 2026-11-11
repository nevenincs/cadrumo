"""A profile worker strengthens a fallback envelope at a later password sign-in, and only with no live session.

After one password proof the worker measures a stronger point in the background
and holds it. The next password proof with no live session re-wraps the same
data key at that point and refuses as custody changed, so the runtime proves the
attempt again on the successor generation. With a live session it proves
normally and writes nothing. The measurement is replaced by a fixed grid point,
because what a host measures depends on its hardware and is proved separately;
the proofs, the custody and the replacement are real. Each mode runs in its own
process, as a worker does, because worker custody is process-global.
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.storage.custody.capsule import load_committed_profile_password_material
from cadrumo.adapters.persistence.storage.master_key.profile_worker_custody import ProfileWorkerCustody
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import profile_authority_contexts
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.custody_ports import ProfileKdfStrength
from cadrumo.core.config import override_settings
from cadrumo.entrypoints.adapter_composition import profile_adapter_composition
from cadrumo.tests.audited_process import run_audited_process
from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ...adapters.tests.profile_worker_support import PROFILE_INPUT, lease, worker_profiles
from .. import profile_login
from ..profile_login import ProfileWorkerHumanLogin

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires Windows profile custody"),
    pytest.mark.usefixtures("authority_operation"),
]

_STRONGER = ProfileKdfStrength(memory_mib=64, iterations=4, parallelism=1)


def _measured_point(patcher: pytest.MonkeyPatch) -> threading.Event:
    measured = threading.Event()

    def measure(_profile_id: object, *, root: Path | None = None) -> ProfileKdfStrength:
        measured.set()
        return _STRONGER

    patcher.setattr(profile_login, "measure_profile_custody_stronger_password_kdf", measure)
    return measured


def _await_measurement(measured: threading.Event) -> None:
    assert measured.wait(30), "a fallback profile's password proof started no measurement"
    for thread in threading.enumerate():
        if thread.name == "profile-kdf-measurement":
            thread.join(30)


def _exercise(tmp_path: Path, mode: str) -> None:
    with pytest.MonkeyPatch.context() as patcher, profile_adapter_composition(), worker_profiles(tmp_path) as profiles:
        root, ((identity, dek), _) = profiles
        with override_settings(cadrumo_storage_root=root):
            profile_id = identity.binding.profile_id
            before = load_committed_profile_password_material(profile_id, root=root).envelope
            measured = _measured_point(patcher)
            custody = ProfileWorkerCustody(identity, storage_root=root)
            human = ProfileWorkerHumanLogin(custody, decode=lambda: profile_authority_contexts()[1])
            proof = bytearray(PROFILE_INPUT.encode())
            try:
                human.authenticate(proof)
                _await_measurement(measured)
                human.cancel()
                if mode == "live_session":
                    custody.install(lease(identity), bytearray(dek))
                    human.authenticate(proof)
                    assert load_committed_profile_password_material(profile_id, root=root).envelope == before
                    return
                with pytest.raises(ProfileAccessRefusedError) as refused:
                    human.authenticate(proof)
                assert refused.value.reason is AccessDenialCode.CUSTODY_CHANGED and refused.value.sign_in is None
                after = load_committed_profile_password_material(profile_id, root=root).envelope
                assert (after.kdf.memory_mib, after.kdf.iterations, after.kdf.parallelism) == (64, 4, 1)
                assert after.password_generation == before.password_generation + 1
                assert after.dek_epoch == before.dek_epoch
                assert human.seconds_until_expiry() is None, "a refused proof left a candidate behind"
            finally:
                proof[:] = bytes(len(proof))
                human.close()
                custody.close()


@pytest.mark.parametrize("mode", ["strengthens", "live_session"])
def test_worker_strengthens_a_fallback_envelope_at_a_later_password_sign_in(tmp_path: Path, mode: str) -> None:
    result = run_audited_process(
        [sys.executable, "-m", "cadrumo_runtime.host.tests.test_human_login_kdf_strengthening", str(tmp_path), mode],
        capture_output=True,
        text=True,
        timeout=None,
        check=False,
    )
    assert result.returncode == 0, result.stderr


if __name__ == "__main__":
    _exercise(Path(sys.argv[1]), sys.argv[2])
