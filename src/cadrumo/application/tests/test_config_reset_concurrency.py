"""Real-process exclusion and recheck proofs for durable config reset."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from textwrap import dedent

import pytest

from .test_config_reset import (
    _OVERRIDE_REASON,
    _PROFILE_A_ID,
    _PROFILE_B_ID,
    _create_profile,
    _fingerprint,
    _isolated_reset_root,
    _persist_filing,
)
from .test_config_reset_recovery import _SETTINGS_PREAMBLE, _child_env

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LOCK_TIMEOUT_SECONDS = 15.0
_MUTATION_TIMEOUT_SECONDS = 1.0
_BUSY_EXIT_CODE = 73
_WRITER_REFUSED_EXIT_CODE = 74
_CONFIRMATION_EXIT_CODE = 75
_EXCLUSION_EXIT_CODE = 76

_LOCK_HOLDER_HARNESS = dedent(
    """
    import sys
    from pathlib import Path

    from cadrumo.adapters.persistence.storage.bucket import (
        acquire_lock,
        bucket_paths,
        release_lock,
    )

    root = Path(sys.argv[1])
    paths = bucket_paths(root, sys.argv[2])
    acquire_lock(paths)
    try:
        print("READY", flush=True)
        sys.stdin.readline()
    finally:
        release_lock(paths)
    """,
)

_BLOCKED_RESET_HARNESS = _SETTINGS_PREAMBLE + dedent(
    """
    import json
    import time

    from cadrumo.adapters.persistence.storage.bucket import BucketBusyError
    from cadrumo.application.config_reset import start_config_reset

    config_module.settings_override.reset(token)
    settings = settings.model_copy(
        update={
            "cadrumo_file_lock_timeout_s": float(sys.argv[2]),
            "cadrumo_bucket_lock_poll_interval_s": 0.01,
        },
    )
    token = config_module.settings_override.set(settings)
    started = time.monotonic()
    try:
        start_config_reset(confirmed=True)
    except BucketBusyError as exc:
        print(
            json.dumps(
                {
                    "bucket_id": exc.bucket_id,
                    "elapsed": time.monotonic() - started,
                },
            ),
        )
        raise SystemExit(73) from exc
    finally:
        config_module.settings_override.reset(token)
    raise RuntimeError("reset unexpectedly acquired every target lock")
    """,
)

# The writer this harness runs is an AUTH revocation, not the retired bucket
# rename it was first written against. The rename verb went with the read-only
# narrowing of bucket maintenance, and nothing replaced it: the surviving
# label mutation is a custody transaction taking the custody lock, not the
# per-bucket lockfile, so it could not prove this exclusion at all. Auth
# revocation is the writer that still enters a named bucket through
# ``auth_mutation_span``, which is the same per-bucket lockfile a reset holds
# across its targets -- so the exclusion the test asserts is the real one and
# not a lock the reset happens to share with itself.
#
# The session is opened first because auth revocation refuses outright without
# one: the browser session it revokes is an encrypted row inside the bucket.
# Opening it is what makes this a genuine write attempt rather than a refusal
# that would pass the busy assertion for the wrong reason.
_WRITER_HARNESS = _SETTINGS_PREAMBLE + dedent(
    """
    import json
    import time

    from cadrumo.adapters.persistence.storage.bucket import BucketBusyError
    from cadrumo.application.auth.operator import reset_operator_auth
    from cadrumo.tests.profile_capsule import open_test_profile_session

    config_module.settings_override.reset(token)
    settings = settings.model_copy(
        update={
            "cadrumo_file_lock_timeout_s": float(sys.argv[3]),
            "cadrumo_bucket_lock_poll_interval_s": 0.01,
        },
    )
    token = config_module.settings_override.set(settings)
    started = time.monotonic()
    try:
        with open_test_profile_session(sys.argv[2]):
            reset_operator_auth(all_providers=True, target_bucket_id=sys.argv[2])
    except BucketBusyError as exc:
        print(
            json.dumps(
                {
                    "bucket_id": exc.bucket_id,
                    "elapsed": time.monotonic() - started,
                },
            ),
        )
        raise SystemExit(74) from exc
    else:
        raise RuntimeError("application writer unexpectedly entered the reset-owned bucket")
    finally:
        config_module.settings_override.reset(token)
    """,
)

_START_HARNESS = _SETTINGS_PREAMBLE + dedent(
    """
    from cadrumo.application.config_reset import start_config_reset

    try:
        operation = start_config_reset(confirmed=True)
        print(operation.model_dump_json())
    finally:
        config_module.settings_override.reset(token)
    """,
)

_EXCLUDED_START_HARNESS = _SETTINGS_PREAMBLE + dedent(
    """
    from cadrumo.application.config_reset import (
        ConfigResetAlreadyRunningError,
        start_config_reset,
    )

    try:
        start_config_reset(confirmed=True)
    except ConfigResetAlreadyRunningError as exc:
        print(exc.context["operation_id"])
        raise SystemExit(76) from exc
    finally:
        config_module.settings_override.reset(token)
    raise RuntimeError("overlapping reset start unexpectedly succeeded")
    """,
)

_RESUME_HARNESS = _SETTINGS_PREAMBLE + dedent(
    """
    from cadrumo.application.config_reset import (
        ConfigResetConfirmationRequiredError,
        resume_config_reset,
    )

    operation_id = sys.argv[2]
    confirmed = sys.argv[3] == "yes"
    override = sys.argv[4] == "yes"
    reason = sys.argv[5] or None
    try:
        operation = resume_config_reset(
            operation_id,
            confirmed=confirmed,
            acknowledge_retention_override=override,
            retention_override_reason=reason,
        )
        print(operation.model_dump_json())
    except ConfigResetConfirmationRequiredError as exc:
        print("CONFIRMATION_REQUIRED")
        raise SystemExit(75) from exc
    finally:
        config_module.settings_override.reset(token)
    """,
)


def _release_parent_bucket_handles(root: Path) -> None:
    """Drop this process's database handles before a child touches the store.

    The child is a FRESH process, which is the whole point of these cases: it
    resumes a reset the way a real one does. But this process created the
    profiles, so its engine cache still holds their SQLite files open, and a
    reset renaming a bucket directory is refused while another process has a
    file inside it open. That refusal is an artefact of the harness, not of the
    scenario -- no real operator has a second process sitting on the capsule --
    so the handles are released here rather than left to disguise themselves as
    a reset defect.
    """
    from ...adapters.persistence.storage.sql.engine import dispose_engines_for_bucket
    from ...adapters.persistence.storage.storage_path_definitions import BUCKETS_DIRNAME

    buckets = root / BUCKETS_DIRNAME
    if not buckets.is_dir():
        return
    for entry in buckets.iterdir():
        if entry.is_dir():
            dispose_engines_for_bucket(entry.name)


def _run_child(
    root: Path,
    harness: str,
    *args: str,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    _release_parent_bucket_handles(root)
    return subprocess.run(  # noqa: S603 - fixed interpreter and repository-owned harness
        [sys.executable, "-c", harness, str(root), *args],
        cwd=Path.cwd(),
        env=_child_env(root),
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=90,
    )


def test_sorted_target_locks_pause_reset_and_exclude_a_real_application_writer(
    tmp_path: Path,
) -> None:
    from ...adapters.persistence.storage.bucket.directory_layout import bucket_paths
    from ...adapters.persistence.storage.bucket.lockfile import lock_path
    from ...core.bucket_pointer import pointer_path
    from .._config_reset_repository import ConfigResetJournalRepository
    from ..workflow.profile_bucket_scan import read_profile_bucket_by_id

    with _isolated_reset_root(tmp_path) as root:
        _create_profile(_PROFILE_A_ID, label="Alpha operator", tax_id="00000000T")
        _create_profile(_PROFILE_B_ID, label="Beta operator", tax_id="00000001R")
        pointer_before = pointer_path(root).read_bytes()
        fingerprints_before = {
            _PROFILE_A_ID: _fingerprint(_PROFILE_A_ID),
            _PROFILE_B_ID: _fingerprint(_PROFILE_B_ID),
        }
        profile_a_before = read_profile_bucket_by_id(_PROFILE_A_ID)
        assert profile_a_before is not None
        profile_a_lock = lock_path(bucket_paths(root, _PROFILE_A_ID))
        holder = subprocess.Popen(  # noqa: S603 - fixed interpreter and repository-owned harness
            [
                sys.executable,
                "-c",
                _LOCK_HOLDER_HARNESS,
                str(root),
                _PROFILE_B_ID,
            ],
            cwd=Path.cwd(),
            env=_child_env(root),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        reset: subprocess.Popen[str] | None = None
        try:
            assert holder.stdout is not None
            assert holder.stdout.readline().strip() == "READY"
            reset_started = time.monotonic()
            reset = subprocess.Popen(  # noqa: S603 - fixed interpreter and repository-owned harness
                [
                    sys.executable,
                    "-c",
                    _BLOCKED_RESET_HARNESS,
                    str(root),
                    str(_LOCK_TIMEOUT_SECONDS),
                ],
                cwd=Path.cwd(),
                env=_child_env(root),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            deadline = time.monotonic() + 20
            while not profile_a_lock.is_file() and time.monotonic() < deadline:
                if reset.poll() is not None:
                    break
                time.sleep(0.01)
            assert profile_a_lock.is_file()
            assert reset.poll() is None

            writer = _run_child(
                root,
                _WRITER_HARNESS,
                _PROFILE_A_ID,
                str(_MUTATION_TIMEOUT_SECONDS),
            )
            assert writer.returncode == _WRITER_REFUSED_EXIT_CODE, writer.stderr
            writer_payload = json.loads(writer.stdout)
            assert writer_payload["bucket_id"] == _PROFILE_A_ID
            assert writer_payload["elapsed"] >= _MUTATION_TIMEOUT_SECONDS
            assert writer_payload["elapsed"] < _LOCK_TIMEOUT_SECONDS
            assert reset.poll() is None

            reset_stdout, reset_stderr = reset.communicate(timeout=30)
            reset_payload = json.loads(reset_stdout)
            observed_reset_elapsed = time.monotonic() - reset_started
            assert reset.returncode == _BUSY_EXIT_CODE, reset_stderr
            assert reset_payload["bucket_id"] == _PROFILE_B_ID
            assert reset_payload["elapsed"] >= _LOCK_TIMEOUT_SECONDS
            assert observed_reset_elapsed >= _LOCK_TIMEOUT_SECONDS
        finally:
            if reset is not None and reset.poll() is None:
                reset.terminate()
                reset.wait(timeout=15)
            if holder.stdin is not None and holder.poll() is None:
                holder.stdin.write("\n")
                holder.stdin.flush()
            try:
                holder.communicate(timeout=15)
            except subprocess.TimeoutExpired:
                holder.terminate()
                holder.wait(timeout=15)

        assert profile_a_lock.exists() is False
        assert ConfigResetJournalRepository().latest() is None
        assert pointer_path(root).read_bytes() == pointer_before
        assert {
            _PROFILE_A_ID: _fingerprint(_PROFILE_A_ID),
            _PROFILE_B_ID: _fingerprint(_PROFILE_B_ID),
        } == fingerprints_before
        profile_a_after = read_profile_bucket_by_id(_PROFILE_A_ID)
        assert profile_a_after is not None
        assert profile_a_after.label == profile_a_before.label


def test_fresh_process_reset_exclusion_retention_recheck_and_renewed_confirmation(
    tmp_path: Path,
) -> None:
    from ...adapters.persistence.storage.bucket.directory_layout import bucket_paths
    from .._config_reset_repository import ConfigResetJournalRepository
    from ..config_reset_models import (
        ConfigResetOperation,
        ConfigResetOperationStatus,
        ConfigResetPauseReason,
    )

    with _isolated_reset_root(tmp_path) as root:
        _create_profile(_PROFILE_A_ID, label="Alpha operator", tax_id="00000000T")
        _persist_filing(_PROFILE_A_ID, filing_year=2025, seed="a")

        started = _run_child(root, _START_HARNESS, check=True)
        operation = ConfigResetOperation.model_validate_json(started.stdout)
        assert operation.status is ConfigResetOperationStatus.PAUSED
        assert operation.pause_reason is ConfigResetPauseReason.RETENTION_UNRESOLVED
        repository = ConfigResetJournalRepository()
        journal_path = repository.path_for(operation.operation_id)
        before_excluded_start = journal_path.read_bytes()

        excluded = _run_child(root, _EXCLUDED_START_HARNESS)
        assert excluded.returncode == _EXCLUSION_EXIT_CODE
        assert excluded.stdout.strip() == operation.operation_id
        assert journal_path.read_bytes() == before_excluded_start

        original_fingerprint = operation.targets[0].fingerprint
        original_retention = operation.targets[0].retention
        assert original_fingerprint is not None
        assert original_retention is not None
        _persist_filing(_PROFILE_A_ID, filing_year=2024, seed="2")
        # The filing grows the retained set, which is what the retention
        # recheck below asserts -- but it does NOT move the capsule digest: it
        # lands in the database, which the inventory covers by path only, and
        # in a retention snapshot outside the capsule. The target-changed pause
        # this case also asserts needs a change the digest actually sees, so
        # the capsule itself is perturbed here as well.
        (bucket_paths(root, _PROFILE_A_ID).bucket_dir / "planted.v1.json").write_bytes(b'{"planted": true}')

        before_unconfirmed_recheck = journal_path.read_bytes()
        unconfirmed = _run_child(
            root,
            _RESUME_HARNESS,
            operation.operation_id,
            "no",
            "yes",
            _OVERRIDE_REASON,
        )
        assert unconfirmed.returncode == _CONFIRMATION_EXIT_CODE
        assert unconfirmed.stdout.strip() == "CONFIRMATION_REQUIRED"
        assert journal_path.read_bytes() == before_unconfirmed_recheck

        changed_process = _run_child(
            root,
            _RESUME_HARNESS,
            operation.operation_id,
            "yes",
            "yes",
            _OVERRIDE_REASON,
            check=True,
        )
        changed = ConfigResetOperation.model_validate_json(changed_process.stdout)
        assert changed.status is ConfigResetOperationStatus.PAUSED
        assert changed.pause_reason is ConfigResetPauseReason.TARGET_STATE_CHANGED
        assert changed.targets[0].fingerprint is not None
        assert changed.targets[0].fingerprint.digest != original_fingerprint.digest
        assert changed.targets[0].retention is not None
        assert changed.targets[0].retention.retained_record_count == (original_retention.retained_record_count + 1)
        assert bucket_paths(root, _PROFILE_A_ID).bucket_dir.is_dir()

        before_renewed_confirmation = journal_path.read_bytes()
        renewed = _run_child(
            root,
            _RESUME_HARNESS,
            operation.operation_id,
            "no",
            "yes",
            _OVERRIDE_REASON,
        )
        assert renewed.returncode == _CONFIRMATION_EXIT_CODE
        assert renewed.stdout.strip() == "CONFIRMATION_REQUIRED"
        assert journal_path.read_bytes() == before_renewed_confirmation

        retention_process = _run_child(
            root,
            _RESUME_HARNESS,
            operation.operation_id,
            "yes",
            "no",
            "",
            check=True,
        )
        retention_paused = ConfigResetOperation.model_validate_json(retention_process.stdout)
        assert retention_paused.status is ConfigResetOperationStatus.PAUSED
        assert retention_paused.pause_reason is ConfigResetPauseReason.RETENTION_UNRESOLVED

        completed_process = _run_child(
            root,
            _RESUME_HARNESS,
            operation.operation_id,
            "yes",
            "yes",
            _OVERRIDE_REASON,
            check=True,
        )
        completed = ConfigResetOperation.model_validate_json(completed_process.stdout)
        assert completed.status is ConfigResetOperationStatus.COMPLETE
        assert completed.summary is not None
        assert completed.summary.retention_override_count == 1
        assert bucket_paths(root, _PROFILE_A_ID).bucket_dir.exists() is False
        assert repository.load(operation.operation_id) == completed
