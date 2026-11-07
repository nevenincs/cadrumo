"""Deadline-window regressions for the complete supported Modelo 202 corpus."""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.core.period import PeriodKind, registry_period_kind
from cadrumo.domain.calculations.registry.temporal import select_revision
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.domain.calculations.registry.tests.registry_tree import bundled_registry_tree

from .profile_schema_support import committed_registry_validator

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("governed_fact_scope")]


# Per supported filing year, in envelope order: each instalment's (month, day) opening, official close
# and domiciliación cutoff, all inside the filing year.
_DEADLINE_DAYS_BY_SUPPORTED_YEAR = (
    (((4, 1), (4, 20), (4, 15)), ((10, 1), (10, 20), (10, 15)), ((12, 1), (12, 20), (12, 15))),
    (((4, 1), (4, 20), (4, 15)), ((10, 1), (10, 20), (10, 15)), ((12, 1), (12, 20), (12, 15))),
    (((4, 1), (4, 22), (4, 17)), ((10, 1), (10, 21), (10, 16)), ((12, 1), (12, 20), (12, 17))),
    (((4, 1), (4, 21), (4, 15)), ((10, 1), (10, 20), (10, 15)), ((12, 1), (12, 22), (12, 17))),
    (((4, 1), (4, 20), (4, 15)), ((10, 1), (10, 20), (10, 15)), ((12, 1), (12, 21), (12, 15))),
)
_EXPECTED_WINDOWS = {
    (year, f"{instalment}P"): tuple(date(year, *month_day) for month_day in month_days)
    for year, per_year in zip(filing_year_envelope().years, _DEADLINE_DAYS_BY_SUPPORTED_YEAR, strict=True)
    for instalment, month_days in enumerate(per_year, start=1)
}


def test_committed_modelo_202_has_exact_supported_year_deadline_census() -> None:
    """Bundled AEAT calendars publish each exact M202/M222 date and cutoff."""
    modelos, catalogues = bundled_registry_tree()
    modelo = next(item for item in modelos if item.id == "202")
    committed_registry_validator(catalogues).validate_modelo(modelo)

    observed = {
        (window.period.filing_year, window.period.registry_token): (
            window.opens_on,
            window.closes_on,
            window.payment_cutoff_on,
        )
        for revision in modelo.revisions.values()
        for window in revision.deadline_windows
        if window.period.filing_year in filing_year_envelope().years
    }

    assert observed == _EXPECTED_WINDOWS


def test_committed_modelo_202_windows_use_canonical_periods_sources_and_owners() -> None:
    modelos, _catalogues = bundled_registry_tree()
    modelo = next(item for item in modelos if item.id == "202")
    windows = [
        (revision, window)
        for revision in modelo.revisions.values()
        for window in revision.deadline_windows
        if window.period.filing_year in filing_year_envelope().years
    ]
    assert len(windows) == len(_EXPECTED_WINDOWS)

    for revision, window in windows:
        filing_year = window.period.filing_year
        period = window.period.registry_token
        calendar_ref = f"aeat-calendario-contribuyente-{filing_year}"

        assert window.id == f"modelo-202-{filing_year}-{period.lower()}"
        assert window.filing_year == filing_year
        assert registry_period_kind(period) is PeriodKind.INSTALMENT
        assert window.period.kind is PeriodKind.INSTALMENT
        assert window.period_kind == "quarterly"
        assert calendar_ref in window.source_refs
        assert calendar_ref in revision.source_refs
        assert calendar_ref in revision.constructs[0].source_refs
        assert select_revision(modelo, filing_year=filing_year, period=period) is revision
