"""Service-contract tests for ``BucketMaintenanceService.disk_usage``.

Exercises the on-disk footprint measurement against a real bucket directory
tree: the fixture provisions a genuine ``BUCKET_DEK_V1`` bucket (real
``db``/``blobs`` subdirectories) and the tests write real bytes to the
database file and to the blobs directory, then assert the service's byte
totals track the real filesystem state via plain ``os.stat`` — never
decrypted secure-object content.

Only current hierarchy members are measured. The retired plaintext bucket
manifest was once enumerated as an extra file beside ``db``; a store that
could carry one is a store custody discovery refuses outright, so counting
it made this the one site presenting a retired artefact as an ordinary
member of a current bucket.

Authority: ``aeat-architecture-boundaries`` (the service reads
filesystem metadata through the existing
:func:`~adapters.persistence.storage.bucket.bucket_paths` layout
resolver rather than inventing a parallel storage-accounting path);
``sensitive-financial-data-secure-storage-only`` (the measurement never
opens or decrypts a secure-object payload — only ``os.stat`` sizes).

See Also:
    :class:`~application.bucket_maintenance.BucketMaintenanceService`
        Application facade whose disk-usage service contract is exercised here.
    :class:`~application.bucket_maintenance.DiskUsageBucketCommand`
        Typed command carrying the measured bucket id.
    :class:`~application.bucket_maintenance.DiskUsageBucketResult`
        Result payload whose totals and per-subdir rows are asserted.
    :mod:`~entrypoints.cli._config._sandbox`
        CLI sandbox usage surface that consumes the same service report.
"""

from __future__ import annotations

import contextlib
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from ....adapters.persistence.storage.bucket import bucket_paths
from ....tests.bucket_layout import provision_bucket_directory
from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from .. import BucketMaintenanceService, DiskUsageBucketCommand

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "1f6b0000-0000-4000-8000-00000000d1d1"


@pytest.fixture
def runtime(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(
        tmp_path=tmp_path,
        bucket_id=_BUCKET_ID,
        label="Disk usage target",
    ) as profile:
        yield profile


def test_disk_usage_reports_two_fixed_subdir_rows(runtime: TestRuntimeProfile) -> None:
    """The report always carries exactly the two fixed-layout subdirectory rows."""
    result = BucketMaintenanceService().disk_usage(DiskUsageBucketCommand(bucket_id=runtime.bucket_id))

    assert result.bucket_id == runtime.bucket_id
    names = {row.subdir for row in result.subdirs}
    assert names == {"db", "blobs"}


def test_disk_usage_blobs_row_grows_after_a_real_file_write(runtime: TestRuntimeProfile) -> None:
    """Writing a real file into the blobs directory increases the measured ``blobs`` total.

    This is the core proof the #422 slice asks for: the measurement is a
    genuine filesystem walk, not a cached or hardcoded value — it reacts to
    real bytes landing on disk.
    """
    before = BucketMaintenanceService().disk_usage(DiskUsageBucketCommand(bucket_id=runtime.bucket_id))
    before_blobs = next(row for row in before.subdirs if row.subdir == "blobs")
    assert before_blobs.total_bytes == 0
    assert before_blobs.file_count == 0

    payload = b"sealed-ciphertext-placeholder" * 100
    blob_path = runtime.paths.blobs_dir / "artefact-01.bin"
    blob_path.write_bytes(payload)

    after = BucketMaintenanceService().disk_usage(DiskUsageBucketCommand(bucket_id=runtime.bucket_id))
    after_blobs = next(row for row in after.subdirs if row.subdir == "blobs")
    assert after_blobs.total_bytes == len(payload)
    assert after_blobs.file_count == 1
    assert after.total_bytes == before.total_bytes + len(payload)


def test_disk_usage_total_bytes_equals_the_sum_of_subdir_rows(runtime: TestRuntimeProfile) -> None:
    """The reported grand total is exactly the sum of the per-subdir totals."""
    (runtime.paths.blobs_dir / "artefact-01.bin").write_bytes(b"\x00" * 256)

    result = BucketMaintenanceService().disk_usage(DiskUsageBucketCommand(bucket_id=runtime.bucket_id))

    assert result.total_bytes == sum(row.total_bytes for row in result.subdirs)
    assert result.total_bytes > 0


def test_disk_usage_measures_a_non_active_bucket_without_opening_a_session(
    tmp_path: Path,
    runtime: TestRuntimeProfile,
) -> None:
    """A second, never-activated bucket's footprint can be measured directly.

    ``disk_usage`` reads only ``bucket_paths`` + ``os.stat`` — no master
    key or active-bucket session is required — so it must report a real,
    non-zero total for a bucket that is not the currently active one,
    exactly like ``preview_discard_sandbox`` already relies on for a
    non-active sandbox.
    """
    other_bucket_id = "1f6b0000-0000-4000-8000-0000000007e7"
    other_paths = provision_bucket_directory(runtime.settings.cadrumo_local_storage_root, other_bucket_id)
    (other_paths.blobs_dir / "other-artefact.bin").write_bytes(b"\x01" * 512)

    # Confirm bucket_paths resolves identically (no drift between the
    # provisioning call and the service's internal resolution).
    resolved = bucket_paths(runtime.settings.cadrumo_local_storage_root, other_bucket_id)
    assert resolved.blobs_dir == other_paths.blobs_dir

    result = BucketMaintenanceService().disk_usage(DiskUsageBucketCommand(bucket_id=other_bucket_id))

    assert result.bucket_id == other_bucket_id
    blobs_row = next(row for row in result.subdirs if row.subdir == "blobs")
    assert blobs_row.total_bytes == 512
    assert blobs_row.file_count == 1


def test_disk_usage_tolerates_a_blob_vanishing_mid_measurement(runtime: TestRuntimeProfile) -> None:
    """A blob write/delete racing the disk-usage read no longer crashes the report.

    ``_directory_byte_total`` previously had no per-file ``OSError``
    tolerance: a file vanishing between ``rglob`` yielding it and the
    ``.stat()`` call raised straight through the service -- a real latent
    bug, since nothing stops a concurrent secure-object write from
    removing/replacing a blob while an operator runs a disk-usage report.
    Delegating to :func:`~cadrumo.core.paths.directory_byte_total` in
    tolerant mode closes it. This is a REAL concurrent
    race (a background thread deletes files while the measurement walks the
    directory), not a mock: with 200 files being deleted concurrently the
    race is reliably hit, and the assertion that matters is simply that the
    call completes without raising.
    """
    file_count = 200
    for index in range(file_count):
        (runtime.paths.blobs_dir / f"artefact-{index:03d}.bin").write_bytes(b"x" * 16)

    stop = threading.Event()

    def _delete_files() -> None:
        for index in range(file_count):
            if stop.is_set():
                return
            with contextlib.suppress(OSError):
                (runtime.paths.blobs_dir / f"artefact-{index:03d}.bin").unlink()

    deleter = threading.Thread(target=_delete_files)
    deleter.start()
    try:
        # Must not raise even though files are disappearing underneath it.
        result = BucketMaintenanceService().disk_usage(DiskUsageBucketCommand(bucket_id=runtime.bucket_id))
    finally:
        stop.set()
        deleter.join(timeout=5)

    assert result.bucket_id == runtime.bucket_id
