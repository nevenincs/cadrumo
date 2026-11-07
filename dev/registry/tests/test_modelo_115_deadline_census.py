"""Modelo 115 deadline census over the supported filing years.

The fleet deadline projection is an eager validated-authority capability, so
this census reads the development compiler's validated authority.
"""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.domain.calculations.registry.temporal import select_revision
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope, open_ended_revision

from ..compiler.authority import compiled_bundled_authority
from ..conformance.registry_schema_support import committed_modelo
from .monthly_deadline_support import MONTHLY_RETENCION_DEADLINES
from .quarterly_deadline_support import QUARTERLY_RETENCION_DEADLINES

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_OPEN_ENDED_REVISION = str(open_ended_revision("115").id)


def test_modelo_115_supported_year_deadline_census_dates_sources_and_ownership() -> None:
    modelo, _ = committed_modelo("115")
    revision = modelo.revisions[_OPEN_ENDED_REVISION]
    horizon = filing_year_envelope().horizon
    windows = {(window.filing_year, window.period.registry_token): window for window in revision.deadline_windows}

    assert len(revision.deadline_windows) == len(windows) == 80
    assert set(revision.constructs[0].deadline_windows) == {window.id for window in revision.deadline_windows}

    for filing_year in QUARTERLY_RETENCION_DEADLINES:
        monthly_periods = tuple(f"{month:02d}" for month in range(1, 13))
        expected_periods = {*monthly_periods, "1T", "2T", "3T", "4T"}
        assert {period for year, period in windows if year == filing_year} == expected_periods
        projected = compiled_bundled_authority().deadline_windows(filing_year, modelos=("115",))
        assert len(projected) == 16
        assert {window.period.registry_token for _, _, window in projected} == expected_periods
        assert {selected.id for _, selected, _ in projected} == {_OPEN_ENDED_REVISION}

        expected = {
            **{
                f"{month:02d}": close_text
                for month, (close_text, _cutoff_text) in enumerate(
                    MONTHLY_RETENCION_DEADLINES[filing_year],
                    start=1,
                )
            },
            **{
                f"{quarter}T": close_text
                for quarter, (close_text, _cutoff_text) in enumerate(
                    QUARTERLY_RETENCION_DEADLINES[filing_year],
                    start=1,
                )
            },
        }
        for period, close_text in expected.items():
            window = windows[(filing_year, period)]
            assert select_revision(modelo, filing_year=filing_year, period=period) is revision
            assert window.id == f"modelo-115-{filing_year}-{period.lower()}"
            assert window.filing_year == window.period.filing_year == filing_year
            assert window.opens_on == date(window.closes_on.year, window.closes_on.month, 1)
            assert window.closes_on == date.fromisoformat(close_text)
            expected_sources = {"aeat-modelo-115-guia-censal"}
            if window.closes_on.year <= horizon:
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
        for quarter, (_close_text, cutoff_text) in enumerate(QUARTERLY_RETENCION_DEADLINES[filing_year], start=1):
            quarterly = windows[(filing_year, f"{quarter}T")]
            assert quarterly.payment_cutoff_on == (None if cutoff_text is None else date.fromisoformat(cutoff_text))
        for period in monthly_periods:
            assert windows[(filing_year, period)].payment_cutoff_on is None

    assert windows[(horizon, "4T")].payment_cutoff_on is None
