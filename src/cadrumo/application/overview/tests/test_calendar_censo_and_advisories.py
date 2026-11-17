"""Unit tests for the overview-calendar censo warnings and filing-obligation advisories."""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

import pytest

from ....core.config import override_settings
from ....core.i18n.render import I18N_STRICT_MISSING_KEYS
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.published_authority import (
    PublishedGovernedFactSource,
)
from ....domain.contribuyente.entity_type import EntityType, LegalEntityForm
from ....domain.contribuyente.renta_codes import FiscalResidency
from ....domain.deadlines.models import (
    IVARegime,
    TaxpayerProfile,
)
from ....tests.log_records import delivered_records
from ..calendar import (
    build_overview_calendar,
)
from ..calendar_models import (
    OverviewCalendarRange,
    OverviewCensoEnrolmentState,
)
from ..calendar_warnings import calendar_applicability_profile_keys_for_modelo
from ..read_calendar_item_projection import OverviewCalendarWarningSnapshot
from ..status_report import build_filing_obligation_advisories
from .calendar_test_support import (
    profile as calendar_profile,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SUPPORT = PublishedGovernedFactSource().supported_filing_years()
_YEAR = _SUPPORT.horizon


_M303_CENSO_ENROLMENT_KEYS = frozenset(
    {
        "activities.iae_epigraph",
        "iva.regime",
        "taxpayer_type.entity_type",
        "taxpayer_type.irpf_income_categories",
    },
)


_M202_CENSO_ENROLMENT_KEYS = frozenset(
    {
        "taxpayer_type.entity_type",
        "taxpayer_type.incn_prior_12_months",
        "taxpayer_type.legal_entity_form",
        "taxpayer_type.new_entity_first_two_profit_periods",
    },
)


def test_calendar_censo_warning_requires_every_modelo_enrolment_key(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    applicability_303 = set(
        calendar_applicability_profile_keys_for_modelo("303", operation=authority_operation),
    )
    assert _M303_CENSO_ENROLMENT_KEYS - {"activities.iae_epigraph"} <= applicability_303

    calendar = build_overview_calendar(
        calendar_profile(),
        OverviewCalendarRange(from_date=date(_YEAR, 4, 1), to_date=date(_YEAR, 4, 20)),
        operation=authority_operation,
        today=date(_YEAR, 4, 1),
        live_censo_verified_profile_keys=tuple(sorted(_M303_CENSO_ENROLMENT_KEYS - {"iva.regime"})),
    )

    assert any(entry.modelo == "303" for entry in calendar.entries)
    modelo_303 = next(entry for entry in calendar.entries if entry.modelo == "303")
    assert modelo_303.censo_enrolment_state is OverviewCensoEnrolmentState.UNVERIFIED
    warning = next(item for item in calendar.warnings if item.code == "censo.enrolment_unverified")
    assert "303" in warning.affected_modelos


@pytest.mark.parametrize(
    ("language", "terms"),
    [
        ("en", ("census", "not", "verified")),
        ("es", ("censo", "no", "verificado")),
        ("ca", ("cens", "no", "verificat")),
        ("hu", ("nyilvántartásba", "nem", "ellenőrizték")),
    ],
)
def test_calendar_censo_warning_is_rendered_in_the_read_language(
    authority_operation: PinnedAuthorityOperation, language: str, terms: tuple[str, ...]
) -> None:
    calendar = build_overview_calendar(
        calendar_profile(),
        OverviewCalendarRange(from_date=date(_YEAR, 4, 1), to_date=date(_YEAR, 4, 20)),
        operation=authority_operation,
        today=date(_YEAR, 4, 1),
        live_censo_verified_profile_keys=tuple(sorted(_M303_CENSO_ENROLMENT_KEYS - {"iva.regime"})),
    )
    warning = next(item for item in calendar.warnings if item.code == "censo.enrolment_unverified")
    assert "303" in warning.affected_modelos

    token = I18N_STRICT_MISSING_KEYS.set(True)
    try:
        with override_settings(cadrumo_output_language=language):
            text = OverviewCalendarWarningSnapshot.from_warning(warning).text
    finally:
        I18N_STRICT_MISSING_KEYS.reset(token)

    assert text is not None
    assert all(term in text.lower() for term in terms)


def test_calendar_censo_warning_clears_when_every_modelo_enrolment_key_is_verified(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    calendar = build_overview_calendar(
        calendar_profile(),
        OverviewCalendarRange(from_date=date(_YEAR, 4, 1), to_date=date(_YEAR, 4, 20)),
        operation=authority_operation,
        today=date(_YEAR, 4, 1),
        live_censo_verified_profile_keys=tuple(sorted(_M303_CENSO_ENROLMENT_KEYS)),
    )

    assert any(entry.modelo == "303" for entry in calendar.entries)
    modelo_303 = next(entry for entry in calendar.entries if entry.modelo == "303")
    assert modelo_303.censo_enrolment_state is OverviewCensoEnrolmentState.VERIFIED
    censo_warnings = [item for item in calendar.warnings if item.code == "censo.enrolment_unverified"]
    assert not any("303" in warning.affected_modelos for warning in censo_warnings)


def test_calendar_keeps_unverified_posture_when_no_censo_is_verified(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Retirement guard: with the live censo scrape retired, nothing stamps a
    censo-verified fact, so the calendar keeps its honest ``censo.enrolment_unverified``
    posture for every censo-dependent modelo when the verified-key set is empty.

    Pins the honest default: an empty ``live_censo_verified_profile_keys`` (the
    post-retirement reality) must never grant a VERIFIED enrolment state.
    """
    calendar = build_overview_calendar(
        calendar_profile(),
        OverviewCalendarRange(from_date=date(_YEAR, 1, 1), to_date=date(_YEAR, 12, 31)),
        operation=authority_operation,
        today=date(_YEAR, 1, 1),
        live_censo_verified_profile_keys=(),
    )

    censo_dependent = {"100", "130", "303", "390"}
    present = {entry.modelo for entry in calendar.entries} & censo_dependent
    assert present, "fixture must yield at least one censo-dependent modelo"

    for entry in calendar.entries:
        assert entry.censo_enrolment_state is not OverviewCensoEnrolmentState.VERIFIED

    warning = next(item for item in calendar.warnings if item.code == "censo.enrolment_unverified")
    for modelo in present:
        entry = next(item for item in calendar.entries if item.modelo == modelo)
        assert entry.censo_enrolment_state is OverviewCensoEnrolmentState.UNVERIFIED
        assert modelo in warning.affected_modelos


def test_calendar_entry_marks_censo_enrolment_not_checked_when_no_live_censo_scope(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    calendar = build_overview_calendar(
        calendar_profile(),
        OverviewCalendarRange(from_date=date(_YEAR, 4, 1), to_date=date(_YEAR, 4, 20)),
        operation=authority_operation,
        today=date(_YEAR, 4, 1),
    )

    modelo_303 = next(entry for entry in calendar.entries if entry.modelo == "303")
    assert modelo_303.censo_enrolment_state is OverviewCensoEnrolmentState.NOT_CHECKED
    assert "censo.enrolment_unverified" not in {warning.code for warning in calendar.warnings}


def _corporate_profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="B00015016",
        entity_type=EntityType.from_registry("legal_entity"),
        legal_entity_form=LegalEntityForm.from_registry("SL"),
        iva_regime=IVARegime("GENERAL"),
        incn_prior_12_months=Decimal("7500000.00"),
        # Modelo 202 names the residencies it applies to, so the entity
        # states its own: unanswered, the pago fraccionado is incomplete and
        # the censo axes under test never get a row to be judged against.
        fiscal_residency=FiscalResidency.from_registry("resident_irpf"),
    )


def test_calendar_censo_warning_requires_corporate_modelo_202_enrolment_keys(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    applicability_202 = set(
        calendar_applicability_profile_keys_for_modelo("202", operation=authority_operation),
    )
    assert applicability_202 >= _M202_CENSO_ENROLMENT_KEYS

    calendar = build_overview_calendar(
        _corporate_profile(),
        OverviewCalendarRange(from_date=date(_YEAR, 4, 1), to_date=date(_YEAR, 4, 20)),
        operation=authority_operation,
        today=date(_YEAR, 4, 1),
        live_censo_verified_profile_keys=tuple(
            sorted(_M202_CENSO_ENROLMENT_KEYS - {"taxpayer_type.incn_prior_12_months"}),
        ),
    )

    assert any(entry.modelo == "202" for entry in calendar.entries)
    warning = next(item for item in calendar.warnings if item.code == "censo.enrolment_unverified")
    assert "202" in warning.affected_modelos


def test_calendar_censo_warning_clears_for_complete_corporate_modelo_202_provenance(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    calendar = build_overview_calendar(
        _corporate_profile(),
        OverviewCalendarRange(from_date=date(_YEAR, 4, 1), to_date=date(_YEAR, 4, 20)),
        operation=authority_operation,
        today=date(_YEAR, 4, 1),
        live_censo_verified_profile_keys=tuple(sorted(_M202_CENSO_ENROLMENT_KEYS)),
    )

    assert any(entry.modelo == "202" for entry in calendar.entries)
    censo_warnings = [item for item in calendar.warnings if item.code == "censo.enrolment_unverified"]
    assert not any("202" in warning.affected_modelos for warning in censo_warnings)


_INVALID_PAGADORES_ADVISORY_CASES: tuple[tuple[str, dict[str, str], str, str, str], ...] = (
    (
        "not-a-count-secret",
        {
            "irpf.pagadores_count": "not-a-count-secret",
            "irpf.pagadores_secondary_income": "1700",
        },
        "overview filing obligation advisory ignored invalid integer profile value",
        "irpf.pagadores_count",
        "ValueError",
    ),
    (
        "not-income-secret",
        {
            "irpf.pagadores_count": "2",
            "irpf.pagadores_secondary_income": "not-income-secret",
        },
        "overview filing obligation advisory ignored invalid decimal profile value",
        "irpf.pagadores_secondary_income",
        "InvalidOperation",
    ),
)


@pytest.mark.parametrize(
    ("raw_value", "profile_values", "expected_message", "expected_field", "expected_error_type"),
    _INVALID_PAGADORES_ADVISORY_CASES,
    ids=("invalid-count", "invalid-secondary-income"),
)
def test_invalid_pagadores_values_are_debug_logged_without_raw_value(
    caplog: pytest.LogCaptureFixture,
    authority_operation: PinnedAuthorityOperation,
    raw_value: str,
    profile_values: dict[str, str],
    expected_message: str,
    expected_field: str,
    expected_error_type: str,
) -> None:
    with caplog.at_level(logging.DEBUG, logger="cadrumo.application.overview"):
        advisories = build_filing_obligation_advisories(profile_values, operation=authority_operation)

    assert advisories == ()
    delivered = delivered_records(caplog)
    relevant = [record for record in delivered if record.getMessage() == expected_message]
    assert len(relevant) == 1
    assert relevant[0].__dict__["profile_field"] == expected_field
    assert relevant[0].__dict__["error_type"] == expected_error_type
    assert all(raw_value not in record.getMessage() for record in delivered)


_MULTIPLE_PAGADORES_OBLIGATION_KEY = "cli.overview.status.filing_obligation_multiple_pagadores"


@pytest.mark.parametrize("filing_year", _SUPPORT.years)
def test_multi_payer_over_reduced_limit_surfaces_obligation_advisory(
    authority_operation: PinnedAuthorityOperation,
    filing_year: int,
) -> None:
    # 2 pagadores, secondary €1,600 > €1,500, total €18,000 over the reduced
    # limit (€15,876 or lower in earlier exercises) → the Art. 96.3 LIRPF obligation advisory fires.
    advisories = build_filing_obligation_advisories(
        {
            "irpf.pagadores_count": "2",
            "irpf.pagadores_secondary_income": "1600",
            "irpf.pagadores_total_work_income": "18000",
        },
        filing_year=filing_year,
        operation=authority_operation,
    )
    assert advisories == (_MULTIPLE_PAGADORES_OBLIGATION_KEY,)


@pytest.mark.parametrize("filing_year", _SUPPORT.years)
def test_multi_payer_under_reduced_limit_does_not_surface_advisory(
    authority_operation: PinnedAuthorityOperation,
    filing_year: int,
) -> None:
    # Same multiple-pagadores trigger but total €10,000 is below the reduced
    # limit → not obliged, no advisory.
    advisories = build_filing_obligation_advisories(
        {
            "irpf.pagadores_count": "2",
            "irpf.pagadores_secondary_income": "1600",
            "irpf.pagadores_total_work_income": "10000",
        },
        filing_year=filing_year,
        operation=authority_operation,
    )
    assert advisories == ()


@pytest.mark.parametrize("filing_year", _SUPPORT.years)
def test_single_payer_under_general_limit_does_not_surface_advisory(
    authority_operation: PinnedAuthorityOperation,
    filing_year: int,
) -> None:
    # 1 pagador, total €18,000 below the general €22,000 → no obligation.
    advisories = build_filing_obligation_advisories(
        {
            "irpf.pagadores_count": "1",
            "irpf.pagadores_secondary_income": "0",
            "irpf.pagadores_total_work_income": "18000",
        },
        filing_year=filing_year,
        operation=authority_operation,
    )
    assert advisories == ()


@pytest.mark.parametrize("filing_year", _SUPPORT.years)
def test_multi_payer_total_undeclared_surfaces_conservatively(
    authority_operation: PinnedAuthorityOperation,
    filing_year: int,
) -> None:
    # Total work income undeclared but the multiple-pagadores trigger is met →
    # the advisory surfaces conservatively rather than granting a false clear.
    advisories = build_filing_obligation_advisories(
        {
            "irpf.pagadores_count": "2",
            "irpf.pagadores_secondary_income": "1600",
        },
        filing_year=filing_year,
        operation=authority_operation,
    )
    assert advisories == (_MULTIPLE_PAGADORES_OBLIGATION_KEY,)


def test_obligation_advisory_key_resolves_to_a_translation() -> None:
    # The surfaced key must resolve to a real (non-humanised-fallback) locale
    # string in every shipped locale — the half-shipped gap this closes.
    from ....core.i18n.render import tr

    rendered = tr(_MULTIPLE_PAGADORES_OBLIGATION_KEY)
    # Cites the binding provision and names the form; not the humanised fallback.
    assert "96.3" in rendered
    assert "100" in rendered
    assert rendered != "Filing obligation multiple pagadores"
