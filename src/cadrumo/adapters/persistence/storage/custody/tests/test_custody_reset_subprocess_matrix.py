"""Fresh-interpreter matrices for config reset and the destructive delete.

Config reset is a delete authority that must behave identically with no test
process state behind it: the journal, the preflight snapshots, the KDF and the
capsule lifecycle all resolve from the storage root alone. These cases run the
whole reset, the retired-custody refusal, and a delete torn by a hard exit in
a brand-new interpreter seeded only through production doors, and assert on
the filesystem state left behind.

No mocks, no skips; the only concession to the fresh interpreter is the
settings mirroring in ``_child_env``, the same env-var seams a deployed
process would use.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from uuid import UUID

import pytest

from ......application.user_profile.lifecycle import ProfileCapsuleLifecycle
from ......application.user_profile.custody_transactions import ProfileCustodyTransactionRefusalError
from ......tests.secure_sql import isolated_profile_storage_root
from .. import (
    ProfileCustodyRecoveryGuidance,
    ProfileCustodyRefusal,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_PROFILE_ID = UUID("06648eb9-e60e-46d2-bd35-9aaf55a92e24")
_LEGACY_BUCKET_ID = "33333333-3333-4333-8333-333333333333"

_PROFILE_COMPOSITION_CHILD = r"""
from contextlib import ExitStack

from cadrumo.adapters.persistence.storage import build_profile_custody_port, build_profile_login_session_port
from cadrumo.application.user_profile import bind_profile_custody_port, bind_profile_login_session_port

composition = ExitStack()
composition.enter_context(bind_profile_custody_port(build_profile_custody_port()))
composition.enter_context(bind_profile_login_session_port(build_profile_login_session_port()))
"""

_RESET_CHILD = (
    _PROFILE_COMPOSITION_CHILD
    + r"""
import sys

from cadrumo.application.config_reset import (
    ConfigResetOperationStatus,
    resume_config_reset,
    start_config_reset,
)
from cadrumo.tests.profile_capsule import open_test_profile_session
from cadrumo.tests.user_profile import register_minimal_profile

root = sys.argv[1]
profile_id = sys.argv[2]
with open_test_profile_session(profile_id):
    register_minimal_profile(profile_id=profile_id, record_empty_legal_hold=True)
operation = start_config_reset(confirmed=True)
for _ in range(8):
    if operation.status is ConfigResetOperationStatus.COMPLETE:
        break
    operation = resume_config_reset(operation.operation_id, confirmed=True)
print(operation.status.value, flush=True)
sys.exit(0 if operation.status is ConfigResetOperationStatus.COMPLETE else 9)
"""
)

_LEGACY_REFUSAL_CHILD = (
    _PROFILE_COMPOSITION_CHILD
    + r"""
import sys
from pathlib import Path

from cadrumo.adapters.persistence.storage.custody import ProfileCustodyRefusedError
from cadrumo.application.config_reset import start_config_reset

root = Path(sys.argv[1])
bucket_id = sys.argv[2]
bucket_dir = root / "buckets" / bucket_id
bucket_dir.mkdir(parents=True)
(bucket_dir / "manifest.toml").write_text(f"bucket_id = {bucket_id!r}\n", encoding="utf-8")
try:
    start_config_reset(confirmed=True)
except ProfileCustodyRefusedError as exc:
    print(exc.refusal.value, flush=True)
    print(exc.recovery_guidance[0].value, exc.recovery_guidance[1].value, flush=True)
    sys.exit(7)
print("no-refusal", flush=True)
sys.exit(8)
"""
)

_DELETE_CRASH_CHILD = (
    _PROFILE_COMPOSITION_CHILD
    + r"""
import os
import sys
from pathlib import Path
from uuid import UUID

from cadrumo.application.user_profile import ProfileCapsuleLifecycle
from cadrumo.tests.profile_capsule import open_test_profile_session
from cadrumo.tests.user_profile import register_minimal_profile

root = Path(sys.argv[1])
profile_id = sys.argv[2]
with open_test_profile_session(profile_id):
    register_minimal_profile(profile_id=profile_id, record_empty_legal_hold=True)
lifecycle = ProfileCapsuleLifecycle(root=root)
journal = lifecycle.prepare_delete(profile_id=UUID(profile_id))
confirmation = lifecycle.confirm_delete(journal)
print(journal.transaction_id, flush=True)
os._exit(97)
"""
)


def _child_env(root: Path) -> dict[str, str]:
    """Mirror the isolated-root overrides into a fresh interpreter's settings."""
    from ......core.config import load_settings

    settings = load_settings()
    passphrase = settings.cadrumo_secret_passphrase
    if passphrase is None:
        raise RuntimeError("the reset subprocess matrix requires a configured secret-store passphrase")
    return {
        **os.environ,
        "CADRUMO_LOCAL_STORAGE_ROOT": str(root),
        "CADRUMO_PROFILE_KDF_MEASURE_CALIBRATION": "false",
        "CADRUMO_SECRET_STORE_BACKEND": settings.cadrumo_secret_store_backend,
        "CADRUMO_SECRET_PASSPHRASE": passphrase.get_secret_value(),
    }


def test_fresh_interpreter_reset_erases_the_seeded_profile_through_the_production_door(
    tmp_path: Path,
) -> None:
    """A whole reset runs to completion in an interpreter with no test state."""
    with isolated_profile_storage_root(tmp_path=tmp_path) as root:
        proc = subprocess.Popen(  # noqa: S603 - fixed test interpreter and module
            [sys.executable, "-c", _RESET_CHILD, str(root), str(_PROFILE_ID)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=_child_env(root),
        )
        assert proc.stdout is not None
        status = proc.stdout.readline().strip()
        assert proc.wait(timeout=120) == 0, proc.stderr.read() if proc.stderr else status
        assert status == "complete"
        assert not (root / "buckets" / str(_PROFILE_ID)).exists()


def test_fresh_interpreter_refuses_a_reset_against_a_retired_custody_member(
    tmp_path: Path,
) -> None:
    """The DESTRUCTIVE_RESET guidance fires with no test process state behind it."""
    with isolated_profile_storage_root(tmp_path=tmp_path) as root:
        proc = subprocess.Popen(  # noqa: S603 - fixed test interpreter and module
            [sys.executable, "-c", _LEGACY_REFUSAL_CHILD, str(root), _LEGACY_BUCKET_ID],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=_child_env(root),
        )
        assert proc.stdout is not None
        lines = [proc.stdout.readline().strip() for _ in range(2)]
        assert proc.wait(timeout=60) == 7, proc.stderr.read() if proc.stderr else lines
        assert lines == [
            ProfileCustodyRefusal.LEGACY_CUSTODY_DETECTED.value,
            f"{ProfileCustodyRecoveryGuidance.DESTRUCTIVE_RESET.value} "
            f"{ProfileCustodyRecoveryGuidance.REENROLL_PROFILE.value}",
        ]


def test_crash_between_confirm_and_delete_leaves_an_intact_capsule_and_no_resumable_half_state(
    tmp_path: Path,
) -> None:
    """A delete torn after confirmation is inert: nothing resumes it, and a fresh one completes."""
    with isolated_profile_storage_root(tmp_path=tmp_path) as root:
        proc = subprocess.Popen(  # noqa: S603 - fixed test interpreter and module
            [sys.executable, "-c", _DELETE_CRASH_CHILD, str(root), str(_PROFILE_ID)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=_child_env(root),
        )
        assert proc.stdout is not None
        tx_line = proc.stdout.readline().strip()
        assert proc.wait(timeout=120) == 97, proc.stderr.read() if proc.stderr else tx_line
        stale_transaction_id = UUID(tx_line)

        capsule = root / "buckets" / str(_PROFILE_ID)
        assert (capsule / "db" / "cadrumo.db").is_file()

        lifecycle = ProfileCapsuleLifecycle(root=root)
        with pytest.raises(
            ProfileCustodyTransactionRefusalError,
            match="does not name a custody create transaction",
        ):
            lifecycle.recover_create(stale_transaction_id)

        journal = lifecycle.prepare_delete(profile_id=_PROFILE_ID)
        confirmation = lifecycle.confirm_delete(journal)
        lifecycle.delete(confirmation)
        assert not capsule.exists()
