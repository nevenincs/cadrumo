"""The recovery-enrollment manifest mirror reconciles from the envelope on read.

Recovery enrollment writes two things: the recovery envelope itself, and a
``recovery_enrolled`` mirror of that fact in the active profile manifest. They
live in different directories, so no write can make them atomic together — a
process killed between the two leaves the mirror reading false while a
genuinely enrolled envelope sits on disk.

The envelope is the single source of truth, and the recovery status and verify
authorities already read it directly. Reading the status therefore reconciles
the mirror against the envelope, in both directions, so the drift is
self-healing on the natural read path instead of persisting until the next
enrollment happens to overwrite it.

These drive the real production path: real bucket runtime, real encrypted file
secret store, real master-key provider, real BIP-39 mint, real atomic envelope
install, real manifest read and write. The crash is simulated the only honest
way — by putting the two artefacts on disk in exactly the disagreeing state a
kill between the writes would leave, then reading through the production
authority. No mocks, stubs, monkeypatches, skips, or expected-fail markers.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ....adapters.persistence.storage.bucket import BucketManifest, bucket_paths, read_manifest, write_manifest
from ....core.config import load_settings
from ....tests.secure_sql import isolated_runtime_profile
from .._custody import create_recovery_code, inspect_recovery_status, recovery_wrap_path

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]


def _manifest_paths(bucket_id: str) -> object:
    return bucket_paths(Path(load_settings().cadrumo_local_storage_root), bucket_id)


def _enroll() -> None:
    """Run a real recovery enrollment against the active profile."""
    create_recovery_code(confirm=lambda words: words)


def _force_mirror(bucket_id: str, *, enrolled: bool) -> None:
    """Put the manifest mirror into a chosen state directly on disk."""
    paths = _manifest_paths(bucket_id)
    manifest = read_manifest(paths)
    write_manifest(paths, manifest.model_copy(update={"recovery_enrolled": enrolled}))


def _mirror(bucket_id: str) -> bool:
    return read_manifest(_manifest_paths(bucket_id)).recovery_enrolled


def test_status_read_repairs_a_mirror_a_crash_left_false(tmp_path: Path) -> None:
    """An enrolled envelope with a false mirror is reconciled to true."""
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        _enroll()
        assert _mirror(runtime.bucket_id) is True, "enrollment must set the mirror"

        # The crash window: the envelope landed, the mirror write never ran.
        _force_mirror(runtime.bucket_id, enrolled=False)
        assert _mirror(runtime.bucket_id) is False, "the drift must be real on disk"
        assert recovery_wrap_path().is_file(), "the envelope must genuinely still exist"

        status = inspect_recovery_status()

        assert status.recovery_enrolled is True, "status must stand on the envelope, not the mirror"
        assert _mirror(runtime.bucket_id) is True, "reading the status must repair the mirror on disk"


def test_status_read_clears_a_mirror_left_true_without_an_envelope(tmp_path: Path) -> None:
    """Reconciliation runs in both directions, not just the crash direction.

    A mirror reading true with no envelope behind it is the more dangerous
    drift: it advertises a recovery capability the operator does not actually
    have.
    """
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        _enroll()
        assert _mirror(runtime.bucket_id) is True

        recovery_wrap_path().unlink()
        assert not recovery_wrap_path().is_file()
        assert _mirror(runtime.bucket_id) is True, "the stale mirror must be real on disk"

        status = inspect_recovery_status()

        assert status.recovery_enrolled is False
        assert _mirror(runtime.bucket_id) is False, "the stale mirror must be cleared on disk"


def test_status_read_leaves_an_already_correct_manifest_byte_identical(tmp_path: Path) -> None:
    """Reconciliation writes only on an actual mismatch.

    The common path is a read. A status query that rewrote the manifest every
    time would churn the file and re-stamp it for no reason.
    """
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        _enroll()
        paths = _manifest_paths(runtime.bucket_id)
        from ....adapters.persistence.storage.bucket import manifest_path

        before = manifest_path(paths).read_bytes()

        assert inspect_recovery_status().recovery_enrolled is True

        assert manifest_path(paths).read_bytes() == before, "an in-sync mirror must not be rewritten by a read"


def test_status_is_repeatable_and_settles(tmp_path: Path) -> None:
    """Repeated reads converge rather than oscillating."""
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        _enroll()
        _force_mirror(runtime.bucket_id, enrolled=False)

        first = inspect_recovery_status()
        second = inspect_recovery_status()

        assert first.recovery_enrolled is True
        assert second.recovery_enrolled is True
        assert first.recovery_fingerprint == second.recovery_fingerprint
        assert _mirror(runtime.bucket_id) is True


def test_unenrolled_store_reports_false_without_creating_an_envelope(tmp_path: Path) -> None:
    """The baseline: no envelope, no enrollment claimed, nothing written."""
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        assert not recovery_wrap_path().is_file()

        status = inspect_recovery_status()

        assert status.recovery_enrolled is False
        assert status.recovery_fingerprint is None
        assert _mirror(runtime.bucket_id) is False
        assert not recovery_wrap_path().is_file(), "a status read must never mint an envelope"


def test_the_mirror_write_preserves_every_field_it_does_not_own(tmp_path: Path) -> None:
    """The recovery mirror owns ``recovery_enrolled`` and must touch nothing else.

    This is the sixth manifest writer, completing the set the sibling
    preservation gate covers for the five repository writers. It is included
    despite being a single-field ``model_copy`` — a shape that cannot drop a
    field by construction — precisely so that a later conversion to
    field-by-field reconstruction is caught here rather than shipping as a
    silent reset, which is exactly what happened to the profile save writer.

    Every defaultable field is seeded NON-default first. ``_manifest_io``
    omits a ``None``-valued optional on write and re-``setdefault``s it on
    read, so a field left at its default is indistinguishable on disk from one
    silently reset.
    """
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        _enroll()
        paths = _manifest_paths(runtime.bucket_id)

        seeded = read_manifest(paths).model_copy(
            update={
                "idle_lock_minutes": 17,
                "session_absolute_minutes": 33,
                "recovery_enrolled": False,
            },
        )
        write_manifest(paths, seeded)

        # Drive the real reconciliation, which must flip the mirror back to true.
        assert inspect_recovery_status().recovery_enrolled is True

        persisted = read_manifest(paths)
        assert persisted.recovery_enrolled is True, "the mirror write must have actually run"

        preserved = set(BucketManifest.model_fields) - {"recovery_enrolled"}
        dropped = {
            field: (getattr(seeded, field), getattr(persisted, field))
            for field in preserved
            if getattr(persisted, field) != getattr(seeded, field)
        }
        assert dropped == {}, (
            "the recovery-enrollment mirror changed manifest field(s) outside its own "
            f"projection, shown as field: (before, after) -> {dropped}"
        )
