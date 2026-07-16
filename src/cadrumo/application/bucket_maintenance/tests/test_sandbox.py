"""Service-contract tests for the sandbox experiment-workspace lifecycle.

Exercises :func:`create_sandbox`, :func:`discard_sandbox`,
:func:`archive_sandbox`, and :func:`restore_sandbox`
(``cadrumo.application.bucket_maintenance``) against real per-bucket encrypted
storage. The full create -> seed -> switch -> discard round trip (and the
archive -> restore round trip) is covered end to end at the CLI layer
(``entrypoints.cli.tests.test_config_profile_sandbox``); this module covers
the service-boundary contracts that are awkward to isolate through the CLI:
the non-sandbox destructive-action guard, the reserved-label helpers, and
the archive/restore refusal contracts.

Authority: ``composition-service-no-parallel-write-path`` — the sandbox
service composes ``BucketMaintenanceService.delete`` /
``BucketMaintenanceService.archive`` / ``BucketMaintenanceService.restore``
and the canonical profile atomic-create span rather than re-implementing
bucket erasure, tombstoning, or provisioning.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....adapters.persistence.storage.bucket import bucket_paths, manifest_path, read_manifest
from ....domain.user_profile import UserProfileStatus
from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from .. import (
    SANDBOX_LABEL_PREFIX,
    ArchiveSandboxCommand,
    DiscardSandboxCommand,
    MergeSandboxCommand,
    PreviewDiscardSandboxCommand,
    RestoreSandboxCommand,
    SandboxDiscardRefusedError,
    SandboxMergeRefusedError,
    SandboxMergeScope,
    SandboxNotArchivedError,
    SandboxNotFoundError,
    archive_sandbox,
    discard_sandbox,
    is_sandbox_label,
    list_sandboxes,
    merge_sandbox,
    preview_discard_sandbox,
    restore_sandbox,
    sandbox_label,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_BUCKET_ID = "66666666-6666-4666-8666-666666666666"
_REAL_PROFILE_LABEL = "Real client profile"


def test_sandbox_label_prefix_helpers_round_trip() -> None:
    """``sandbox_label``/``is_sandbox_label`` are inverse; a real label is never mistaken for one."""
    label = sandbox_label("bakeoff")
    assert label == f"{SANDBOX_LABEL_PREFIX}bakeoff"
    assert is_sandbox_label(label)
    assert not is_sandbox_label(_REAL_PROFILE_LABEL)


@pytest.fixture
def runtime(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(
        tmp_path=tmp_path,
        bucket_id=_BUCKET_ID,
        label=_REAL_PROFILE_LABEL,
    ) as profile:
        yield profile


def test_discard_refuses_a_non_sandbox_labelled_bucket_by_default(runtime: TestRuntimeProfile) -> None:
    """``discard_sandbox`` refuses a bucket whose label is not sandbox-tagged.

    This is the safety guard #422 requires: an operator (or an LLM agent)
    calling the sandbox-discard verb by mistake against a real profile must
    be refused before any erase primitive runs, not merely warned.
    """
    with pytest.raises(SandboxDiscardRefusedError):
        discard_sandbox(DiscardSandboxCommand(bucket_id=runtime.bucket_id, confirmed=True))


def test_discard_of_non_sandbox_bucket_erases_nothing_on_refusal(runtime: TestRuntimeProfile) -> None:
    """The refused non-sandbox discard leaves the bucket directory and manifest untouched."""
    paths = bucket_paths(runtime.storage_root, runtime.bucket_id)
    assert manifest_path(paths).is_file()

    with pytest.raises(SandboxDiscardRefusedError):
        discard_sandbox(DiscardSandboxCommand(bucket_id=runtime.bucket_id, confirmed=True))

    # The guard fires before BucketMaintenanceService.delete runs; the
    # manifest this test seeded must still be exactly where it was.
    assert manifest_path(paths).is_file()


def test_preview_discard_refuses_a_non_sandbox_labelled_bucket_by_default(runtime: TestRuntimeProfile) -> None:
    """``preview_discard_sandbox`` applies the identical non-sandbox refusal ``discard_sandbox`` does.

    A preview must never suggest an erase the real discard verb would refuse:
    the guard fires before any read-only session is opened against the
    target bucket.
    """
    with pytest.raises(SandboxDiscardRefusedError):
        preview_discard_sandbox(PreviewDiscardSandboxCommand(bucket_id=runtime.bucket_id))


def test_list_sandboxes_excludes_a_non_sandbox_labelled_bucket(runtime: TestRuntimeProfile) -> None:
    """``list_sandboxes`` never names a bucket whose label lacks the reserved prefix."""
    assert list_sandboxes() == ()


def test_archive_refuses_a_non_sandbox_labelled_bucket_by_default(runtime: TestRuntimeProfile) -> None:
    """``archive_sandbox`` refuses a bucket whose label is not sandbox-tagged.

    Mirrors ``test_discard_refuses_a_non_sandbox_labelled_bucket_by_default``:
    an operator (or an LLM agent) calling the sandbox-archive verb by
    mistake against a real profile must be refused before any tombstone
    primitive runs.
    """
    with pytest.raises(SandboxDiscardRefusedError):
        archive_sandbox(ArchiveSandboxCommand(bucket_id=runtime.bucket_id, confirmed=True))


def test_archive_of_non_sandbox_bucket_tombstones_nothing_on_refusal(runtime: TestRuntimeProfile) -> None:
    """The refused non-sandbox archive leaves the bucket's manifest status untouched."""
    paths = bucket_paths(runtime.storage_root, runtime.bucket_id)

    with pytest.raises(SandboxDiscardRefusedError):
        archive_sandbox(ArchiveSandboxCommand(bucket_id=runtime.bucket_id, confirmed=True))

    # The guard fires before BucketMaintenanceService.archive runs; the
    # manifest must still report active status.
    assert read_manifest(paths).status is UserProfileStatus.ACTIVE


def test_restore_refuses_a_non_sandbox_labelled_bucket_by_default(runtime: TestRuntimeProfile) -> None:
    """``restore_sandbox`` applies the identical non-sandbox refusal ``archive_sandbox`` does."""
    with pytest.raises(SandboxDiscardRefusedError):
        restore_sandbox(RestoreSandboxCommand(bucket_id=runtime.bucket_id))


def test_restore_refuses_a_sandbox_that_is_not_archived(tmp_path: Path) -> None:
    """``restore_sandbox`` refuses a live (never-archived) sandbox-labelled bucket.

    Uses a dedicated sandbox-labelled runtime (rather than the module's
    real-profile fixture) so the non-sandbox guard does not mask the
    not-archived refusal this test targets.
    """
    with (
        isolated_runtime_profile(
            tmp_path=tmp_path,
            bucket_id="77777777-7777-4777-8777-777777777777",
            label=sandbox_label("live-one"),
        ) as profile,
        pytest.raises(SandboxNotArchivedError),
    ):
        restore_sandbox(RestoreSandboxCommand(bucket_id=profile.bucket_id))


def test_merge_refuses_without_confirmation(runtime: TestRuntimeProfile) -> None:
    """``merge_sandbox`` refuses a merge that has not been explicitly confirmed.

    Mirrors ``discard``/``archive``'s ``confirmed=True`` boundary contract:
    a programmatic caller must observe the same guarantee the CLI ``--yes``
    flag provides, before any typed-catalogue write runs.
    """
    with pytest.raises(SandboxMergeRefusedError):
        merge_sandbox(
            MergeSandboxCommand(
                source_bucket_id=sandbox_label("bakeoff"),
                target_bucket_id=runtime.bucket_id,
                scope=SandboxMergeScope.LEDGER,
                confirmed=False,
            ),
        )


def test_merge_refuses_when_source_and_target_are_identical(runtime: TestRuntimeProfile) -> None:
    """``merge_sandbox`` refuses when the source and target bucket ids are the same.

    Merging a bucket into itself is a no-op that would only waste a write
    cycle; the guard fires before any repository session opens.
    """
    with pytest.raises(SandboxMergeRefusedError):
        merge_sandbox(
            MergeSandboxCommand(
                source_bucket_id=runtime.bucket_id,
                target_bucket_id=runtime.bucket_id,
                scope=SandboxMergeScope.LEDGER,
                confirmed=True,
            ),
        )


def test_merge_refuses_a_non_sandbox_labelled_source_by_default(runtime: TestRuntimeProfile) -> None:
    """``merge_sandbox`` refuses to promote FROM a bucket that is not sandbox-labelled.

    Mirrors ``discard``/``archive``'s non-sandbox guard: an operator (or an
    LLM agent) invoking the merge verb against a real profile as the source
    by mistake must be refused before any catalogue is read.
    """
    with pytest.raises(SandboxDiscardRefusedError):
        merge_sandbox(
            MergeSandboxCommand(
                source_bucket_id=runtime.bucket_id,
                target_bucket_id="88888888-8888-4888-8888-888888888888",
                scope=SandboxMergeScope.LEDGER,
                confirmed=True,
            ),
        )


def test_merge_refuses_an_unknown_target_bucket(tmp_path: Path) -> None:
    """``merge_sandbox`` refuses when the target bucket has no registered pointer."""
    with (
        isolated_runtime_profile(
            tmp_path=tmp_path,
            bucket_id="99999999-9999-4999-8999-999999999999",
            label=sandbox_label("live-two"),
        ) as profile,
        pytest.raises(SandboxNotFoundError),
    ):
        merge_sandbox(
            MergeSandboxCommand(
                source_bucket_id=profile.bucket_id,
                target_bucket_id="00000000-0000-4000-8000-000000000000",
                scope=SandboxMergeScope.LEDGER,
                confirmed=True,
            ),
        )
