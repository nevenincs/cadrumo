"""Service-contract tests for the sandbox experiment-workspace lifecycle.

Exercises :func:`create_sandbox` and :func:`discard_sandbox`
(``aeat.application.bucket_maintenance``) against real per-bucket encrypted
storage. The full create -> seed -> switch -> discard round trip is covered
end to end at the CLI layer
(``entrypoints.cli.tests.test_config_profile_sandbox``); this module covers
the service-boundary contracts that are awkward to isolate through the CLI:
the non-sandbox destructive-action guard, and the reserved-label helpers.

Authority: ``composition-service-no-parallel-write-path`` — the sandbox
service composes ``BucketMaintenanceService.delete`` and the canonical
profile atomic-create span rather than re-implementing bucket erasure or
provisioning.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from .. import (
    SANDBOX_LABEL_PREFIX,
    DiscardSandboxCommand,
    PreviewDiscardSandboxCommand,
    SandboxDiscardRefusedError,
    discard_sandbox,
    is_sandbox_label,
    list_sandboxes,
    preview_discard_sandbox,
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
    from ....adapters.persistence.storage.bucket import bucket_paths, manifest_path

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
