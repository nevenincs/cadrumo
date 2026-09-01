"""The filing owner exposes the retention position, not only a blocking flag.

The custody deletion gate needs one bit -- may this profile be erased. The
operator-facing refusal needs three facts: how many filed records are still
retained, the floor they are measured against, and the date erasure becomes
safe. That message cites Ley 58/2003 (LGT) arts. 66 and 70, so a refusal that
cannot name them is worse than no message: it asserts a statute and then
declines to say what the statute requires.

Both come from one computation. These tests pin that the detailed view is real
rather than nominal, that it agrees with the flag the gate reads, and that an
absent snapshot refuses instead of reporting an empty assessment -- a zero
retained count is indistinguishable from "nothing is retained", which reads as
permission to erase.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest

from ....core.period import Period
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.filing_record import ModeloRecord, derive_filing_record_id
from ....domain.retention.floor import TAX_RECORD_RETENTION_FLOOR_YEARS
from ..retention import FilingRetentionAuthority

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = UUID("5f2b9c14-7d3e-4a61-9f08-2c6b1d5e4a37")
_NOW = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)


def _filed_record(*, filed_at: datetime, seed: str) -> ModeloRecord:
    """Produce a real filed-modelo fact for the canonical filing owner."""
    work_unit_id = (seed * 64)[:64]
    calculation_revision_id = (chr(ord(seed[0]) + 1) * 64)[:64]
    return ModeloRecord(
        filing_record_id=derive_filing_record_id(
            work_unit_id=work_unit_id,
            calculation_revision_id=calculation_revision_id,
            filed_by="aeat.cli.modelo.file",
        ),
        work_unit_id=work_unit_id,
        calculation_revision_id=calculation_revision_id,
        bucket_id=str(_PROFILE_ID),
        modelo=ModeloCode("303"),
        filing_year=filed_at.year,
        period=Period.from_year_and_code(filed_at.year, "2T"),
        filed_at=filed_at,
        filed_by="aeat.cli.modelo.file",
    )


def test_the_assessment_names_the_records_the_flag_only_counts(tmp_path: Path) -> None:
    """Two recently filed records are retained, and the detail says so."""
    authority = FilingRetentionAuthority(root=tmp_path)
    authority.record_filing_catalogue(
        profile_id=_PROFILE_ID,
        records=(
            _filed_record(filed_at=_NOW - timedelta(days=30), seed="a"),
            _filed_record(filed_at=_NOW - timedelta(days=60), seed="c"),
        ),
        observed_at=_NOW,
    )

    assessment = authority.assess(_PROFILE_ID, now=_NOW)

    assert assessment.blocks_erase is True
    assert len(assessment.retained) == 2
    assert assessment.floor_years == TAX_RECORD_RETENTION_FLOOR_YEARS
    assert assessment.latest_safe_erase_date is not None
    # The operator can act on this: the whole set clears at the latest of the
    # per-record boundaries, which must lie beyond the assessment instant.
    assert assessment.latest_safe_erase_date > _NOW
    assert assessment.latest_safe_erase_date == max(record.earliest_safe_erase_date for record in assessment.retained)


def test_the_detailed_and_gate_views_cannot_disagree(tmp_path: Path) -> None:
    """The flag the custody gate reads is the same answer, narrowed.

    Asserted for both dispositions rather than one, because a view that always
    returned ``True`` would satisfy a single-direction check.
    """
    authority = FilingRetentionAuthority(root=tmp_path)

    authority.record_filing_catalogue(
        profile_id=_PROFILE_ID,
        records=(_filed_record(filed_at=_NOW - timedelta(days=10), seed="a"),),
        observed_at=_NOW,
    )
    assert authority.assess(_PROFILE_ID, now=_NOW).blocks_erase is True
    assert authority.project(_PROFILE_ID, now=_NOW).blocks_local_deletion is True

    long_past = _NOW.replace(year=_NOW.year - (TAX_RECORD_RETENTION_FLOOR_YEARS + 2))
    authority.record_filing_catalogue(
        profile_id=_PROFILE_ID,
        records=(_filed_record(filed_at=long_past, seed="a"),),
        observed_at=_NOW,
    )
    cleared = authority.assess(_PROFILE_ID, now=_NOW)
    assert cleared.blocks_erase is False
    assert cleared.retained == ()
    assert cleared.latest_safe_erase_date is None
    assert authority.project(_PROFILE_ID, now=_NOW).blocks_local_deletion is False


def test_an_absent_snapshot_refuses_rather_than_reporting_nothing_retained(tmp_path: Path) -> None:
    """The zero case must be unreachable by accident.

    An assessment defaulted to zero retained records cannot be told apart from
    a genuine clear result, and on a destructive path that difference is the
    whole safeguard. Absence raises, exactly as the gate view does.
    """
    authority = FilingRetentionAuthority(root=tmp_path)

    with pytest.raises(FileNotFoundError):
        authority.assess(_PROFILE_ID, now=_NOW)

    with pytest.raises(FileNotFoundError):
        authority.project(_PROFILE_ID, now=_NOW)
