"""The file result reports the posture the record kept, and never a second opinion.

A filing window can be amended after a declaration was filed, so recomputing
lateness when a record is read would silently rewrite history: a filing that
was timely when it was made could later be reported as extemporánea, or the
reverse. The posture is therefore decided once, at filing time, kept on the
:class:`~cadrumo.domain.modelos.filing_record.ModeloRecord`, and only repeated
by the public result.

A record that kept no posture -- one written before the field existed, or by a
path that decides none -- reads as ``unknown``. Unknown is not timely.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ....core.filing_timeliness import FilingTimeliness
from ....core.period import Period
from ....domain.modelos.filing_record import (
    AeatConfirmationState,
    FilingDeclarationKind,
    FilingOrigin,
    ModeloRecord,
    derive_filing_record_id,
)
from ..filing_projection import ModeloFilingRecordSnapshot
from ..lifecycle_advisories import ModeloLifecycleAdvisories
from ..work_filing_contracts import ModeloWorkFilePublicResultV2

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_WORK_UNIT_ID = "b" * 64
_REVISION_ID = "a" * 64
_BUCKET_ID = "91fb7268-c9d4-4309-879c-d44fa7970f9d"
_FILED_AT = datetime(2026, 4, 15, 10, 0, tzinfo=UTC)


def _record(kept: FilingTimeliness | None) -> ModeloRecord:
    return ModeloRecord(
        filing_record_id=derive_filing_record_id(
            work_unit_id=_WORK_UNIT_ID, calculation_revision_id=_REVISION_ID, filed_by="operator"
        ),
        work_unit_id=_WORK_UNIT_ID,
        calculation_revision_id=_REVISION_ID,
        bucket_id=_BUCKET_ID,
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        filed_at=_FILED_AT,
        filed_by="operator",
        origin=FilingOrigin.LOCAL,
        confirmation=AeatConfirmationState.PENDIENTE,
        declaration_kind=FilingDeclarationKind.ORIGINAL,
        filing_timeliness=kept,
    )


def _result(record: ModeloRecord, reported: FilingTimeliness) -> ModeloWorkFilePublicResultV2:
    return ModeloWorkFilePublicResultV2(
        record=ModeloFilingRecordSnapshot.from_record(record),
        advisories=ModeloLifecycleAdvisories(
            work_unit_id=_WORK_UNIT_ID,
            calculation_revision_id=_REVISION_ID,
            modelo="130",
            filing_year=2026,
            period="1T",
        ),
        published=True,
        filing_timeliness=reported,
        filing_record_id=record.filing_record_id,
        work_unit_id=_WORK_UNIT_ID,
        calculation_revision_id=_REVISION_ID,
    )


@pytest.mark.parametrize(
    "kept",
    [FilingTimeliness.EN_PLAZO, FilingTimeliness.EXTEMPORANEA, FilingTimeliness.UNKNOWN],
)
def test_the_kept_posture_survives_the_transport_snapshot(kept: FilingTimeliness) -> None:
    """The receipt carries the posture through its wire snapshot unchanged."""
    record = _record(kept)
    snapshot = ModeloFilingRecordSnapshot.from_record(record)

    assert snapshot.filing_timeliness is kept
    assert snapshot.to_record() == record
    assert _result(record, kept).filing_timeliness is kept


def test_a_record_that_kept_no_posture_is_reported_as_unknown() -> None:
    """An absent posture reads as unknown; it is never reported as en plazo."""
    record = _record(None)

    assert ModeloFilingRecordSnapshot.from_record(record).filing_timeliness is None
    assert _result(record, FilingTimeliness.UNKNOWN).filing_timeliness is FilingTimeliness.UNKNOWN

    with pytest.raises(ValidationError, match="posture the record kept"):
        _result(record, FilingTimeliness.EN_PLAZO)


def test_the_result_cannot_contradict_the_posture_its_record_kept() -> None:
    """A timely record cannot be published as a late filing, or the reverse."""
    with pytest.raises(ValidationError, match="posture the record kept"):
        _result(_record(FilingTimeliness.EN_PLAZO), FilingTimeliness.EXTEMPORANEA)
    with pytest.raises(ValidationError, match="posture the record kept"):
        _result(_record(FilingTimeliness.EXTEMPORANEA), FilingTimeliness.EN_PLAZO)
