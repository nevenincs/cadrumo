"""Real current-capsule authentication and A-to-B handover coverage.

Every profile in this module is registered through the production credential
door, then unlocked through the public login service against an isolated real
storage root.  No substitute custody provider or synthetic session is used.
"""

from __future__ import annotations

import json
import os
import shutil
import time
from contextvars import Token
from datetime import UTC, datetime, timedelta
from multiprocessing import get_context
from multiprocessing.queues import Queue
from multiprocessing.synchronize import Event
from pathlib import Path
from threading import Event as ThreadEvent
from threading import Thread
from typing import TypedDict
from uuid import UUID

import pytest
from sqlalchemy.exc import DatabaseError as SqlDatabaseError

from cadrumo.application.user_profile import profile_current_bucket_session, profile_session_path

from ....adapters.persistence.storage.custody import (
    PROFILE_CUSTODY_SENTINEL_FILENAME,
    ProfileCustodyPasswordError,
    ProfileCustodyRecordError,
    compare_and_replace_same_or_predecessor_profile_custody_local_record,
    load_committed_profile_password_material,
    resume_profile_session,
)
from ....core import (
    BucketPointer,
    ProfileSessionRefusalReason,
    capture_pointer,
    iter_directory,
    read_pointer,
    write_pointer,
)
from ....core import config as config_module
from ....core.config import Settings
from ....core.time import now as _now
from ....domain.buckets import BucketEventHistoryPersistenceError
from ....tests.secure_sql import isolated_profile_storage_root
from .._login_session import (
    _HANDOVER_JOURNAL_MAX_BYTES,
    _clear_handover_journal,
    _handover_journal_path,
    _HandoverPhase,
    _load_handover_journal,
    _ProfileLoginHandoverJournal,
    _save_handover_journal,
    login_profile,
)
from .._profile_pointer_transaction import ActiveProfilePointerTransactionError
from .._profile_record_repository import close_active_profile_record_session, require_profile_record_session
from .._registration import register_profile_with_credentials

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_PASSWORD_A = "login-handover-password-a"  # noqa: S105 - real test credential
_PASSWORD_B = "login-handover-password-b"  # noqa: S105 - real test credential


class _ConflictResult(TypedDict, total=False):
    active_bucket: str
    record_profile: str
    same_live: bool
    same_record: bool
    unexpected_success: bool


class _AccelerationResult(TypedDict):
    active_bucket: str | None
    pointer: bytes | None
    session_persisted: bool


class _RecoveryResult(TypedDict):
    active_bucket: str
    outcome_bucket: str
    record_profile: str


class _ChildLoginResult(TypedDict):
    bucket_id: str
    closed_previous: str | None
    already_authenticated: bool


class _ResumeProbeResult(TypedDict):
    resumed: bool
    dek_length: int
    refusal: str | None


def _register_two_profiles(storage_root: Path) -> tuple[str, str]:
    first = register_profile_with_credentials(label="Handover A", passphrase=_PASSWORD_A)
    second = register_profile_with_credentials(label="Handover B", passphrase=_PASSWORD_B)
    return first.profile_id, second.profile_id


def _close_live_login() -> None:
    from cadrumo.application.user_profile import profile_close_bucket_session

    close_active_profile_record_session()
    profile_close_bucket_session()


def _child_settings(storage_root: Path) -> tuple[Settings, Token[Settings | None]]:
    # Calibration measurement is off for the same reason the session default in
    # `cadrumo/conftest.py` turns it off, and it has to be said again HERE:
    # these children are spawned, so no in-process override reaches them, and
    # `_env_file=None` means no environment default would either. The child
    # rebuilds `Settings` from scratch and would otherwise re-measure the KDF
    # grid -- 16.1s of supervised child processes -- once per spawned
    # registration, for the answer the parent already has.
    #
    # Declining adopts the fixed fallback `calibrate_profile_kdf` also returns
    # on deadline, which is stronger than the measured band's floor, so the
    # custody envelope these children write is wrapped no more weakly.
    settings = Settings(
        _env_file=None,
        cadrumo_local_storage_root=storage_root,
        cadrumo_active_profile=None,
        cadrumo_profile_kdf_measure_calibration=False,
    )
    return settings, config_module._settings_override.set(settings)


def _close_child_login(token: Token[Settings | None]) -> None:
    _close_live_login()
    config_module._settings_override.reset(token)


def _prepared_handover_journal() -> _ProfileLoginHandoverJournal:
    """Build a real v1 witness through the production journal constructor."""
    return _ProfileLoginHandoverJournal.prepare(
        profile_a="journal-profile-a",
        profile_b="journal-profile-b",
        pointer_before=b"active-profile-a",
        pointer_after=b"active-profile-b",
        activation_at=datetime(2026, 8, 14, 9, 30, tzinfo=UTC),
    )


def _replace_journal_in_child(path_text: str, payload: bytes, result_queue: Queue[str]) -> None:
    """Substitute one leaf in an independent interpreter without app cooperation."""
    path = Path(path_text)
    replacement = path.with_name(f".{path.name}.replacement")
    replacement.write_bytes(payload)
    os.replace(replacement, path)
    result_queue.put("replaced")


def _replace_journal_after_cas_stage_appears(
    path_text: str,
    payload: bytes,
    ready: Event,
    result_queue: Queue[str],
) -> None:
    """Replace the real leaf after the custody CAS has captured its expected bytes."""
    path = Path(path_text)
    stage_prefix = f".{path.name}.cas-stage."
    ready.set()
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if any(entry.name.startswith(stage_prefix) for entry in iter_directory(path.parent)):
            replacement = path.with_name(f".{path.name}.interleaving-replacement")
            replacement.write_bytes(payload)
            os.replace(replacement, path)
            result_queue.put("replaced-after-capture")
            return
    result_queue.put("missed-cas-stage")


def _block_idempotent_journal_cleanup_after_publication(
    path_text: str,
    predecessor: bytes,
    watching: Event,
    ready: Event,
    release: Event,
    result_queue: Queue[str],
) -> None:
    """Make only post-publication predecessor cleanup unavailable in a child.

    Windows keeps the deterministic ReplaceFileW backup open without DELETE
    sharing. POSIX removes directory write permission only after the exchanged
    backup has the predecessor bytes, so the receipt target is already current.
    """
    path = Path(path_text)
    backup_name = f".{path.name}.cas-idempotent-backup"
    deadline = time.monotonic() + 30
    original_mode: int | None = None
    handle = None
    try:
        watching.set()
        while time.monotonic() < deadline:
            if os.name == "nt":
                backup = path.with_name(backup_name)
                if backup.exists():
                    handle = backup.open("rb")
                    ready.set()
                    if not release.wait(30):
                        result_queue.put("release-timeout")
                        return
                    result_queue.put("released")
                    return
            else:
                backup = path.with_name(backup_name)
                try:
                    if not backup.exists() or backup.read_bytes() != predecessor:
                        time.sleep(0.001)
                        continue
                except OSError:
                    continue
                original_mode = path.parent.stat().st_mode
                os.chmod(path.parent, original_mode & ~0o222)
                ready.set()
                if not release.wait(30):
                    result_queue.put("release-timeout")
                    return
                result_queue.put("released")
                return
            time.sleep(0.001)
        result_queue.put("missed-post-publication-cleanup")
    finally:
        if original_mode is not None:
            os.chmod(path.parent, original_mode)
        if handle is not None:
            handle.close()


def _read_journal_phase_without_blocking_replace(path: Path) -> str:
    """Observe a Windows journal while allowing its real atomic replacement.

    Python's ordinary file reader does not share DELETE access on Windows,
    so merely observing a live journal can make ``os.replace`` fail.  This
    opens the real file with Windows read/write/delete sharing; no production
    writer, test double, or source mutation is involved.
    """
    if os.name != "nt":
        payload = json.loads(path.read_text(encoding="utf-8"))
        phase = payload["phase"]
        assert isinstance(phase, str)
        return phase
    import ctypes
    import msvcrt
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    kernel32.CreateFileW.restype = wintypes.HANDLE
    handle = kernel32.CreateFileW(
        str(path),
        0x80000000,  # GENERIC_READ
        0x00000001 | 0x00000002 | 0x00000004,  # FILE_SHARE_READ|WRITE|DELETE
        None,
        3,  # OPEN_EXISTING
        0x00000080,  # FILE_ATTRIBUTE_NORMAL
        None,
    )
    if handle == ctypes.c_void_p(-1).value:
        raise OSError(ctypes.get_last_error(), "CreateFileW failed while observing handover journal")
    descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    try:
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 4096):
            chunks.append(chunk)
    finally:
        os.close(descriptor)
    payload = json.loads(b"".join(chunks))
    phase = payload["phase"]
    assert isinstance(phase, str)
    return phase


def _conflicted_b_handover_child(
    storage_root: Path,
    profile_a: str,
    profile_b: str,
    candidate_ready: Event,
    allow_authentication: Event,
    result_queue: Queue[_ConflictResult],
) -> None:
    """Keep A locally active while a separate process rewrites the pointer."""
    settings, token = _child_settings(storage_root)
    _ = settings
    try:
        login_profile(name=profile_a, passphrase_callback=lambda: _PASSWORD_A)
        active_a = profile_current_bucket_session()
        record_a = require_profile_record_session(profile_a)

        def candidate_password() -> str:
            candidate_ready.set()
            if not allow_authentication.wait(30):
                raise TimeoutError("parent did not release candidate authentication")
            return _PASSWORD_B

        try:
            login_profile(name=profile_b, passphrase_callback=candidate_password)
        except ActiveProfilePointerTransactionError:
            active_after_conflict = profile_current_bucket_session()
            assert active_after_conflict is not None
            result_queue.put(
                {
                    "active_bucket": active_after_conflict.bucket_id,
                    "record_profile": str(require_profile_record_session(profile_a).profile_id),
                    "same_live": profile_current_bucket_session() is active_a,
                    "same_record": require_profile_record_session(profile_a) is record_a,
                }
            )
        else:
            result_queue.put({"unexpected_success": True})
    finally:
        _close_child_login(token)


def _acceleration_failure_handover_child(
    storage_root: Path,
    profile_a: str,
    profile_b: str,
    result_queue: Queue[_AccelerationResult],
) -> None:
    """Use keyring's real failing backend in a fresh process only."""
    os.environ["PYTHON_KEYRING_BACKEND"] = "keyring.backends.fail.Keyring"
    settings, token = _child_settings(storage_root)
    _ = settings
    try:
        login_profile(name=profile_a, passphrase_callback=lambda: _PASSWORD_A)
        result = login_profile(name=profile_b, passphrase_callback=lambda: _PASSWORD_B)
        active = profile_current_bucket_session()
        result_queue.put(
            {
                "active_bucket": active.bucket_id if active is not None else None,
                "pointer": capture_pointer(storage_root),
                "session_persisted": result.session_persisted,
            }
        )
    finally:
        _close_child_login(token)


def _crash_after_b_handover_child(storage_root: Path, profile_a: str, profile_b: str) -> None:
    """Terminate after committed B handover without normal process cleanup."""
    settings, _token = _child_settings(storage_root)
    _ = settings
    login_profile(name=profile_a, passphrase_callback=lambda: _PASSWORD_A)
    login_profile(name=profile_b, passphrase_callback=lambda: _PASSWORD_B)
    os._exit(0)


def _recover_selected_profile_child(
    storage_root: Path,
    profile_b: str,
    result_queue: Queue[_RecoveryResult],
) -> None:
    """Authenticate the durable pointer target in a fresh process after a crash."""
    settings, token = _child_settings(storage_root)
    _ = settings
    try:
        result = login_profile(name=None, passphrase_callback=lambda: _PASSWORD_B)
        active = profile_current_bucket_session()
        assert active is not None
        result_queue.put(
            {
                "active_bucket": active.bucket_id,
                "outcome_bucket": result.bucket_id,
                "record_profile": str(require_profile_record_session(profile_b).profile_id),
            }
        )
    finally:
        _close_child_login(token)


def _login_in_separate_process_child(
    storage_root: Path,
    profile: str,
    password: str,
    now: datetime | None,
    result_queue: Queue[_ChildLoginResult],
) -> None:
    """Authenticate one profile the way an operator invocation does: a fresh process."""
    settings, token = _child_settings(storage_root)
    _ = settings
    try:
        outcome = login_profile(name=profile, now=now, passphrase_callback=lambda: password)
        result_queue.put(
            {
                "bucket_id": outcome.bucket_id,
                "closed_previous": outcome.closed_previous_bucket_id,
                "already_authenticated": outcome.already_authenticated,
            }
        )
    finally:
        _close_child_login(token)


def _resume_probe_child(
    storage_root: Path,
    profile: str,
    result_queue: Queue[_ResumeProbeResult],
) -> None:
    """Recover one profile's session material with no passphrase, in its own process."""
    settings, token = _child_settings(storage_root)
    _ = settings
    try:
        material = load_committed_profile_password_material(UUID(profile), root=storage_root)
        outcome, dek = resume_profile_session(
            storage_root=storage_root,
            profile_id=UUID(profile),
            custody_generation=material.envelope.password_generation,
            dek_epoch=material.envelope.dek_epoch,
            now=_now(),
        )
        result_queue.put(
            {
                "resumed": outcome.resumed,
                "dek_length": 0 if dek is None else len(dek),
                "refusal": None if outcome.refusal is None else outcome.refusal.value,
            }
        )
    finally:
        _close_child_login(token)


def _login_in_separate_process(
    storage_root: Path,
    profile: str,
    password: str,
    *,
    now: datetime | None = None,
) -> _ChildLoginResult:
    """Run one login in its own interpreter, which is what every ``aeat`` call is."""
    context = get_context("spawn")
    result_queue: Queue[_ChildLoginResult] = context.Queue()
    child = context.Process(
        target=_login_in_separate_process_child,
        args=(storage_root, profile, password, now, result_queue),
    )
    child.start()
    try:
        result = result_queue.get(timeout=180)
        child.join(timeout=30)
        assert child.exitcode == 0
        return result
    finally:
        if child.is_alive():
            child.terminate()
            child.join(timeout=30)


def _probe_resumable_session(storage_root: Path, profile: str) -> _ResumeProbeResult:
    """Measure recovered key material from a process that never held the session."""
    context = get_context("spawn")
    result_queue: Queue[_ResumeProbeResult] = context.Queue()
    child = context.Process(target=_resume_probe_child, args=(storage_root, profile, result_queue))
    child.start()
    try:
        result = result_queue.get(timeout=180)
        child.join(timeout=30)
        assert child.exitcode == 0
        return result
    finally:
        if child.is_alive():
            child.terminate()
            child.join(timeout=30)


def _assert_no_resumable_material(storage_root: Path, profile: str, *, after: str) -> None:
    """Refuse every route by which a retired profile's DEK is still recoverable."""
    probe = _probe_resumable_session(storage_root, profile)
    assert probe["dek_length"] == 0, (
        f"after {after}: the retired profile's DEK is still recoverable without its passphrase"
    )
    assert probe["resumed"] is False
    assert probe["refusal"] == ProfileSessionRefusalReason.ABSENT.value


def _crash_at_handover_phase_child(
    storage_root: Path,
    profile_a: str,
    profile_b: str,
    phase: _HandoverPhase,
) -> None:
    """Crash the real handover process immediately after one durable receipt.

    The observation rides on the exit status rather than on a file the child
    writes: exit 0 is reached only from a death at the exact target phase, and
    exit 1 from a handover that ran to completion without one. Recording the
    observation first put a filesystem write between seeing the phase and
    dying, which is long enough for the remaining handover work to finish --
    leaving a test named for a crash that never happened, and a retirement that
    silently did run.
    """
    settings, token = _child_settings(storage_root)
    _ = settings
    stop_watcher = ThreadEvent()

    def crash_after_phase_receipt() -> None:
        journal_path = _handover_journal_path(storage_root)
        deadline = time.monotonic() + 120
        while not stop_watcher.is_set() and time.monotonic() < deadline:
            if journal_path.is_file():
                try:
                    observed_phase = _read_journal_phase_without_blocking_replace(journal_path)
                except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                    time.sleep(0.001)
                    continue
                if observed_phase == phase.value:
                    os._exit(0)
            time.sleep(0.001)

    try:
        login_profile(name=profile_a, passphrase_callback=lambda: _PASSWORD_A)
        if phase is _HandoverPhase.A_RETIRED:
            # There is intentionally no production work after the terminal
            # receipt. Crash at the next instruction, after verifying that
            # exact durable boundary, rather than race a watcher against a
            # return path with no further scheduling point.
            login_profile(name=profile_b, passphrase_callback=lambda: _PASSWORD_B)
            payload = json.loads(_handover_journal_path(storage_root).read_text(encoding="utf-8"))
            if payload["phase"] != phase.value:
                os._exit(1)
            os._exit(0)
        watcher: Thread | None = None

        def begin_b_authentication() -> str:
            nonlocal watcher
            watcher = Thread(target=crash_after_phase_receipt, daemon=True)
            watcher.start()
            return _PASSWORD_B

        login_profile(name=profile_b, passphrase_callback=begin_b_authentication)
        stop_watcher.set()
        if watcher is not None:
            watcher.join(timeout=5)
        os._exit(1)
    finally:
        _close_child_login(token)


def test_handover_journal_roundtrips_through_the_anchored_bounded_record_store(tmp_path: Path) -> None:
    """The journal has one bounded canonical form and a real anchored clear."""
    storage_root = tmp_path / "handover-root"
    storage_root.mkdir()
    prepared = _prepared_handover_journal()

    _save_handover_journal(storage_root=storage_root, journal=prepared)

    path = _handover_journal_path(storage_root)
    assert path.read_bytes() == prepared.canonical_json_bytes()
    assert _load_handover_journal(storage_root=storage_root) == prepared

    _clear_handover_journal(storage_root=storage_root, journal=prepared)

    assert _load_handover_journal(storage_root=storage_root) is None


def test_handover_journal_duplicate_prepared_receipt_is_an_identity_preserving_noop(tmp_path: Path) -> None:
    """Re-saving the first durable receipt neither replaces nor clears it."""
    storage_root = tmp_path / "handover-root"
    storage_root.mkdir()
    prepared = _prepared_handover_journal()

    _save_handover_journal(storage_root=storage_root, journal=prepared)

    path = _handover_journal_path(storage_root)
    before = path.stat()
    before_identity = (before.st_dev, before.st_ino)
    before_bytes = path.read_bytes()
    _save_handover_journal(storage_root=storage_root, journal=prepared)

    after = path.stat()
    assert (after.st_dev, after.st_ino) == before_identity
    assert path.read_bytes() == before_bytes == prepared.canonical_json_bytes()
    assert _load_handover_journal(storage_root=storage_root) == prepared


def test_handover_journal_duplicate_later_phase_receipt_is_an_identity_preserving_noop(tmp_path: Path) -> None:
    """A complete later phase can be replayed without regressing or replacing it."""
    storage_root = tmp_path / "handover-root"
    storage_root.mkdir()
    prepared = _prepared_handover_journal()
    published = prepared.at_phase(_HandoverPhase.POINTER_PUBLISHED)
    _save_handover_journal(storage_root=storage_root, journal=prepared)
    _save_handover_journal(storage_root=storage_root, journal=published)

    path = _handover_journal_path(storage_root)
    before = path.stat()
    before_identity = (before.st_dev, before.st_ino)
    before_bytes = path.read_bytes()
    _save_handover_journal(storage_root=storage_root, journal=published)

    after = path.stat()
    assert (after.st_dev, after.st_ino) == before_identity
    assert path.read_bytes() == before_bytes == published.canonical_json_bytes()
    assert _load_handover_journal(storage_root=storage_root) == published


def test_handover_journal_retry_converges_after_postpublication_cleanup_refusal(tmp_path: Path) -> None:
    """A retry removes only the verified predecessor backup after a real cleanup refusal."""
    storage_root = tmp_path / "handover-root"
    storage_root.mkdir()
    prepared = _prepared_handover_journal()
    published = prepared.at_phase(_HandoverPhase.POINTER_PUBLISHED)
    _save_handover_journal(storage_root=storage_root, journal=prepared)

    path = _handover_journal_path(storage_root)
    compare_and_replace_same_or_predecessor_profile_custody_local_record(
        path,
        current=published.canonical_json_bytes(),
        predecessor=prepared.canonical_json_bytes(),
        maximum_bytes=_HANDOVER_JOURNAL_MAX_BYTES,
    )
    assert path.with_name(f".{path.name}.cas-idempotent-backup").exists()

    context = get_context("spawn")
    watching = context.Event()
    ready = context.Event()
    release = context.Event()
    result_queue: Queue[str] = context.Queue()
    child = context.Process(
        target=_block_idempotent_journal_cleanup_after_publication,
        args=(
            str(path),
            prepared.canonical_json_bytes(),
            watching,
            ready,
            release,
            result_queue,
        ),
    )
    failures: list[BaseException] = []

    def save_later_receipt() -> None:
        try:
            _save_handover_journal(storage_root=storage_root, journal=published)
        except BaseException as exc:
            failures.append(exc)

    child.start()
    assert watching.wait(30)
    worker = Thread(target=save_later_receipt, daemon=True)
    worker.start()
    try:
        assert ready.wait(30)
        worker.join(timeout=30)
        assert not worker.is_alive()
        assert len(failures) == 1
        assert isinstance(failures[0], ActiveProfilePointerTransactionError)

        assert path.read_bytes() == published.canonical_json_bytes()
        assert _load_handover_journal(storage_root=storage_root) == published

        release.set()
        assert result_queue.get(timeout=30) == "released"
        child.join(timeout=30)
        assert child.exitcode == 0

        _save_handover_journal(storage_root=storage_root, journal=published)

        assert _load_handover_journal(storage_root=storage_root) == published
        assert not path.with_name(f".{path.name}.cas-idempotent-backup").exists()
    finally:
        release.set()
        worker.join(timeout=30)
        if child.is_alive():
            child.terminate()
            child.join(timeout=30)


@pytest.mark.parametrize(
    "artifact",
    ("oversized", "noncanonical", "duplicate", "nonregular", "leaf_link", "parent_link"),
)
def test_handover_journal_refuses_noncurrent_filesystem_artifacts(tmp_path: Path, artifact: str) -> None:
    """Every journal read remains bounded and refuses links or noncanonical JSON."""
    storage_root = tmp_path / "handover-root"
    storage_root.mkdir()
    path = _handover_journal_path(storage_root)
    outside = tmp_path / "outside.json"
    outside.write_bytes(b"outside-journal-content")

    if artifact == "parent_link":
        redirected_parent = tmp_path / "redirected-journals"
        redirected_parent.mkdir()
        os.symlink(redirected_parent, path.parent, target_is_directory=True)
    else:
        path.parent.mkdir()
        if artifact == "oversized":
            path.write_bytes(b"x" * (_HANDOVER_JOURNAL_MAX_BYTES + 1))
        elif artifact == "noncanonical":
            path.write_bytes(_prepared_handover_journal().canonical_json_bytes() + b"\n")
        elif artifact == "duplicate":
            canonical = _prepared_handover_journal().canonical_json_bytes()
            path.write_bytes(canonical.replace(b'"phase":"prepared"', b'"phase":"prepared","phase":"prepared"'))
        elif artifact == "nonregular":
            path.mkdir()
        else:
            os.symlink(outside, path)

    with pytest.raises(ActiveProfilePointerTransactionError):
        _load_handover_journal(storage_root=storage_root)
    with pytest.raises(ActiveProfilePointerTransactionError):
        _save_handover_journal(storage_root=storage_root, journal=_prepared_handover_journal())

    assert outside.read_bytes() == b"outside-journal-content"


def test_handover_journal_clear_refuses_to_remove_a_replaced_noncanonical_leaf(tmp_path: Path) -> None:
    """Completion never unlinks a substitute after the prior trusted witness."""
    storage_root = tmp_path / "handover-root"
    storage_root.mkdir()
    prepared = _prepared_handover_journal()
    _save_handover_journal(storage_root=storage_root, journal=prepared)
    path = _handover_journal_path(storage_root)
    substitute = _prepared_handover_journal().canonical_json_bytes() + b" "
    path.write_bytes(substitute)

    with pytest.raises(ActiveProfilePointerTransactionError):
        _clear_handover_journal(storage_root=storage_root, journal=prepared)

    assert path.read_bytes() == substitute


def test_handover_journal_refuses_a_fresh_canonical_replacement_from_another_process(tmp_path: Path) -> None:
    """A child substitution cannot be mistaken for this root-locked transition."""
    storage_root = tmp_path / "handover-root"
    storage_root.mkdir()
    prepared = _prepared_handover_journal()
    _save_handover_journal(storage_root=storage_root, journal=prepared)
    replacement = _ProfileLoginHandoverJournal.prepare(
        profile_a="substituted-profile-a",
        profile_b="substituted-profile-b",
        pointer_before=b"substituted-a",
        pointer_after=b"substituted-b",
        activation_at=datetime(2026, 8, 14, 9, 31, tzinfo=UTC),
    )
    context = get_context("spawn")
    result_queue: Queue[str] = context.Queue()
    child = context.Process(
        target=_replace_journal_in_child,
        args=(str(_handover_journal_path(storage_root)), replacement.canonical_json_bytes(), result_queue),
    )
    child.start()
    try:
        assert result_queue.get(timeout=30) == "replaced"
        child.join(timeout=30)
        assert child.exitcode == 0

        with pytest.raises(ActiveProfilePointerTransactionError):
            _save_handover_journal(
                storage_root=storage_root,
                journal=prepared.at_phase(_HandoverPhase.POINTER_PUBLISHED),
            )

        assert _load_handover_journal(storage_root=storage_root) == replacement
    finally:
        if child.is_alive():
            child.terminate()
            child.join(timeout=30)


def test_handover_journal_cas_replace_restores_a_valid_sibling_substitute(tmp_path: Path) -> None:
    """A sibling leaf swap after CAS capture survives instead of being overwritten."""
    storage_root = tmp_path / "handover-root"
    storage_root.mkdir()
    prepared = _prepared_handover_journal()
    _save_handover_journal(storage_root=storage_root, journal=prepared)
    substitute = _ProfileLoginHandoverJournal.prepare(
        profile_a="interleaved-profile-a",
        profile_b="interleaved-profile-b",
        pointer_before=b"interleaved-a",
        pointer_after=b"interleaved-b",
        activation_at=datetime(2026, 8, 14, 9, 32, tzinfo=UTC),
    )
    context = get_context("spawn")
    ready = context.Event()
    result_queue: Queue[str] = context.Queue()
    child = context.Process(
        target=_replace_journal_after_cas_stage_appears,
        args=(str(_handover_journal_path(storage_root)), substitute.canonical_json_bytes(), ready, result_queue),
    )
    child.start()
    try:
        assert ready.wait(30)
        with pytest.raises(ActiveProfilePointerTransactionError):
            _save_handover_journal(
                storage_root=storage_root,
                journal=prepared.at_phase(_HandoverPhase.POINTER_PUBLISHED),
            )
        assert result_queue.get(timeout=30) == "replaced-after-capture"
        child.join(timeout=30)
        assert child.exitcode == 0
        assert _load_handover_journal(storage_root=storage_root) == substitute
    finally:
        if child.is_alive():
            child.terminate()
            child.join(timeout=30)


def test_handover_journal_cas_clear_refuses_and_preserves_a_valid_sibling_substitute(tmp_path: Path) -> None:
    """A canonical sibling replacement cannot be deleted by a stale clear intent."""
    storage_root = tmp_path / "handover-root"
    storage_root.mkdir()
    prepared = _prepared_handover_journal()
    _save_handover_journal(storage_root=storage_root, journal=prepared)
    substitute = _ProfileLoginHandoverJournal.prepare(
        profile_a="clear-interleaved-profile-a",
        profile_b="clear-interleaved-profile-b",
        pointer_before=b"clear-interleaved-a",
        pointer_after=b"clear-interleaved-b",
        activation_at=datetime(2026, 8, 14, 9, 33, tzinfo=UTC),
    )
    context = get_context("spawn")
    result_queue: Queue[str] = context.Queue()
    child = context.Process(
        target=_replace_journal_in_child,
        args=(str(_handover_journal_path(storage_root)), substitute.canonical_json_bytes(), result_queue),
    )
    child.start()
    try:
        assert result_queue.get(timeout=30) == "replaced"
        child.join(timeout=30)
        assert child.exitcode == 0
        with pytest.raises(ActiveProfilePointerTransactionError):
            _clear_handover_journal(storage_root=storage_root, journal=prepared)
        assert _load_handover_journal(storage_root=storage_root) == substitute
    finally:
        if child.is_alive():
            child.terminate()
            child.join(timeout=30)


def test_wrong_b_password_leaves_active_a_and_pointer_bytes_intact(tmp_path: Path) -> None:
    """A rejected B password cannot change any active A handover authority."""
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        profile_a, profile_b = _register_two_profiles(storage_root)
        try:
            login_profile(name=profile_a, passphrase_callback=lambda: _PASSWORD_A)
            active_a = profile_current_bucket_session()
            record_a = require_profile_record_session(profile_a)
            pointer_a = capture_pointer(storage_root)

            with pytest.raises(ProfileCustodyPasswordError):
                login_profile(name=profile_b, passphrase_callback=lambda: "wrong-password-for-b")

            assert capture_pointer(storage_root) == pointer_a
            assert profile_current_bucket_session() is active_a
            assert require_profile_record_session(profile_a) is record_a
            assert not profile_session_path(storage_root=storage_root, profile_id=UUID(profile_b)).exists()
        finally:
            _close_live_login()


def test_invalid_b_candidate_material_leaves_active_a_and_pointer_bytes_intact(tmp_path: Path) -> None:
    """A malformed B custody artifact is refused before any A replacement."""
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        profile_a, profile_b = _register_two_profiles(storage_root)
        instant = datetime.now(UTC)
        try:
            login_profile(name=profile_a, now=instant, passphrase_callback=lambda: _PASSWORD_A)
            active_a = profile_current_bucket_session()
            record_a = require_profile_record_session(profile_a)
            pointer_a = capture_pointer(storage_root)
            sentinel_path = storage_root / "buckets" / profile_b / "data" / PROFILE_CUSTODY_SENTINEL_FILENAME
            sentinel_path.write_bytes(b"not-a-current-custody-sentinel")

            with pytest.raises(ProfileCustodyRecordError):
                login_profile(
                    name=profile_b,
                    now=instant + timedelta(seconds=3),
                    passphrase_callback=lambda: _PASSWORD_B,
                )

            assert capture_pointer(storage_root) == pointer_a
            assert profile_current_bucket_session() is active_a
            assert require_profile_record_session(profile_a) is record_a
            assert not profile_session_path(storage_root=storage_root, profile_id=UUID(profile_b)).exists()
        finally:
            _close_live_login()


def test_corrupt_b_activation_store_rolls_back_every_a_authority(tmp_path: Path) -> None:
    """B event-history unavailability is a handover failure, not post-A cleanup."""
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        profile_a, profile_b = _register_two_profiles(storage_root)
        try:
            login_profile(name=profile_a, passphrase_callback=lambda: _PASSWORD_A)
            active_a = profile_current_bucket_session()
            record_a = require_profile_record_session(profile_a)
            pointer_a = capture_pointer(storage_root)
            a_session_path = profile_session_path(storage_root=storage_root, profile_id=UUID(profile_a))
            a_session_before = a_session_path.read_bytes() if a_session_path.is_file() else None
            b_session_path = profile_session_path(storage_root=storage_root, profile_id=UUID(profile_b))
            database_path = storage_root / "buckets" / profile_b / "db" / "cadrumo.db"
            assert database_path.is_file(), "B must have the committed current event store registration created"
            database_path.write_bytes(b"corrupt-current-b-event-store")

            with pytest.raises((BucketEventHistoryPersistenceError, SqlDatabaseError)):
                login_profile(name=profile_b, passphrase_callback=lambda: _PASSWORD_B)

            assert capture_pointer(storage_root) == pointer_a
            assert profile_current_bucket_session() is active_a
            assert require_profile_record_session(profile_a) is record_a
            assert (a_session_path.read_bytes() if a_session_path.is_file() else None) == a_session_before
            assert not b_session_path.exists()
        finally:
            _close_live_login()


def test_successful_b_handover_publishes_before_retiring_a(tmp_path: Path) -> None:
    """B becomes pointer and process authority before A is retired."""
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        profile_a, profile_b = _register_two_profiles(storage_root)
        try:
            login_profile(name=profile_a, passphrase_callback=lambda: _PASSWORD_A)
            active_a = profile_current_bucket_session()

            result = login_profile(name=profile_b, passphrase_callback=lambda: _PASSWORD_B)

            assert result.bucket_id == profile_b
            assert result.closed_previous_bucket_id == profile_a
            assert profile_current_bucket_session() is not active_a
            assert profile_current_bucket_session() is not None
            active_b = profile_current_bucket_session()
            assert active_b is not None
            assert active_b.bucket_id == profile_b
            assert require_profile_record_session(profile_b).profile_id.hex == profile_b.replace("-", "")
            assert capture_pointer(storage_root) is not None
            assert profile_session_path(storage_root=storage_root, profile_id=UUID(profile_a)).exists() is False
        finally:
            _close_live_login()


def test_handover_leaves_no_resumable_session_material_for_the_retired_profile(tmp_path: Path) -> None:
    """A retired profile's acceleration receipt must not still yield its DEK.

    The receipt wraps A's 32-byte bucket DEK under a key the OS keychain holds,
    and a handover rotates neither A's custody generation nor its DEK epoch, so
    a receipt that outlives the retirement stays resumable: it hands the DEK
    back with no passphrase. That is the profile-A resurrection this phase
    exists to refuse.

    Every login here runs in its own interpreter, because that is what the
    operator flow is: one process per command, with no session live from the
    previous one. A handover measured with both logins inside a single process
    exercises only the configuration in which a live in-process session is
    available to identify the profile being retired, so it can confirm the
    property exactly where its precondition already holds and nowhere else.

    The assertion is on the recovered material rather than on the file, because
    a variant that unlinks the receipt while leaving the key recoverable by any
    other route would satisfy a file-absence check and still be the same defect.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        profile_a, profile_b = _register_two_profiles(storage_root)

        first = _login_in_separate_process(storage_root, profile_a, _PASSWORD_A)
        assert first["bucket_id"] == profile_a

        # Anti-tautology: prove the receipt IS resumable from a THIRD process
        # while A is the selected profile. This arm carries the cross-process
        # weight too -- without it the refusal below could pass merely because
        # a separate process cannot reach the material at all.
        live = _probe_resumable_session(storage_root, profile_a)
        assert live["resumed"] is True
        assert live["dek_length"] == 32

        second = _login_in_separate_process(storage_root, profile_b, _PASSWORD_B)
        assert second["bucket_id"] == profile_b

        # The recovered material is the property, so it is measured before the
        # reported outcome: a run that lost the retirement must fail here, on
        # the recoverable DEK, rather than on how the login described itself.
        _assert_no_resumable_material(storage_root, profile_a, after="a cross-process handover")
        assert second["closed_previous"] == profile_a


def test_same_profile_relogin_in_a_new_process_keeps_its_own_session_material(tmp_path: Path) -> None:
    """Re-entering the selected profile retires nothing and revokes nothing.

    The retirement identity is read from the durable pointer as well as from
    any live session, and in a fresh process the pointer names the profile
    being logged into. Excluding that profile is load-bearing rather than
    defensive: revocation runs after the new receipt is minted, so a widened
    identity that failed to exclude it would destroy the receipt this very
    login just produced.

    The second login is deliberately placed past the first session's idle
    window so it is a real authentication that reaches the retirement step,
    rather than the idempotent no-op that returns before it.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        profile = register_profile_with_credentials(label="Relogin", passphrase=_PASSWORD_A).profile_id

        first = _login_in_separate_process(storage_root, profile, _PASSWORD_A)
        assert first["bucket_id"] == profile

        second = _login_in_separate_process(
            storage_root,
            profile,
            _PASSWORD_A,
            now=_now() + timedelta(days=1),
        )
        assert second["bucket_id"] == profile
        # Placed past the idle window so this is a real authentication that
        # reaches the retirement step. The idempotent no-op returns before it,
        # and a repeat login that took that path would prove nothing here.
        assert second["already_authenticated"] is False

        surviving = _probe_resumable_session(storage_root, profile)
        assert surviving["resumed"] is True
        assert surviving["dek_length"] == 32

        assert first["closed_previous"] is None
        assert second["closed_previous"] is None


def test_pointer_conflict_rolls_back_candidate_and_keeps_live_a(tmp_path: Path) -> None:
    """An external pointer CAS conflict cannot tear down the child process's A."""
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        profile_a, profile_b = _register_two_profiles(storage_root)
        context = get_context("spawn")
        candidate_ready = context.Event()
        allow_authentication = context.Event()
        result_queue: Queue[_ConflictResult] = context.Queue()
        child = context.Process(
            target=_conflicted_b_handover_child,
            args=(storage_root, profile_a, profile_b, candidate_ready, allow_authentication, result_queue),
        )
        child.start()
        try:
            assert candidate_ready.wait(timeout=150), "B candidate did not reach password preflight"
            write_pointer(storage_root, BucketPointer(bucket_id=profile_b, schema_version=1))
            allow_authentication.set()
            result = result_queue.get(timeout=180)
            child.join(timeout=30)

            assert child.exitcode == 0
            assert result == {
                "active_bucket": profile_a,
                "record_profile": profile_a,
                "same_live": True,
                "same_record": True,
            }
            current_pointer = read_pointer(storage_root)
            assert current_pointer is not None
            assert current_pointer.bucket_id == profile_b
            assert not profile_session_path(storage_root=storage_root, profile_id=UUID(profile_b)).exists()
        finally:
            if child.is_alive():
                child.terminate()
                child.join(timeout=30)


def test_keyring_acceleration_failure_leaves_b_process_scoped_after_handover(tmp_path: Path) -> None:
    """The real failing keyring backend is a warning, never an authentication failure."""
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        profile_a, profile_b = _register_two_profiles(storage_root)
        context = get_context("spawn")
        result_queue: Queue[_AccelerationResult] = context.Queue()
        child = context.Process(
            target=_acceleration_failure_handover_child,
            args=(storage_root, profile_a, profile_b, result_queue),
        )
        child.start()
        try:
            result = result_queue.get(timeout=180)
            child.join(timeout=30)

            assert child.exitcode == 0
            assert result["active_bucket"] == profile_b
            assert result["session_persisted"] is False
            assert capture_pointer(storage_root) == result["pointer"]
            assert not profile_session_path(storage_root=storage_root, profile_id=UUID(profile_b)).exists()
        finally:
            if child.is_alive():
                child.terminate()
                child.join(timeout=30)


def test_crash_after_b_handover_recovers_only_durable_b_pointer(
    tmp_path: Path,
    _registered_handover_profiles: tuple[Path, str, str],
) -> None:
    """A post-swap process crash leaves B as the only recoverable selected profile."""
    template_root, profile_a, profile_b = _registered_handover_profiles
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        shutil.copytree(template_root, storage_root)
        context = get_context("spawn")
        crashing_child = context.Process(
            target=_crash_after_b_handover_child,
            args=(storage_root, profile_a, profile_b),
        )
        crashing_child.start()
        crashing_child.join(timeout=180)
        try:
            assert crashing_child.exitcode == 0
            current_pointer = read_pointer(storage_root)
            assert current_pointer is not None
            assert current_pointer.bucket_id == profile_b

            result_queue: Queue[_RecoveryResult] = context.Queue()
            recovery_child = context.Process(
                target=_recover_selected_profile_child,
                args=(storage_root, profile_b, result_queue),
            )
            recovery_child.start()
            try:
                result = result_queue.get(timeout=180)
                recovery_child.join(timeout=30)

                assert recovery_child.exitcode == 0
                assert result == {
                    "active_bucket": profile_b,
                    "outcome_bucket": profile_b,
                    "record_profile": profile_b,
                }
            finally:
                if recovery_child.is_alive():
                    recovery_child.terminate()
                    recovery_child.join(timeout=30)
        finally:
            if crashing_child.is_alive():
                crashing_child.terminate()
                crashing_child.join(timeout=30)


#: Phases at which the handover was already complete when the process died,
#: so the recovery login has nothing to replay.
_TERMINAL_CRASH_PHASES = frozenset({_HandoverPhase.ACTIVATED, _HandoverPhase.A_RETIRED})


@pytest.fixture(scope="module")
def _registered_handover_profiles(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, str, str]:
    """Register the two handover profiles once; each caller copies the tree.

    The crash-recovery matrix is the same A-to-B handover crashed at five
    durable phases, and every run needs a fresh storage tree because the
    handover mutates it. Registration is the expensive half -- every wrap of
    a DEK runs a real Argon2id derivation through a supervised worker in its
    own interpreter -- so register once through the production credential
    door here and let each caller copy the completed root into its own
    ``tmp_path``. The registration cost is paid once for the module instead
    of once per crash phase.

    Children are unaffected by the move: every spawned child rebuilds its
    settings from the storage root it is handed, and the secret substrate is
    a sibling of the root, never inside it, so the copied tree is complete
    and self-consistent for any child that receives it.
    """
    template_root = tmp_path_factory.mktemp("handover-template")
    with isolated_profile_storage_root(tmp_path=template_root) as storage_root:
        profile_a, profile_b = _register_two_profiles(storage_root)
        pointer = read_pointer(storage_root)
        assert pointer is not None and pointer.bucket_id == profile_b, (
            "the handover template must materialise the durable pointer; "
            "registration through the production door did not complete"
        )
        return storage_root, profile_a, profile_b


def _assert_journal_settled_for(phase: _HandoverPhase, *, storage_root: Path) -> None:
    """Assert the journal reached the settled state this crash phase implies.

    The two outcomes differ because the journal is an operation record, not an
    audit record, and the recovery login is the observer that retires it.

    A crash *before* activation leaves work to replay: recovery re-authenticates
    B, drives the handover to its end, and writes the terminal receipt, which is
    then deliberately retained for the NEXT login to observe -- so the file is
    present and terminal here.

    A crash *at or after* activation leaves nothing to replay: the recovery
    login is itself that next observer, classifies the witnessed journal as
    complete, and clears it. Asserting a surviving file in that case would
    require the journal to outlive the operation it records.

    Absence is unambiguous rather than merely permissive: the caller has already
    asserted the pointer names B, so the rollback branch that also clears
    (pointer still at the pre-handover state) cannot have fired.
    """
    journal_path = _handover_journal_path(storage_root)
    if phase in _TERMINAL_CRASH_PHASES:
        assert not journal_path.exists(), (
            f"a crash at the terminal phase {phase.value} left an operation journal behind; "
            "recovery observed a completed handover and must retire the record"
        )
        return
    terminal_journal = json.loads(journal_path.read_text(encoding="utf-8"))
    assert terminal_journal["phase"] == _HandoverPhase.A_RETIRED.value


@pytest.mark.parametrize(
    "phase",
    (
        _HandoverPhase.POINTER_PUBLISHED,
        _HandoverPhase.B_BOUND,
        _HandoverPhase.ACCELERATED,
        _HandoverPhase.ACTIVATED,
        _HandoverPhase.A_RETIRED,
    ),
)
def test_crash_at_each_durable_handover_phase_recovers_selected_b(
    tmp_path: Path,
    phase: _HandoverPhase,
    _registered_handover_profiles: tuple[Path, str, str],
) -> None:
    """A real process death at every published phase has one B recovery result.

    Recovery is also where the retirement of A must land. The crash always
    predates the operator's next command, so the recovering process is a new
    one with no session live from the crashed handover, and A's acceleration
    receipt survives every phase whose retirement had not yet run. Measuring
    only that B comes back would leave the retired profile's DEK recoverable
    with no passphrase at four of the five phases.
    """
    template_root, profile_a, profile_b = _registered_handover_profiles
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        shutil.copytree(template_root, storage_root)
        context = get_context("spawn")
        crashing_child = context.Process(
            target=_crash_at_handover_phase_child,
            args=(storage_root, profile_a, profile_b, phase),
        )
        crashing_child.start()
        crashing_child.join(timeout=240)
        try:
            assert crashing_child.exitcode == 0, (
                f"the injected crash never landed at {phase.value}; the handover ran to completion"
            )
            current_pointer = read_pointer(storage_root)
            assert current_pointer is not None
            assert current_pointer.bucket_id == profile_b
            assert _handover_journal_path(storage_root).is_file()

            # Anti-tautology, phase by phase: the refusal after recovery is only
            # evidence where there was something to refuse. Every phase before
            # the terminal receipt crashed with A's receipt still resumable; the
            # terminal one crashed after retirement had already run.
            crashed = _probe_resumable_session(storage_root, profile_a)
            if phase is _HandoverPhase.A_RETIRED:
                assert crashed["resumed"] is False
            else:
                assert crashed["resumed"] is True
                assert crashed["dek_length"] == 32

            result_queue: Queue[_RecoveryResult] = context.Queue()
            recovery_child = context.Process(
                target=_recover_selected_profile_child,
                args=(storage_root, profile_b, result_queue),
            )
            recovery_child.start()
            try:
                result = result_queue.get(timeout=180)
                recovery_child.join(timeout=30)

                assert recovery_child.exitcode == 0
                assert result == {
                    "active_bucket": profile_b,
                    "outcome_bucket": profile_b,
                    "record_profile": profile_b,
                }
                _assert_journal_settled_for(phase, storage_root=storage_root)
                _assert_no_resumable_material(
                    storage_root,
                    profile_a,
                    after=f"recovery from a crash at {phase.value}",
                )
            finally:
                if recovery_child.is_alive():
                    recovery_child.terminate()
                    recovery_child.join(timeout=30)
        finally:
            if crashing_child.is_alive():
                crashing_child.terminate()
                crashing_child.join(timeout=30)
