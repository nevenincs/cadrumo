"""Fresh-process recovery proofs for every durable config-reset boundary.

The ``"secrets"`` literal in the crash-subprocess settings preamble is
deliberate, not injected: the profile the crash subprocess must unlock is
created beforehand via ``_isolated_reset_root`` (from ``.test_config_reset``),
which wraps ``isolated_profile_storage_root`` -- deriving
``cadrumo_secret_store_dir`` from the real taxonomy accessor
(``storage_overrides(tmp_path, StorageCategory.SECRETS)`` -> ``tmp_path /
"secrets"``). The subprocess must independently compute the same location to
find the master key that setup already minted; renaming it breaks the
handoff between the two processes.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from textwrap import dedent
from typing import Final

import pytest

from ...core.storage_taxonomy import StorageCategory
from ...tests.profile_capsule import open_test_profile_session
from ...tests.storage_scope import storage_env_overrides
from .test_config_reset import (
    _OVERRIDE_REASON,
    _PROFILE_A_ID,
    _create_profile,
    _isolated_reset_root,
    _persist_filing,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

PINNED_TAXONOMY_LITERALS: Final[frozenset[str]] = frozenset({"secrets"})
"""Taxonomy-vocabulary literals this module deliberately pins. See the module docstring."""

_CRASH_EXIT_CODE = 91
_BOUNDARIES = (
    "snapshotted",
    "retention_approved",
    "auth_clearing",
    "auth_clearing_after_effect",
    "auth_cleared",
    "pointer_reconciling",
    "pointer_reconciling_after_effect",
    "pointer_reconciled",
    "deleting",
    "deleting_after_effect",
    "deleted",
)

_SETTINGS_PREAMBLE = dedent(
    """
    from __future__ import annotations

    import sys
    from pathlib import Path

    from cadrumo.core import config as config_module
    from cadrumo.core.config import DEV_TEST_DATABASE_PASSWORD, Settings

    root = Path(sys.argv[1])
    settings = Settings(
        _env_file=None,
        cadrumo_local_storage_root=root,
        cadrumo_active_profile=None,
        cadrumo_secret_store_backend="auto",
        cadrumo_secret_store_dir=root.parent / "secrets",
        cadrumo_secret_passphrase=DEV_TEST_DATABASE_PASSWORD,
        cadrumo_output_language="en",
    )
    token = config_module._settings_override.set(settings)
    from cadrumo.application.wizard.compiler import ensure_profile_keys_registered

    ensure_profile_keys_registered()

    from contextlib import ExitStack

    from cadrumo.adapters.persistence.storage import (
        build_profile_custody_port,
        build_profile_login_session_port,
    )
    from cadrumo.application.user_profile.custody_ports import bind_profile_custody_port
    from cadrumo.application.user_profile.login_session_port import bind_profile_login_session_port

    composition = ExitStack()
    composition.enter_context(bind_profile_custody_port(build_profile_custody_port()))
    composition.enter_context(bind_profile_login_session_port(build_profile_login_session_port()))
    """,
)

_CRASH_HARNESS = _SETTINGS_PREAMBLE + dedent(
    """
    import os

    from cadrumo.application._config_reset_repository import ConfigResetJournalRepository
    from cadrumo.application.config_reset import start_config_reset

    boundary = sys.argv[2]
    phase_by_boundary = {
        "snapshotted": "snapshotted",
        "retention_approved": "retention_approved",
        "auth_clearing": "auth_clearing",
        "auth_clearing_after_effect": "auth_clearing",
        "auth_cleared": "auth_cleared",
        "pointer_reconciling": "pointer_reconciling",
        "pointer_reconciling_after_effect": "pointer_reconciling",
        "pointer_reconciled": "pointer_reconciled",
        "deleting": "deleting",
        "deleting_after_effect": "deleting",
        "deleted": "deleted",
    }
    # Each entry anchors a crash on the RETURN of the effect that phase really
    # performs, so both anchors track the flow rather than a past shape of it:
    #
    # * auth clearing anchors on the acquisition-lock sweep, not on the full
    #   revocation. A reset holds locks on profiles it has not unlocked, and a
    #   locked target deliberately gets the key-free half only -- driving the
    #   full revocation at it was a defect the flow already closed -- so
    #   `reset_operator_auth` is never reached on this path.
    # * deletion anchors on the capsule lifecycle, which is where the erase
    #   moved when the custody capsule became the sole profile authority.
    effect_return_by_boundary = {
        "auth_clearing_after_effect": ("operator_cleanup.py", "clear_operator_auth_acquisition_locks"),
        "pointer_reconciling_after_effect": ("profile_pointer.py", "clear"),
        # The module holding ProfileCapsuleLifecycle.delete was renamed from
        # _lifecycle.py to lifecycle.py. This pin kept the old spelling, which
        # then matched only the unrelated invoices/_lifecycle.py -- a module
        # with no delete at all -- so the trace never fired and the boundary
        # was never injected. A pin naming a file is a rename away from
        # testing nothing, which is why the RuntimeError below exists.
        "deleting_after_effect": ("user_profile/lifecycle.py", "delete"),
    }

    def durable_target_phase() -> str | None:
        operation = ConfigResetJournalRepository().latest()
        if operation is None or len(operation.targets) != 1:
            return None
        return operation.targets[0].phase.value

    # A crash boundary that never matches injects nothing, and the run then
    # completes normally -- indistinguishable from a passing test unless the
    # miss is reported. Record whether the injection point was ever reached so
    # the failure names which half went wrong.
    effect_frame_seen = []

    def trace(frame, event, arg):
        if event != "return":
            return trace
        expected_effect = effect_return_by_boundary.get(boundary)
        if expected_effect is not None:
            filename, function_name = expected_effect
            native = filename.replace("/", os.sep)
            if frame.f_code.co_filename.endswith(native) and frame.f_code.co_name == function_name:
                effect_frame_seen.append(True)
                if durable_target_phase() == phase_by_boundary[boundary]:
                    os._exit(91)
            return trace
        if frame.f_code.co_name not in {"create_exclusive", "save"}:
            return trace
        if not frame.f_code.co_filename.endswith(("_config_reset_repository.py", "journal_repository.py")):
            return trace
        if durable_target_phase() == phase_by_boundary[boundary]:
            os._exit(91)
        return trace

    sys.settrace(trace)
    try:
        start_config_reset(confirmed=True)
    finally:
        config_module._settings_override.reset(token)
    if boundary in effect_return_by_boundary and not effect_frame_seen:
        filename, function_name = effect_return_by_boundary[boundary]
        raise RuntimeError(
            f"crash boundary {boundary} never reached its injection point "
            f"{function_name} in a file ending {filename}: the effect moved or was renamed, "
            "so this boundary was silently never injected"
        )
    raise RuntimeError(f"reset completed without observing requested boundary: {boundary}")
    """,
)

_RESUME_HARNESS = _SETTINGS_PREAMBLE + dedent(
    """
    from cadrumo.application.config_reset import resume_config_reset

    operation_id = sys.argv[2]
    try:
        operation = resume_config_reset(
            operation_id,
            confirmed=True,
            acknowledge_retention_override=True,
            retention_override_reason=sys.argv[3],
        )
        print(operation.model_dump_json())
    finally:
        config_module._settings_override.reset(token)
    """,
)


def _child_env(root: Path) -> dict[str, str]:
    from ...core.config import DEV_TEST_DATABASE_PASSWORD

    env = {key: value for key, value in os.environ.items() if not key.startswith(("AEAT_", "CADRUMO_", "PYTEST_"))}
    env.update(
        {
            "CADRUMO_LOCAL_STORAGE_ROOT": str(root),
            "CADRUMO_SECRET_STORE_BACKEND": "auto",
            # Anchored on the root's parent, so the secret substrate stays a
            # sibling of the bucket tree rather than nesting inside it.
            **storage_env_overrides(root.parent, StorageCategory.SECRETS),
            "CADRUMO_SECRET_PASSPHRASE": DEV_TEST_DATABASE_PASSWORD,
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
        },
    )
    return env


def _run_fresh_resume_allowing_failure(
    root: Path,
    operation_id: str,
) -> subprocess.CompletedProcess[str]:
    """Resume without asserting success, for cases that must FAIL.

    The ordinary runner refuses on a non-zero child so a broken resume cannot
    pass unnoticed. A case asserting the refusal itself needs the process back
    instead.
    """
    return subprocess.run(  # noqa: S603 - fixed interpreter and repository-owned harness
        [sys.executable, "-c", _RESUME_HARNESS, str(root), operation_id, _OVERRIDE_REASON],
        cwd=Path.cwd(),
        env=_child_env(root),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=90,
    )


def _refuse_with_child_stderr(
    result: subprocess.CompletedProcess[str],
    *,
    what: str,
) -> subprocess.CompletedProcess[str]:
    """Fail with the child's OWN error rather than an opaque exit code.

    These harnesses run the reset in a real child process, so everything that
    explains a failure -- the traceback, the refusal, an import that could not
    resolve -- is written to that child's stderr. ``check=True`` discards it:
    ``CalledProcessError`` renders only the argv, so a red case reports that a
    process exited 1 and nothing whatever about why.

    That gap has twice turned a one-look diagnosis into hours of search. The
    second time, the child had died importing ``cadrumo`` while a peer was
    mid-write in this shared worktree -- a fact stated plainly in one line of
    the stderr surfaced here, and wholly invisible in the exit code.
    """
    if result.returncode == 0:
        return result
    separator = chr(10)
    raise AssertionError(
        separator.join(
            (
                f"{what} child exited {result.returncode}",
                "--- child stdout ---",
                result.stdout[-2000:],
                "--- child stderr ---",
                result.stderr[-4000:],
            ),
        ),
    )


def _run_crashing_start(root: Path, boundary: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - fixed interpreter and repository-owned harness
        [sys.executable, "-c", _CRASH_HARNESS, str(root), boundary],
        cwd=Path.cwd(),
        env=_child_env(root),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=90,
    )


def _run_fresh_resume(
    root: Path,
    operation_id: str,
) -> subprocess.CompletedProcess[str]:
    resumed = subprocess.run(  # noqa: S603 - fixed interpreter and repository-owned harness
        [
            sys.executable,
            "-c",
            _RESUME_HARNESS,
            str(root),
            operation_id,
            _OVERRIDE_REASON,
        ],
        cwd=Path.cwd(),
        env=_child_env(root),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=90,
    )
    return _refuse_with_child_stderr(resumed, what="fresh resume")


@pytest.mark.parametrize("boundary", _BOUNDARIES)
def test_every_durable_boundary_rolls_forward_in_a_fresh_process(
    tmp_path: Path,
    boundary: str,
) -> None:
    from ...adapters.persistence.storage.bucket import bucket_paths
    from ...adapters.persistence.storage.sql import dispose_engine
    from ...core.bucket_pointer import read_pointer
    from .._config_reset_models import (
        ConfigResetOperation,
        ConfigResetOperationStatus,
        ConfigResetTargetPhase,
    )
    from .._config_reset_repository import ConfigResetJournalRepository
    from ..auth.operator import configure_operator_auth

    with _isolated_reset_root(tmp_path) as root:
        _create_profile(_PROFILE_A_ID, label="Recovery operator", tax_id="00000000T")
        with open_test_profile_session(_PROFILE_A_ID):
            configure_operator_auth("certificate")
        if boundary == "snapshotted":
            _persist_filing(_PROFILE_A_ID, filing_year=2025, seed="7")
        dispose_engine()

        crashed = _run_crashing_start(root, boundary)

        assert crashed.returncode == _CRASH_EXIT_CODE, (
            boundary,
            crashed.stdout,
            crashed.stderr,
        )
        repository = ConfigResetJournalRepository()
        interrupted = repository.latest()
        assert interrupted is not None
        expected_phase = boundary.removesuffix("_after_effect")
        assert interrupted.targets[0].phase.value == expected_phase
        if boundary == "pointer_reconciling_after_effect":
            assert read_pointer(root).bucket_id is None
        if boundary == "deleting_after_effect":
            assert bucket_paths(root, _PROFILE_A_ID).bucket_dir.exists() is False

        resumed_process = _run_fresh_resume(root, interrupted.operation_id)
        resumed = ConfigResetOperation.model_validate_json(resumed_process.stdout)
        assert resumed.status is ConfigResetOperationStatus.COMPLETE
        assert resumed.summary is not None
        assert resumed.summary.target_count == 1
        assert resumed.summary.deleted_count == 1
        assert resumed.targets[0].phase is ConfigResetTargetPhase.DELETED
        assert bucket_paths(root, _PROFILE_A_ID).bucket_dir.exists() is False
        assert read_pointer(root).bucket_id is None
        assert repository.load(interrupted.operation_id) == resumed


def test_pointer_reconciling_resume_refuses_a_later_absent_tombstone(tmp_path: Path) -> None:
    """A later clear is not the reset's exact expected pointer successor."""
    from .._config_reset_models import ConfigResetOperationStatus, ConfigResetPauseReason
    from .._config_reset_repository import ConfigResetJournalRepository
    from ..config_reset import resume_config_reset
    from ..user_profile.profile_pointer import active_profile_pointer_transaction

    with _isolated_reset_root(tmp_path) as root:
        _create_profile(_PROFILE_A_ID, label="Recovery operator", tax_id="00000000T")
        crashed = _run_crashing_start(root, "pointer_reconciling_after_effect")
        assert crashed.returncode == _CRASH_EXIT_CODE, (crashed.stdout, crashed.stderr)
        interrupted = ConfigResetJournalRepository().latest()
        assert interrupted is not None
        expected = interrupted.pointer_snapshot.record.transition_revision + 1

        with active_profile_pointer_transaction(root) as pointer:
            selected = pointer.select("22222222-2222-4222-8222-222222222222")
            later_tombstone = pointer.clear()
        assert selected.transition_revision == expected + 1
        assert later_tombstone.bucket_id is None
        assert later_tombstone.transition_revision == expected + 2

        resumed = resume_config_reset(
            interrupted.operation_id,
            confirmed=True,
            acknowledge_retention_override=True,
            retention_override_reason=_OVERRIDE_REASON,
        )
        assert resumed.status is ConfigResetOperationStatus.PAUSED
        assert resumed.pause_reason is ConfigResetPauseReason.POINTER_CHANGED
        assert resumed.pointer_snapshot.record == later_tombstone


def test_fresh_resume_canonicalizes_journal_bucket_identity_before_target_lock(
    tmp_path: Path,
) -> None:
    """A whitespace-bearing durable identity resumes under its canonical lock key."""
    from ...adapters.persistence.storage.bucket import bucket_paths
    from .._config_reset_models import ConfigResetOperation, ConfigResetOperationStatus
    from .._config_reset_repository import ConfigResetJournalRepository

    with _isolated_reset_root(tmp_path) as root:
        _create_profile(_PROFILE_A_ID, label="Recovery operator", tax_id="00000000T")
        crashed = _run_crashing_start(root, "retention_approved")
        assert crashed.returncode == _CRASH_EXIT_CODE, (crashed.stdout, crashed.stderr)

        repository = ConfigResetJournalRepository()
        interrupted = repository.latest()
        assert interrupted is not None
        journal_path = repository.path_for(interrupted.operation_id)
        document = json.loads(journal_path.read_text(encoding="utf-8"))
        document["targets"][0]["bucket_id"] = f" {_PROFILE_A_ID} "
        journal_path.write_text(json.dumps(document), encoding="utf-8")

        resumed_process = _run_fresh_resume(root, interrupted.operation_id)
        resumed = ConfigResetOperation.model_validate_json(resumed_process.stdout)

        assert resumed.status is ConfigResetOperationStatus.COMPLETE
        assert resumed.targets[0].bucket_id == _PROFILE_A_ID
        assert bucket_paths(root, _PROFILE_A_ID).bucket_dir.exists() is False


def test_resume_refuses_malformed_journal_identity_before_target_lock(
    tmp_path: Path,
) -> None:
    """An invalid journal target is an application error before deletion can start."""
    from ...adapters.persistence.storage.bucket import bucket_paths
    from .._config_reset_repository import ConfigResetJournalRepository
    from ..config_reset import ConfigResetError, resume_config_reset

    with _isolated_reset_root(tmp_path) as root:
        _create_profile(_PROFILE_A_ID, label="Recovery operator", tax_id="00000000T")
        crashed = _run_crashing_start(root, "retention_approved")
        assert crashed.returncode == _CRASH_EXIT_CODE, (crashed.stdout, crashed.stderr)

        repository = ConfigResetJournalRepository()
        interrupted = repository.latest()
        assert interrupted is not None
        journal_path = repository.path_for(interrupted.operation_id)
        document = json.loads(journal_path.read_text(encoding="utf-8"))
        document["targets"][0]["bucket_id"] = "x" * 129
        journal_path.write_text(json.dumps(document), encoding="utf-8")

        with pytest.raises(ConfigResetError) as raised:
            resume_config_reset(interrupted.operation_id, confirmed=True)

        assert raised.value.context == {"operation_id": interrupted.operation_id, "journal_corrupt": True}
        assert bucket_paths(root, _PROFILE_A_ID).bucket_dir.is_dir()


def test_a_deletion_marker_cannot_attest_an_erase_that_is_not_its_own(tmp_path: Path) -> None:
    """The marker that authorises "my erase already landed" is unforgeable.

    A resume advances a target whose capsule is already gone, on the strength of
    the deletion marker this operation wrote immediately before erasing it.
    Absence looks identical whether the reset destroyed the capsule or something
    else did, so that marker is the whole difference between reporting work this
    reset performed and laying claim to somebody else's destruction.

    Both dimensions of the claim are refused at the journal boundary rather than
    at the point of use, which is the stronger place for them: a disowned marker
    cannot be persisted or loaded at all, so no code path downstream has to
    remember to check.
    """
    from pydantic import ValidationError

    from ...adapters.persistence.storage.bucket import bucket_paths
    from ...adapters.persistence.storage.sql import dispose_engine
    from .._config_reset_models import ConfigResetOperation
    from .._config_reset_repository import ConfigResetJournalRepository

    with _isolated_reset_root(tmp_path) as root:
        _create_profile(_PROFILE_A_ID, label="Recovery operator", tax_id="00000000T")
        dispose_engine()

        crashed = _run_crashing_start(root, "deleting_after_effect")
        assert crashed.returncode == _CRASH_EXIT_CODE, (crashed.stdout, crashed.stderr)

        repository = ConfigResetJournalRepository()
        interrupted = repository.latest()
        assert interrupted is not None
        target = interrupted.targets[0]
        assert target.deletion_marker is not None
        assert bucket_paths(root, _PROFILE_A_ID).bucket_dir.exists() is False

        def _rebuilt_with(marker_update: dict[str, str]) -> None:
            deletion_marker = target.deletion_marker
            assert deletion_marker is not None
            ConfigResetOperation.model_validate_json(
                interrupted.model_copy(
                    update={
                        "targets": (
                            target.model_copy(
                                update={"deletion_marker": deletion_marker.model_copy(update=marker_update)},
                            ),
                        ),
                    },
                ).model_dump_json(),
            )

        with pytest.raises(ValidationError, match="operation id does not match its journal"):
            _rebuilt_with({"operation_id": "b" * 64})

        with pytest.raises(ValidationError, match="bucket id does not match its reset target"):
            _rebuilt_with({"bucket_id": "99999999-9999-4999-8999-999999999999"})
