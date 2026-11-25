"""Modelo 115 deadline census over the supported filing years.

The fleet deadline projection is an eager validated-authority capability, so
this census reads the development compiler's validated authority.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.temporal import select_revision
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope, open_ended_revision

from ..compiler.authority import compiled_bundled_authority
from ..conformance.registry_schema_support import committed_modelo
from .retencion_deadline_support import (
    MONTHLY_PERIODS,
    QUARTERLY_PERIODS,
    RETENCION_PERIODS,
    calendar_is_bundled,
    expected_close,
    expected_cutoff,
)

if TYPE_CHECKING:
    from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_modelo_115_supported_year_deadline_census_dates_sources_and_ownership() -> None:
    with bundled_indexed_authority().operation() as operation:
        _check_supported_year_deadlines(operation)


def _check_supported_year_deadlines(operation: PinnedAuthorityOperation) -> None:
    modelo, _ = committed_modelo("115")
    revision = modelo.revisions[open_ended_revision("115").id]
    windows = {(window.filing_year, window.period.registry_token): window for window in revision.deadline_windows}

    assert len(revision.deadline_windows) == len(windows) == len(RETENCION_PERIODS) * len(filing_year_envelope().years)
    assert set(revision.constructs[0].deadline_windows) == {window.id for window in revision.deadline_windows}

    for filing_year in filing_year_envelope().years:
        expected_periods = set(RETENCION_PERIODS)
        assert {period for year, period in windows if year == filing_year} == expected_periods
        projected = compiled_bundled_authority().deadline_windows(filing_year, modelos=("115",))
        assert len(projected) == 16
        assert {window.period.registry_token for _, _, window in projected} == expected_periods
        assert {selected.id for _, selected, _ in projected} == {revision.id}

        for period in RETENCION_PERIODS:
            window = windows[(filing_year, period)]
            assert select_revision(modelo, filing_year=filing_year, period=period) is revision
            assert window.id == f"modelo-115-{filing_year}-{period.lower()}"
            assert window.filing_year == window.period.filing_year == filing_year
            assert window.opens_on == date(window.closes_on.year, window.closes_on.month, 1)
            assert window.closes_on == expected_close(operation, "115", filing_year, period)
            expected_sources = {"aeat-modelo-115-guia-censal"}
            if calendar_is_bundled(window.closes_on.year):
                expected_sources.add(f"aeat-calendario-contribuyente-{window.closes_on.year}")
            else:
                # No bundled calendar covers this close, so the statutory
                # twentieth day of RIRPF art. 108 carries it. The folleto de
                # actividades states only the trimestral plazo, so it grounds
                # the quarterly window and must not be claimed for the monthly
                # one, whose plazo is paragraph two of the same article.
                expected_sources.add("boe-rirpf-art-108-retencion-deadline")
                if window.period_kind == "quarterly":
                    expected_sources.add("aeat-modelo-115-180-folleto-actividades")
            assert set(window.source_refs) == expected_sources
            assert len(window.applicability_conditions) == 1
            assert window.applicability_conditions[0].field == "pays_rent_with_retencion"

        # The quarterly cadence authors its domiciliación day; the monthly one
        # does not, because the governed deadlines.domiciliation-cutoff-clause
        # fact already declares this modelo's monthly Anexo II day. Asserting
        # the absence keeps a later per-month restatement from passing silently.
        for period in QUARTERLY_PERIODS:
            assert windows[(filing_year, period)].payment_cutoff_on == expected_cutoff(filing_year, period)
        for period in MONTHLY_PERIODS:
            assert windows[(filing_year, period)].payment_cutoff_on is None

    assert windows[(filing_year_envelope().horizon, "4T")].payment_cutoff_on is None
