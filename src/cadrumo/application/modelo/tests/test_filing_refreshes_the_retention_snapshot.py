"""Filing records the retention facts a later deletion preflight will assess.

The retention position is derived from filed records, but a deletion preflight
cannot read them: it runs against profiles it has not unlocked, and the
catalogue lives in the bucket's encrypted store. The plaintext snapshot bridges
that, and filing is the moment it can be written -- the position changes there,
and a session is held by construction.

The second test is the load-bearing one. A filing carries a statutory
obligation; a deletion-support record does not. So the snapshot write must be
incapable of failing a filing, and that is asserted rather than assumed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from ....core import Period
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.filing_record import ModeloRecord, ModeloRecordCatalogue, derive_filing_record_id
from ...filing import FilingRetentionAuthority
from .._revision_persistence import _refresh_filing_retention_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "9c4e17b3-58da-4d2f-b6a1-3f70e9c85d26"
_FILED_AT = datetime(2026, 6, 30, tzinfo=UTC)
_OBSERVED_AT = datetime(2026, 8, 15, tzinfo=UTC)


def _catalogue() -> ModeloRecordCatalogue:
    """One real filed-modelo fact, shaped as the filing path would leave it."""
    work_unit_id = "a" * 64
    revision_id = "b" * 64
    record_id = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        filed_by="aeat.cli.modelo.file",
    )
    return ModeloRecordCatalogue(
        records={
            record_id: ModeloRecord(
                filing_record_id=record_id,
                work_unit_id=work_unit_id,
                calculation_revision_id=revision_id,
                bucket_id=_BUCKET_ID,
                modelo=ModeloCode("303"),
                filing_year=_FILED_AT.year,
                period=Period.from_year_and_code(_FILED_AT.year, "2T"),
                filed_at=_FILED_AT,
                filed_by="aeat.cli.modelo.file",
            )
        }
    )


def test_the_snapshot_written_at_filing_makes_retention_assessable(tmp_path: Path) -> None:
    """Before the refresh the assessment refuses; after it, it answers."""
    from ....core.config import override_settings

    with override_settings(cadrumo_local_storage_root=tmp_path):
        authority = FilingRetentionAuthority()
        identity = UUID(_BUCKET_ID)

        # The state every profile is in until something records the facts.
        with pytest.raises(FileNotFoundError):
            authority.assess(identity, now=_OBSERVED_AT)

        _refresh_filing_retention_snapshot(
            bucket_id=_BUCKET_ID,
            catalogue=_catalogue(),
            observed_at=_OBSERVED_AT,
        )

        assessment = authority.assess(identity, now=_OBSERVED_AT)

    # A record filed weeks ago is inside its window, so the position is real
    # rather than an empty answer that happens not to raise.
    assert assessment.blocks_erase is True
    assert len(assessment.retained) == 1
    assert assessment.latest_safe_erase_date is not None
    assert assessment.latest_safe_erase_date > _OBSERVED_AT


def test_a_failing_snapshot_write_cannot_fail_the_filing() -> None:
    """The obligation outranks the convenience, and the code must say so.

    A filing that succeeded with a stale snapshot is recoverable; a filing
    REFUSED because a deletion-support record could not be written is not. The
    failure here is real rather than simulated -- a bucket identifier that is
    not a UUID cannot be recorded against -- so this exercises the actual
    swallow rather than a stand-in for it.
    """
    _refresh_filing_retention_snapshot(
        bucket_id="not-a-uuid",
        catalogue=_catalogue(),
        observed_at=_OBSERVED_AT,
    )
