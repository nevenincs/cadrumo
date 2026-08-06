"""Contract parity between sandbox lifecycle application results and their CLI shells.

``ConfigProfileSandboxCreateResult``, ``...DiscardResult``,
``...ArchiveResult``, and ``...RestoreResult`` must refuse the malformed
bucket identity and timestamp shapes the canonical
``CreateSandboxResult`` / ``DiscardSandboxResult`` / ``ArchiveSandboxResult``
/ ``RestoreSandboxResult`` records already refuse, and must carry the same
``occurred_at`` the confirmed (non-dry-run) lifecycle mutations produce.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from .._config_sandbox_payloads import (
    ConfigProfileSandboxArchiveResult,
    ConfigProfileSandboxCreateResult,
    ConfigProfileSandboxDiscardResult,
    ConfigProfileSandboxRestoreResult,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_OCCURRED_AT = datetime(2026, 6, 1, 8, 0, tzinfo=UTC)


def test_create_result_rejects_a_blank_bucket_id() -> None:
    """A blank bucket id is refused, matching the canonical ``BucketId`` constraint."""
    with pytest.raises(ValidationError):
        ConfigProfileSandboxCreateResult(bucket_id="", label="sandbox:demo")


def test_create_result_accepts_a_real_bucket_id() -> None:
    """A genuine bucket id round-trips cleanly."""
    result = ConfigProfileSandboxCreateResult(bucket_id="bucket-1", label="sandbox:demo", seeded_from="main")

    assert result.bucket_id == "bucket-1"


def test_discard_result_rejects_a_blank_bucket_id() -> None:
    """A blank bucket id on the confirmed-discard envelope is refused."""
    with pytest.raises(ValidationError):
        ConfigProfileSandboxDiscardResult(
            dry_run=False,
            bucket_id="",
            previous_label="sandbox:demo",
            occurred_at=_OCCURRED_AT,
        )


def test_discard_result_carries_the_confirmed_erase_timestamp() -> None:
    """The confirmed branch's ``occurred_at`` mirrors ``DiscardSandboxResult.occurred_at``."""
    result = ConfigProfileSandboxDiscardResult(
        dry_run=False,
        bucket_id="bucket-1",
        previous_label="sandbox:demo",
        occurred_at=_OCCURRED_AT,
    )

    assert result.occurred_at == _OCCURRED_AT


def test_discard_result_dry_run_carries_no_timestamp() -> None:
    """The ``--dry-run`` preview branch never mutates, so ``occurred_at`` stays absent."""
    result = ConfigProfileSandboxDiscardResult(dry_run=True, bucket_id="bucket-1", namespaces=[])

    assert result.occurred_at is None


def test_discard_result_rejects_a_non_datetime_occurred_at() -> None:
    """A non-datetime ``occurred_at`` is refused under the strict envelope."""
    with pytest.raises(ValidationError):
        ConfigProfileSandboxDiscardResult.model_validate(
            {
                "dry_run": False,
                "bucket_id": "bucket-1",
                "previous_label": "sandbox:demo",
                "occurred_at": "not-a-time",
            },
        )


def test_archive_result_rejects_a_blank_bucket_id() -> None:
    """A blank bucket id on the archive envelope is refused."""
    with pytest.raises(ValidationError):
        ConfigProfileSandboxArchiveResult(bucket_id="", label="sandbox:demo", occurred_at=_OCCURRED_AT)


def test_archive_result_carries_the_confirmed_archive_timestamp() -> None:
    """The confirmed branch's ``occurred_at`` mirrors ``ArchiveSandboxResult.occurred_at``."""
    result = ConfigProfileSandboxArchiveResult(bucket_id="bucket-1", label="sandbox:demo", occurred_at=_OCCURRED_AT)

    assert result.occurred_at == _OCCURRED_AT


def test_restore_result_rejects_a_blank_bucket_id() -> None:
    """A blank bucket id on the restore envelope is refused."""
    with pytest.raises(ValidationError):
        ConfigProfileSandboxRestoreResult(bucket_id="", label="sandbox:demo", occurred_at=_OCCURRED_AT)


def test_restore_result_requires_an_occurred_at() -> None:
    """Restore has no dry-run preview, so ``occurred_at`` is a required field."""
    with pytest.raises(ValidationError):
        ConfigProfileSandboxRestoreResult.model_validate({"bucket_id": "bucket-1", "label": "sandbox:demo"})


def test_restore_result_carries_the_restore_timestamp() -> None:
    """A genuine restore result round-trips cleanly with its timestamp."""
    result = ConfigProfileSandboxRestoreResult(bucket_id="bucket-1", label="sandbox:demo", occurred_at=_OCCURRED_AT)

    assert result.occurred_at == _OCCURRED_AT
