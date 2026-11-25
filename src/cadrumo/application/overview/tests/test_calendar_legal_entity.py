"""Legal-entity calendar coverage for the overview application facade."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....domain.calculations.registry.applicability import derive_modelo_applicability
from ....domain.calculations.registry.applicability_modelo202 import (
    modelo_202_incn_threshold_decimal,
    resolve_modelo_202_art_40_3_incn_threshold,
)
from ....domain.calculations.registry.applicability_models import ApplicabilityVerdict
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.errors import RegistryFailureCondition
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.contribuyente.entity_type import EntityType
from ....domain.contribuyente.renta_codes import FiscalResidency
from ....domain.deadlines.models import IVARegime, ModeloEnrollment, TaxpayerProfile
from ..calendar import build_overview_calendar
from ..calendar_models import OverviewCalendarRange, SuppressedCalendarEntry
from .calendar_test_support import profile as calendar_autonomo

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_YEAR = filing_year_envelope().horizon


def _legal_entity() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="B00015016",
        entity_type=EntityType.from_registry("legal_entity"),
        iva_regime=IVARegime("GENERAL"),
        has_employees=False,
        pays_professionals_with_retencion=False,
        art109_activity_income_withholding_ge_70pct=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        third_party_transactions_above_347_threshold=False,
        bienes_extranjero_above_threshold=False,
        fiscal_residency=FiscalResidency.from_registry("resident_irpf"),
        enrollment=ModeloEnrollment(large_company=False),
        regimen_entidades_navieras_tonelaje=False,
    )


def _legal_entity_with_incn(incn: Decimal | None) -> TaxpayerProfile:
    return _legal_entity().model_copy(update={"incn_prior_12_months": incn})


def _art_40_3_threshold(operation: PinnedAuthorityOperation, year: int) -> Decimal:
    return modelo_202_incn_threshold_decimal(
        resolve_modelo_202_art_40_3_incn_threshold(effective_date=date(year, 12, 31), authority=operation),
    )


def _modelo_202_calendar(
    profile: TaxpayerProfile,
    year: int,
    operation: PinnedAuthorityOperation,
) -> tuple[set[str], list[SuppressedCalendarEntry]]:
    """Return the year's surfaced 202 periods and its suppressed 202 rows."""
    rng = OverviewCalendarRange(from_date=date(year, 1, 1), to_date=date(year, 12, 31))
    cal = build_overview_calendar(profile, rng, operation=operation, today=date(year, 1, 1), show_suppressed=True)
    surfaced = {entry.period.registry_token for entry in cal.entries if entry.modelo == "202"}
    suppressed = [entry for entry in cal.suppressed_entries if entry.modelo == "202"]
    return surfaced, suppressed


def test_calendar_modelo_202_applies_when_incn_exceeds_the_art_40_3_threshold(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Above the threshold the order makes filing mandatory in every period, even with no ingreso."""
    for year in filing_year_envelope().years:
        above = _art_40_3_threshold(authority_operation, year) + Decimal("0.01")
        surfaced, suppressed = _modelo_202_calendar(_legal_entity_with_incn(above), year, authority_operation)
        assert surfaced == {"1P", "2P", "3P"}, year
        assert suppressed == [], year


def test_calendar_modelo_202_is_incomplete_when_filing_depends_on_an_ingreso(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """At or below the threshold filing is owed only when the period yields an ingreso, which the profile cannot tell."""
    for year in filing_year_envelope().years:
        at_threshold = _art_40_3_threshold(authority_operation, year)
        for incn in (at_threshold, Decimal(0)):
            surfaced, suppressed = _modelo_202_calendar(_legal_entity_with_incn(incn), year, authority_operation)
            assert surfaced == set(), (year, incn)
            assert {entry.period.registry_token for entry in suppressed} == {"1P", "2P", "3P"}, (year, incn)
            assert all(entry.verdict is ApplicabilityVerdict.INCOMPLETE for entry in suppressed), (year, incn)
            assert all("ingreso" in entry.reason for entry in suppressed), (year, incn)


def test_calendar_modelo_202_is_incomplete_when_incn_is_undeclared(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """An undeclared INCN leaves the modality, and with it the filing obligation, unknown."""
    profile = _legal_entity_with_incn(None)
    for year in filing_year_envelope().years:
        surfaced, suppressed = _modelo_202_calendar(profile, year, authority_operation)
        assert surfaced == set(), year
        assert {entry.period.registry_token for entry in suppressed} == {"1P", "2P", "3P"}, year
        assert all(entry.verdict is ApplicabilityVerdict.INCOMPLETE for entry in suppressed), year
        applicability = derive_modelo_applicability(
            profile, "202", reference_date=date(year, 12, 31), operation=authority_operation
        )
        assert applicability.failure is not None, year
        assert applicability.failure.condition is RegistryFailureCondition.MODELO_202_INCN_DECLARED, year


def test_calendar_modelo_202_is_not_applicable_outside_the_impuesto_sobre_sociedades(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A natural person files no Modelo 202 whatever the INCN, so the threshold never promotes it."""
    for year in filing_year_envelope().years:
        above = _art_40_3_threshold(authority_operation, year) + Decimal("0.01")
        autonomo = calendar_autonomo().model_copy(update={"incn_prior_12_months": above})
        surfaced, suppressed = _modelo_202_calendar(autonomo, year, authority_operation)
        # The 202 filing schedule names legal entities, so no window is scheduled to suppress.
        assert surfaced == set(), year
        assert suppressed == [], year
        applicability = derive_modelo_applicability(
            autonomo, "202", reference_date=date(year, 12, 31), operation=authority_operation
        )
        assert applicability.verdict is ApplicabilityVerdict.NOT_APPLICABLE, year


def test_calendar_legal_entity_shows_modelo_200_impuesto_sociedades(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    rng = OverviewCalendarRange(from_date=date(_YEAR, 1, 1), to_date=date(_YEAR, 12, 31))
    cal = build_overview_calendar(_legal_entity(), rng, operation=authority_operation, today=date(_YEAR, 4, 1))

    surfaced = {entry.modelo for entry in cal.entries}
    assert "200" in surfaced, (
        "M200 (IS annual) must appear for a LEGAL_ENTITY profile querying its filing year; "
        "absent means covered_years() did not include the prior fiscal year"
    )
