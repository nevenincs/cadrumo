"""Registry-build gates for canonical deadline revision ownership."""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema_deadlines import DeadlineWindowDefinition, ModeloScheduleDefinition
from cadrumo.domain.calculations.registry.schema_references import PeriodSelector
from cadrumo.domain.calculations.registry.snapshot_globals import SupportedFilingYearsCatalogue
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

from ..compiler.validate_revision_rules import (
    validate_deadline_window_cadence,
    validate_deadline_window_ownership,
    validate_periodic_deadline_completeness,
)
from .profile_schema_support import committed_registry_validator
from .referential_integrity_support import minimal_catalogues, minimal_modelo, minimal_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_YEAR = filing_year_envelope().horizon


def _window(window_id: str, period: str) -> DeadlineWindowDefinition:
    return DeadlineWindowDefinition(
        id=window_id,
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, period),
        period_kind="monthly" if period.isdigit() else "quarterly",
        opens_on=date(_YEAR, 1, 1),
        closes_on=date(_YEAR, 1, 20),
        legal_refs=("ley-58-2003:art-29",),
        source_refs=("aeat-manual-modelo",),
    )


def _cutover_modelo(*, quarter_in_monthly_revision: bool):
    monthly_windows = (_window("monthly-window", "01"),)
    quarterly_windows = (_window("quarterly-window", "1T"),)
    if quarter_in_monthly_revision:
        monthly_windows += quarterly_windows
        quarterly_windows = ()

    monthly = minimal_revision(deadline_windows=monthly_windows).model_copy(
        update={
            "id": "monthly",
            "valid_from": date(_YEAR, 1, 1),
            "period_selector": PeriodSelector(year_from=_YEAR, year_to=_YEAR, periods=("01",)),
        },
    )
    quarterly = minimal_revision(deadline_windows=quarterly_windows).model_copy(
        update={
            "id": "quarterly",
            "valid_from": date(_YEAR, 1, 1),
            "period_selector": PeriodSelector(year_from=_YEAR, year_to=_YEAR, periods=("1T",)),
        },
    )
    return minimal_modelo(minimal_revision()).model_copy(
        update={"revisions": {monthly.id: monthly, quarterly.id: quarterly}},
    )


def test_period_sensitive_cutover_accepts_windows_beneath_selected_revisions() -> None:
    modelo = _cutover_modelo(quarter_in_monthly_revision=False)

    assert validate_deadline_window_ownership(modelo) == []


def test_period_sensitive_cutover_rejects_window_beneath_non_selected_revision() -> None:
    modelo = _cutover_modelo(quarter_in_monthly_revision=True)

    failures = validate_deadline_window_ownership(modelo)

    assert failures == [
        "modelo 130 revision monthly: deadline window 'quarterly-window' belongs to canonically selected "
        f"revision 'quarterly' for filing coordinate ({_YEAR}, '1T')",
    ]


def test_registry_build_routes_ownership_through_canonical_validation_pass() -> None:
    modelo = _cutover_modelo(quarter_in_monthly_revision=True)

    with pytest.raises(
        RegistryValidationError,
        match=r"deadline window 'quarterly-window' belongs to canonically selected revision 'quarterly'",
    ):
        committed_registry_validator(minimal_catalogues()).validate_modelo(modelo)


def test_registry_build_rejects_deadline_cadence_that_contradicts_canonical_period() -> None:
    contradictory = _window("contradictory-window", "01").model_copy(update={"period_kind": "quarterly"})
    revision = minimal_revision(deadline_windows=(contradictory,)).model_copy(
        update={
            "valid_from": date(_YEAR, 1, 1),
            "period_selector": PeriodSelector(year_from=_YEAR, year_to=_YEAR, periods=("01",)),
        },
    )
    modelo = minimal_modelo(revision)

    assert validate_deadline_window_cadence(modelo) == [
        "modelo 130 revision test-revision: deadline window 'contradictory-window' "
        "period_kind 'quarterly' contradicts period '01'",
    ]
    with pytest.raises(RegistryValidationError, match=r"period_kind 'quarterly' contradicts period '01'"):
        committed_registry_validator(minimal_catalogues()).validate_modelo(modelo)


def test_registry_build_accumulates_missing_and_ambiguous_canonical_owners() -> None:
    ambiguous_window = _window("ambiguous-window", "1T")
    missing_window = _window("missing-window", "0A")
    first = minimal_revision(deadline_windows=(ambiguous_window, missing_window)).model_copy(
        update={
            "id": "first",
            "valid_from": date(_YEAR, 1, 1),
            "period_selector": PeriodSelector(year_from=_YEAR, year_to=_YEAR, periods=("1T",)),
        },
    )
    second = minimal_revision().model_copy(
        update={
            "id": "second",
            "valid_from": date(_YEAR, 1, 1),
            "period_selector": PeriodSelector(year_from=_YEAR, year_to=_YEAR, periods=("1T",)),
        },
    )
    modelo = minimal_modelo(minimal_revision()).model_copy(
        update={"revisions": {first.id: first, second.id: second}},
    )

    with pytest.raises(RegistryValidationError) as excinfo:
        committed_registry_validator(minimal_catalogues()).validate_modelo(modelo)

    message = str(excinfo.value)
    assert "deadline window 'ambiguous-window' has no unique canonical owner" in message
    assert "ambiguous revision selection" in message
    assert "deadline window 'missing-window' has no unique canonical owner" in message
    assert f"modelo 130: no revision for year={_YEAR} period='0A' revision=None" in message


def test_periodic_deadline_completeness_bites_on_one_planted_missing_cell() -> None:
    schedule = ModeloScheduleDefinition(
        id="monthly",
        period_kind="monthly",
        periods=("01", "02"),
        legal_refs=("ley-58-2003:art-29",),
        source_refs=("aeat-manual-modelo",),
    )
    revision = minimal_revision(deadline_windows=(_window("january", "01"),)).model_copy(
        update={
            "valid_from": date(_YEAR, 1, 1),
            "valid_to": date(_YEAR, 12, 31),
            "period_selector": PeriodSelector(year_from=_YEAR, year_to=_YEAR, periods=("01", "02")),
            "filing_schedules": (schedule,),
        },
    )
    modelo = minimal_modelo(revision)

    assert validate_periodic_deadline_completeness(modelo, supported_filing_years=(_YEAR,)) == [
        f"modelo 130 revision test-revision: periodic filing schedule coordinate ({_YEAR}, '02') "
        "has no deadline window",
    ]

    catalogues = minimal_catalogues().model_copy(
        update={"supported_filing_years": SupportedFilingYearsCatalogue(floor=_YEAR, horizon=_YEAR)},
    )
    with pytest.raises(RegistryValidationError, match=rf"coordinate \({_YEAR}, '02'\) has no deadline window"):
        committed_registry_validator(catalogues).validate_modelo(modelo)
