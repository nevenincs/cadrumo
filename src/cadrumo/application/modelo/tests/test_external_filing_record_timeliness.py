"""An imported AEAT filing's posture comes from when AEAT says it was presented.

An AEAT-origin chain entry records a declaration someone already presented. The
import's own clock says when the reconstruction ran, so judging lateness on it
would call every reconstruction of an old filing extemporánea. The register's
observed presentation date is the only date that answers the question, and
without one the posture stays unknown: an import that cannot say when the
declaration was presented cannot say whether it was presented in time.

Modelo 303 1T 2026 closes on 20 April 2026, a business day.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from ....core.filing_timeliness import FilingTimeliness
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.deadlines.effective_close import resolve_effective_filing_deadline
from ....domain.modelos.filing_record import (
    AeatRegisterRef,
    ExternalEvidenceKind,
    FilingDeclarationKind,
    derive_filing_record_id,
)
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ..external_import_actions import build_external_filing_record

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_BUCKET_ID = "e" * 64
_REVISION_ID = "2026-y-siguientes"
_MODELO = "303"
_FILING_YEAR = 2026
_PERIOD_CODE = "1T"
#: Deliberately long after every presentation date under test: the import clock
#: must not influence the posture.
_IMPORTED_AT = datetime(2028, 9, 1, 8, 0, tzinfo=UTC)
_CSV = "ABCD1234EFGH5678"


def _work_unit() -> WorkUnit:
    period = Period.from_year_and_code(_FILING_YEAR, _PERIOD_CODE)
    created = datetime(_FILING_YEAR, 1, 1, tzinfo=UTC)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo=_MODELO,
            filing_year=_FILING_YEAR,
            period=period,
            revision_id=_REVISION_ID,
        ),
        bucket_id=_BUCKET_ID,
        modelo=_MODELO,
        filing_year=_FILING_YEAR,
        period=period,
        revision_id=_REVISION_ID,
        name="imported first quarter",
        created_at=created,
        updated_at=created,
    )


def _timeliness(
    *,
    aeat_register: AeatRegisterRef | None,
    operation: PinnedAuthorityOperation,
    declaration_kind: FilingDeclarationKind = FilingDeclarationKind.ORIGINAL,
) -> FilingTimeliness | None:
    unit = _work_unit()
    record = build_external_filing_record(
        filing_record_id=derive_filing_record_id(
            work_unit_id=unit.work_unit_id,
            calculation_revision_id="a" * 64,
            filed_by="aeat-import",
        ),
        work_unit=unit,
        calculation_revision_id="a" * 64,
        filed_at=_IMPORTED_AT,
        filed_by="aeat-import",
        evidence_kind=ExternalEvidenceKind.AEAT_CSV_REGISTER,
        evidence_reference_id="TEST-CSV-REGISTER",
        declaration_kind=declaration_kind,
        operation=operation,
        aeat_register=aeat_register,
    )
    assert record.filed_at == _IMPORTED_AT
    return record.filing_timeliness


def _register(presented_at: datetime | None) -> AeatRegisterRef:
    """A valid register reference; one needs an expediente id or a CSV."""
    return AeatRegisterRef(csv=_CSV, presented_at=presented_at)


def test_a_presentation_inside_the_window_is_timely_however_late_the_import_ran(
    operation: PinnedAuthorityOperation,
) -> None:
    """The import clock is two years later and does not make the filing late."""
    deadline = resolve_effective_filing_deadline(
        _MODELO, _FILING_YEAR, Period.from_year_and_code(_FILING_YEAR, _PERIOD_CODE), operation=operation
    )
    assert deadline is not None
    presented_on = deadline.closes_on
    presented_at = datetime(presented_on.year, presented_on.month, presented_on.day, 10, 0, tzinfo=UTC)

    assert _timeliness(aeat_register=_register(presented_at), operation=operation) is FilingTimeliness.EN_PLAZO


def test_a_presentation_after_the_window_is_extemporanea(operation: PinnedAuthorityOperation) -> None:
    """The observed date past the effective close decides it."""
    deadline = resolve_effective_filing_deadline(
        _MODELO, _FILING_YEAR, Period.from_year_and_code(_FILING_YEAR, _PERIOD_CODE), operation=operation
    )
    assert deadline is not None
    presented_on = deadline.closes_on + timedelta(days=1)
    presented_at = datetime(presented_on.year, presented_on.month, presented_on.day, 10, 0, tzinfo=UTC)

    assert _timeliness(aeat_register=_register(presented_at), operation=operation) is FilingTimeliness.EXTEMPORANEA


def test_the_observed_instant_is_read_on_the_spanish_civil_date(operation: PinnedAuthorityOperation) -> None:
    """22:30 UTC on the closing day is the next Spanish day, so the filing is late."""
    deadline = resolve_effective_filing_deadline(
        _MODELO, _FILING_YEAR, Period.from_year_and_code(_FILING_YEAR, _PERIOD_CODE), operation=operation
    )
    assert deadline is not None
    presented_at = datetime(
        deadline.closes_on.year, deadline.closes_on.month, deadline.closes_on.day, 22, 30, tzinfo=UTC
    )

    assert presented_at.date() == deadline.closes_on
    assert _timeliness(aeat_register=_register(presented_at), operation=operation) is FilingTimeliness.EXTEMPORANEA


@pytest.mark.parametrize("aeat_register", [None, _register(None)], ids=["no-register", "register-without-date"])
def test_without_an_observed_presentation_date_the_posture_is_unknown(
    aeat_register: AeatRegisterRef | None,
    operation: PinnedAuthorityOperation,
) -> None:
    """An absent observed date is unknown, never the import clock's answer."""
    assert _timeliness(aeat_register=aeat_register, operation=operation) is FilingTimeliness.UNKNOWN


def test_an_imported_rectificativa_keeps_an_unknown_posture(operation: PinnedAuthorityOperation) -> None:
    """The declaration-kind policy applies to imported entries too."""
    deadline = resolve_effective_filing_deadline(
        _MODELO, _FILING_YEAR, Period.from_year_and_code(_FILING_YEAR, _PERIOD_CODE), operation=operation
    )
    assert deadline is not None
    presented_on = deadline.closes_on + timedelta(days=30)
    presented_at = datetime(presented_on.year, presented_on.month, presented_on.day, 10, 0, tzinfo=UTC)

    assert (
        _timeliness(
            aeat_register=_register(presented_at),
            operation=operation,
            declaration_kind=FilingDeclarationKind.RECTIFICATIVA,
        )
        is FilingTimeliness.UNKNOWN
    )
