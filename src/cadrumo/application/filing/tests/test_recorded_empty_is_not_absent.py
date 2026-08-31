"""A recorded-empty retention snapshot is not the same as an absent one.

Absence means nobody asked the filing owner; an empty recorded snapshot means
the owner was asked and answered "nothing". The retention assessment refuses on
the first and answers on the second, and that difference is load-bearing: the
snapshot writes are allowed to be best-effort ONLY because absence fails closed
and blocks a deletion. If absence ever came to mean "nothing retained", every
swallowed write would become a fail-open.

So these tests exist to keep the two states apart, not merely to show the empty
case works.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from ..retention import (
    FilingRetentionAuthority,
    try_record_filing_retention_snapshot,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = UUID("2f8c6b41-9d05-4e73-a1c2-7b3e5d09f846")
_OBSERVED_AT = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)


def test_absent_and_recorded_empty_are_distinguishable(tmp_path: Path) -> None:
    """The assessment refuses on absence and answers on a recorded empty."""
    from ....core.config import override_settings

    with override_settings(cadrumo_local_storage_root=tmp_path):
        authority = FilingRetentionAuthority()

        # Absent: nobody asked. This is what makes a swallowed write safe.
        with pytest.raises(FileNotFoundError):
            authority.assess(_PROFILE_ID, now=_OBSERVED_AT)

        assert (
            try_record_filing_retention_snapshot(
                bucket_id=str(_PROFILE_ID),
                records=(),
                observed_at=_OBSERVED_AT,
            )
            is True
        )

        # Recorded empty: asked and answered. A real assessment, not a refusal.
        assessment = authority.assess(_PROFILE_ID, now=_OBSERVED_AT)

    assert assessment.blocks_erase is False
    assert assessment.retained == ()
    assert assessment.latest_safe_erase_date is None


def test_the_recorder_reports_failure_instead_of_raising() -> None:
    """No caller may be failed by a deletion-support record.

    The failure is genuine rather than simulated -- a bucket identifier that is
    not a canonical UUID cannot be recorded against -- so this exercises the
    real swallow. The boolean is what lets a caller's own tests assert the write
    happened without inferring it from a side effect.
    """
    assert (
        try_record_filing_retention_snapshot(
            bucket_id="not-a-uuid",
            records=(),
            observed_at=_OBSERVED_AT,
        )
        is False
    )
