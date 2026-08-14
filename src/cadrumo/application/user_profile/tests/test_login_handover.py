"""Real current-capsule authentication and A-to-B handover coverage.

Every profile in this module is registered through the production credential
door, then unlocked through the public login service against an isolated real
storage root.  No substitute custody provider or synthetic session is used.
"""

from __future__ import annotations

import json
import os
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

import pytest
from sqlalchemy.exc import DatabaseError as SqlDatabaseError

from ....adapters.persistence.storage.custody import (
    PROFILE_CUSTODY_SENTINEL_FILENAME,
    ProfileCustodyPasswordError,
    ProfileCustodyRecordError,
)
from ....application.profile_custody import profile_current_bucket_session, profile_session_path
from ....core import BucketPointer, capture_pointer, read_pointer, write_pointer
from ....core import config as config_module
from ....core.config import Settings
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


def _register_two_profiles(storage_root: Path) -> tuple[str, str]:
    first = register_profile_with_credentials(label="Handover A", passphrase=_PASSWORD_A)
    second = register_profile_with_credentials(label="Handover B", passphrase=_PASSWORD_B)
    return first.profile_id, second.profile_id


def _close_live_login() -> None:
    from ....application.profile_custody import profile_close_bucket_session

    close_active_profile_record_session()
    profile_close_bucket_session()


def _child_settings(storage_root: Path) -> tuple[Settings, Token[Settings | None]]:
    settings = Settings(
        _env_file=None,
        cadrumo_local_storage_root=storage_root,
        cadrumo_active_profile=None,
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


def _crash_at_handover_phase_child(
    storage_root: Path,
    profile_a: str,
    profile_b: str,
    phase: _HandoverPhase,
    observed_phase_path: Path,
) -> None:
    """Crash the real handover process immediately after one durable receipt."""
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
                    observed_phase_path.write_text(phase.value, encoding="utf-8")
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
            observed_phase_path.write_text(phase.value, encoding="utf-8")
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
        observed_phase_path.write_text("missed-phase", encoding="utf-8")
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

    _clear_handover_journal(storage_root=storage_root)

    assert _load_handover_journal(storage_root=storage_root) is None


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
        _clear_handover_journal(storage_root=storage_root)

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
            assert not profile_session_path(storage_root=storage_root, bucket_id=profile_b).exists()
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
            assert not profile_session_path(storage_root=storage_root, bucket_id=profile_b).exists()
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
            a_session_path = profile_session_path(storage_root=storage_root, bucket_id=profile_a)
            a_session_before = a_session_path.read_bytes() if a_session_path.is_file() else None
            b_session_path = profile_session_path(storage_root=storage_root, bucket_id=profile_b)
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
            assert profile_session_path(storage_root=storage_root, bucket_id=profile_a).exists() is False
        finally:
            _close_live_login()


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
            assert not profile_session_path(storage_root=storage_root, bucket_id=profile_b).exists()
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
            assert not profile_session_path(storage_root=storage_root, bucket_id=profile_b).exists()
        finally:
            if child.is_alive():
                child.terminate()
                child.join(timeout=30)


def test_crash_after_b_handover_recovers_only_durable_b_pointer(tmp_path: Path) -> None:
    """A post-swap process crash leaves B as the only recoverable selected profile."""
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        profile_a, profile_b = _register_two_profiles(storage_root)
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
) -> None:
    """A real process death at every published phase has one B recovery result."""
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        profile_a, profile_b = _register_two_profiles(storage_root)
        context = get_context("spawn")
        observed_phase_path = tmp_path / f"handover-{phase.value}.txt"
        crashing_child = context.Process(
            target=_crash_at_handover_phase_child,
            args=(storage_root, profile_a, profile_b, phase, observed_phase_path),
        )
        crashing_child.start()
        crashing_child.join(timeout=240)
        try:
            assert crashing_child.exitcode == 0
            assert observed_phase_path.read_text(encoding="utf-8") == phase.value
            current_pointer = read_pointer(storage_root)
            assert current_pointer is not None
            assert current_pointer.bucket_id == profile_b
            assert _handover_journal_path(storage_root).is_file()

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
                terminal_journal = json.loads(_handover_journal_path(storage_root).read_text(encoding="utf-8"))
                assert terminal_journal["phase"] == _HandoverPhase.A_RETIRED.value
            finally:
                if recovery_child.is_alive():
                    recovery_child.terminate()
                    recovery_child.join(timeout=30)
        finally:
            if crashing_child.is_alive():
                crashing_child.terminate()
                crashing_child.join(timeout=30)
