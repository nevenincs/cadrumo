"""An imported AEAT filing's posture comes from when AEAT says it was presented.

An AEAT-origin chain entry records a declaration someone already presented. The
import's own clock says when the reconstruction ran, so judging lateness on it
would call every reconstruction of an old filing extemporánea. The register's
observed presentation date is the only date that answers the question, and
without one the posture stays unknown: an import that cannot say when the
declaration was presented cannot say whether it was presented in time.

The filing axis and its revision are scanned from the published authority, not
named here: the supported years and each modelo's editions are declared once in
the registry.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from ....core.filing_timeliness import FilingTimeliness
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.irpf_income_categories import require_irpf_income_category
from ....domain.calculations.registry.tests.published_authority import published_selected_revision_id
from ....domain.contribuyente.entity_type import require_entity_type
from ....domain.deadlines.models import IVARegime, TaxpayerProfile
from ....domain.deadlines.tests.effective_close_scan import ScannedObligation, obligation_with_a_shifted_close
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
_REVISION_SHA = "a" * 64
_CSV = "ABCD1234EFGH5678"
#: Days between the observed presentation and the import run, so the import
#: clock is plainly a different date from the presentation it records.
_IMPORT_LAG_DAYS = 900


def _scan_profile() -> TaxpayerProfile:
    return TaxpayerProfile.model_validate(
        {
            "tax_id": "X0001500M",
            "entity_type": require_entity_type("natural_person"),
            "irpf_income_categories": frozenset({require_irpf_income_category("actividad_economica")}),
            "iva_regime": IVARegime("GENERAL"),
            "has_employees": True,
            "pays_rent_with_retencion": True,
        },
    )


@pytest.fixture(name="scanned")
def _scanned(operation: PinnedAuthorityOperation) -> ScannedObligation:
    """A real filing window whose close moves to the next business day."""
    return obligation_with_a_shifted_close(_scan_profile(), operation=operation)


def _work_unit(scanned: ScannedObligation) -> WorkUnit:
    modelo = str(scanned.obligation.modelo)
    period: Period = scanned.obligation.period
    revision_id = published_selected_revision_id(modelo, filing_year=period.filing_year, period=period.registry_token)
    created = datetime(period.filing_year, 1, 1, tzinfo=UTC)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo=modelo,
            filing_year=period.filing_year,
            period=period,
            revision_id=revision_id,
        ),
        bucket_id=_BUCKET_ID,
        modelo=modelo,
        filing_year=period.filing_year,
        period=period,
        revision_id=revision_id,
        name=f"imported {modelo} {period.registry_token}",
        created_at=created,
        updated_at=created,
    )


def _register(presented_at: datetime | None) -> AeatRegisterRef:
    """A valid register reference; one needs an expediente id or a CSV."""
    return AeatRegisterRef(csv=_CSV, presented_at=presented_at)


def _timeliness(
    scanned: ScannedObligation,
    *,
    aeat_register: AeatRegisterRef | None,
    operation: PinnedAuthorityOperation,
    declaration_kind: FilingDeclarationKind = FilingDeclarationKind.ORIGINAL,
) -> FilingTimeliness | None:
    unit = _work_unit(scanned)
    imported_at = datetime(
        scanned.effective_closes_on.year,
        scanned.effective_closes_on.month,
        scanned.effective_closes_on.day,
        8,
        0,
        tzinfo=UTC,
    ) + timedelta(days=_IMPORT_LAG_DAYS)
    record = build_external_filing_record(
        filing_record_id=derive_filing_record_id(
            work_unit_id=unit.work_unit_id,
            calculation_revision_id=_REVISION_SHA,
            filed_by="aeat-import",
        ),
        work_unit=unit,
        calculation_revision_id=_REVISION_SHA,
        filed_at=imported_at,
        filed_by="aeat-import",
        evidence_kind=ExternalEvidenceKind.AEAT_CSV_REGISTER,
        evidence_reference_id="TEST-CSV-REGISTER",
        declaration_kind=declaration_kind,
        operation=operation,
        aeat_register=aeat_register,
    )
    assert record.filed_at == imported_at
    assert record.filed_at.date() > scanned.effective_closes_on, "the import clock is a later date than the filing"
    return record.filing_timeliness


def _presented_at(scanned: ScannedObligation, *, days_after_close: int, hour: int = 10) -> datetime:
    day = scanned.effective_closes_on + timedelta(days=days_after_close)
    return datetime(day.year, day.month, day.day, hour, 0, tzinfo=UTC)


def test_a_presentation_inside_the_window_is_timely_however_late_the_import_ran(
    scanned: ScannedObligation,
    operation: PinnedAuthorityOperation,
) -> None:
    """The import clock is years later and does not make the filing late."""
    presented_at = _presented_at(scanned, days_after_close=0)

    assert _timeliness(scanned, aeat_register=_register(presented_at), operation=operation) is (
        FilingTimeliness.EN_PLAZO
    )


def test_a_presentation_after_the_window_is_extemporanea(
    scanned: ScannedObligation,
    operation: PinnedAuthorityOperation,
) -> None:
    """The observed date past the effective close decides it."""
    presented_at = _presented_at(scanned, days_after_close=1)

    assert _timeliness(scanned, aeat_register=_register(presented_at), operation=operation) is (
        FilingTimeliness.EXTEMPORANEA
    )


def test_the_observed_instant_is_read_on_the_spanish_civil_date(
    scanned: ScannedObligation,
    operation: PinnedAuthorityOperation,
) -> None:
    """23:30 UTC on the closing day is the next Spanish day, so the filing is late."""
    presented_at = _presented_at(scanned, days_after_close=0, hour=23)

    assert presented_at.date() == scanned.effective_closes_on
    assert _timeliness(scanned, aeat_register=_register(presented_at), operation=operation) is (
        FilingTimeliness.EXTEMPORANEA
    )


@pytest.mark.parametrize("with_register", [False, True], ids=["no-register", "register-without-date"])
def test_without_an_observed_presentation_date_the_posture_is_unknown(
    with_register: bool,
    scanned: ScannedObligation,
    operation: PinnedAuthorityOperation,
) -> None:
    """An absent observed date is unknown, never the import clock's answer."""
    aeat_register = _register(None) if with_register else None

    assert _timeliness(scanned, aeat_register=aeat_register, operation=operation) is FilingTimeliness.UNKNOWN


def test_an_imported_rectificativa_keeps_an_unknown_posture(
    scanned: ScannedObligation,
    operation: PinnedAuthorityOperation,
) -> None:
    """The declaration-kind policy applies to imported entries too."""
    presented_at = _presented_at(scanned, days_after_close=30)

    assert (
        _timeliness(
            scanned,
            aeat_register=_register(presented_at),
            operation=operation,
            declaration_kind=FilingDeclarationKind.RECTIFICATIVA,
        )
        is FilingTimeliness.UNKNOWN
    )
