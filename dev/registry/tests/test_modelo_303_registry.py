"""Tests for the committed Modelo 303 (IVA autoliquidacion) registry foundation."""

from __future__ import annotations

import re
from datetime import date, timedelta

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.errors import FilingYearOutsideSupportEnvelopeError
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_catalogues import RegistryCatalogues
from cadrumo.domain.calculations.registry.temporal import select_revision
from cadrumo.domain.calculations.registry.tests.authored_editions import (
    authored_revisions,
    filing_year_envelope,
    open_ended_revision,
    revision_covering,
    split_exercise_revisions,
)
from cadrumo.domain.calculations.registry.tests.modelo_303_registry_constants import (
    M303_RECORD_DESIGN_LAYOUT_MODIFICATION_LEGAL_REF,
    M303_SUPPORTED_EDITION_IDS,
    m303_annual_orden_source,
    m303_extraction_profile_target_legal_refs,
    m303_record_design_source,
)
from cadrumo.domain.calculations.registry.tests.snapshot_support import build_snapshot
from cadrumo.domain.deadlines.domiciliation_cutoff import DerivedPaymentCutoff, resolve_payment_cutoff

from .authored_edition_support import source_first_exercise, source_with_sha256
from .modelo_303_registry_support import load_modelo_303
from .profile_schema_support import committed_registry_validator

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("governed_fact_scope")]

_FLOOR_REVISION_ID = str(revision_covering("303", filing_year_envelope().floor).id)
_NEWEST = open_ended_revision("303")
# The two exercises whose forms were re-laid mid-year: the early and later revision of each.
_SPLIT_2T_3T = split_exercise_revisions("303", early_period="2T", late_period="3T")
_SPLIT_1T_2T = split_exercise_revisions("303", early_period="1T", late_period="2T")
_SPLIT_IDS = {str(revision.id) for pair in (_SPLIT_2T_3T, _SPLIT_1T_2T) for revision in pair}
#: The editions authored for exactly one whole exercise, oldest first.
_WHOLE_YEAR_REVISIONS = tuple(revision for revision in authored_revisions("303") if str(revision.id) not in _SPLIT_IDS)
_LAST_WHOLE_YEAR = _WHOLE_YEAR_REVISIONS[-1]
_ALL_PERIODS = ("1T", "2T", "3T", "4T", "01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12")


def test_modelo_303_registry_validator_accepts_committed_definition() -> None:
    modelo, catalogues = load_modelo_303()
    assert modelo.id == "303"
    assert modelo.revisions, "303 must declare at least one revision"
    assert any(rev.casillas for rev in modelo.revisions.values()), "303 must declare casillas"
    committed_registry_validator(catalogues).validate_modelo(modelo)


def test_modelo_303_metadata_matches_orden_eha_3786_2008() -> None:
    modelo, catalogues = load_modelo_303()

    assert modelo.title == "IVA. Autoliquidación (trimestral)"
    assert modelo.tax_domain == "iva"
    assert modelo.cadence == "quarterly"
    assert modelo.jurisdiction == "ES-AEAT"
    assert "orden-eha-3786-2008:art-1" in modelo.legal_refs
    assert "orden-eha-3786-2008:art-7" in modelo.legal_refs
    assert m303_record_design_source(str(_LAST_WHOLE_YEAR.id)) in modelo.source_refs
    assert "aeat-modelo-303-procedure" in modelo.source_refs
    assert catalogues.sources["aeat-modelo-303-procedure"].evidence_tier == "official_source_guidance"
    assert catalogues.sources["boe-modelo-303-2008-form"].evidence_tier == "layout_authority"


def _scheduled_periods(revision: ModeloRevision) -> tuple[str, ...]:
    """Return the periods the revision's own filing schedules declare, in order."""
    ordered: list[str] = []
    for schedule in revision.filing_schedules:
        for period in schedule.periods:
            if period not in ordered:
                ordered.append(period)
    return tuple(ordered)


def test_modelo_303_revision_period_selectors_cover_the_supported_span() -> None:
    """Each revision claims exactly the filing year(s) it is named for.

    The earliest revision used to span 2009-2022 and this asserted that. The
    pre-window span was deliberately retired when it was renamed to `2022`, so
    the supported floor is now filing year 2022. Eight bundled designs
    (2014 through 2021) currently have no revision citing them; that is a scope
    question about the supported floor, recorded rather than reverted here.
    """
    modelo, _ = load_modelo_303()

    floor_revision = modelo.revisions[_FLOOR_REVISION_ID]
    floor = filing_year_envelope().floor
    assert floor_revision.valid_from == date(floor, 1, 1)
    assert floor_revision.valid_to == date(floor, 12, 31)
    assert floor_revision.period_selector.year_from == floor
    assert floor_revision.period_selector.year_to == floor
    # The edition admits both cadences: its quarterly and monthly filing
    # schedules together are exactly what the selector claims.
    assert floor_revision.period_selector.periods == _scheduled_periods(floor_revision)

    for metadata in _WHOLE_YEAR_REVISIONS:
        revision = modelo.revisions[str(metadata.id)]
        year = metadata.valid_from.year
        assert revision.valid_from == date(year, 1, 1), revision.id
        assert revision.valid_to == date(year, 12, 31), revision.id
        assert revision.period_selector.year_from == year, revision.id
        assert revision.period_selector.year_to == year, revision.id
        if str(metadata.id) != _FLOOR_REVISION_ID:
            assert revision.period_selector.periods == _ALL_PERIODS, revision.id

    # The span is carried per revision rather than assumed to run January to
    # December. The first split exercise is a MID-YEAR split -- AEAT re-laid the form from
    # period 09 / 3T -- so its two revisions meet at 31 August / 1 September, and
    # that boundary is the whole content of the split. Asserting a uniform
    # 1 January - 31 December span erased it and reddened on the revision the
    # split created.
    early_metadata, late_metadata = _SPLIT_2T_3T
    early = modelo.revisions[str(early_metadata.id)]
    late = modelo.revisions[str(late_metadata.id)]
    split_year = early_metadata.valid_from.year
    assert (early.valid_from, early.valid_to) == (date(split_year, 1, 1), date(split_year, 8, 31))
    assert (late.valid_from, late.valid_to) == (date(split_year, 9, 1), date(split_year, 12, 31))
    for revision, periods in (
        (early, ("1T", "2T", "01", "02", "03", "04", "05", "06", "07", "08")),
        (late, ("3T", "4T", "09", "10", "11", "12")),
    ):
        assert revision.period_selector.year_from == split_year
        assert revision.period_selector.year_to == split_year
        assert revision.period_selector.periods == periods

    # The two split revisions must MEET, with no gap and no overlap: the day one
    # ends is the day before the other begins.
    assert early.valid_to == late.valid_from - timedelta(days=1)

    rev_early_metadata, rev_current_metadata = _SPLIT_1T_2T
    rev_current = modelo.revisions[str(rev_current_metadata.id)]
    rev_early = modelo.revisions[str(rev_early_metadata.id)]
    year = rev_early_metadata.valid_from.year
    assert rev_early.valid_from == date(year, 1, 1)
    assert rev_early.valid_to == date(year, 3, 31)
    assert rev_early.period_selector.periods_for_year(year) == ("01", "1T")
    assert rev_current.valid_from == date(year, 2, 1)
    assert rev_current.period_selector.year_from == year
    assert rev_current.period_selector.year_to is None
    assert rev_current.period_selector.periods_for_year(year) == (
        "02",
        "03",
        "04",
        "05",
        "06",
        "07",
        "08",
        "09",
        "10",
        "11",
        "12",
        "2T",
        "3T",
        "4T",
    )
    assert rev_current.period_selector.periods_for_year(year + 1) == rev_current.period_selector.periods
    assert {"01", "1T", "12", "4T"} <= set(rev_current.period_selector.periods_for_year(year + 1))


def test_modelo_303_snapshot_builds_for_each_quarter() -> None:
    modelo, catalogues = load_modelo_303()

    for metadata in _WHOLE_YEAR_REVISIONS:
        for period in ("1T", "2T", "3T", "4T"):
            snapshot = build_snapshot(
                modelo,
                catalogues,
                source_root=bundled_path(),
                filing_year=metadata.valid_from.year,
                period=period,
            )
            assert snapshot.revision.id == str(metadata.id)

    early_metadata, late_metadata = _SPLIT_2T_3T
    expected_split_revisions = {
        "1T": early_metadata,
        "2T": early_metadata,
        "3T": late_metadata,
        "4T": late_metadata,
        "01": early_metadata,
        "08": early_metadata,
        "09": late_metadata,
        "12": late_metadata,
    }
    for period, expected_revision in expected_split_revisions.items():
        snapshot = build_snapshot(
            modelo,
            catalogues,
            source_root=bundled_path(),
            filing_year=early_metadata.valid_from.year,
            period=period,
        )
        assert snapshot.revision.id == str(expected_revision.id)

    rev_early_metadata, rev_current_metadata = _SPLIT_1T_2T
    for period in ("1T", "2T", "3T", "4T"):
        snapshot = build_snapshot(
            modelo,
            catalogues,
            source_root=bundled_path(),
            filing_year=rev_current_metadata.valid_from.year,
            period=period,
        )
        assert snapshot.revision.id == str(rev_early_metadata.id if period == "1T" else rev_current_metadata.id)

    # The retirement of the span below the floor is asserted, not merely worked around: the floor
    # refuses rather than silently resolving an earlier filing under the floor edition's norms.
    with pytest.raises(FilingYearOutsideSupportEnvelopeError):
        build_snapshot(
            modelo,
            catalogues,
            source_root=bundled_path(),
            filing_year=filing_year_envelope().floor - 1,
            period="1T",
        )


def _assert_further_sources_are_cited_forms(revision: ModeloRevision, catalogues: RegistryCatalogues) -> None:
    """Every revision-level source past the four fixed ones is a printed form one of the edition's formulas cites."""
    formula_sources = {ref for formula in revision.formulas for ref in formula.source_refs}
    for further in revision.source_refs[4:]:
        assert catalogues.sources[further].kind == "form_spec", (revision.id, further)
        assert further in formula_sources, (revision.id, further)


def test_modelo_303_explicit_record_design_revisions_have_one_exact_source() -> None:
    """Each design has its own primary source, never a fallback.

    The design and the annual Orden are the ones whose applicability opens the
    edition. A further revision-level source is only a printed BOE form that one
    of the edition's own formulas cites, as the January and first-quarter edition
    does for the prior form annex it is still filed on.
    """
    modelo, catalogues = load_modelo_303()

    for revision_id in M303_SUPPORTED_EDITION_IDS:
        revision = modelo.revisions[revision_id]
        record_design_source = m303_record_design_source(revision_id)
        annual_orden_source = m303_annual_orden_source(revision_id)

        assert revision.source_refs[:4] == (
            record_design_source,
            "aeat-modelo-303-procedure",
            annual_orden_source,
            "boe-modelo-303-2008-form",
        ), revision_id
        _assert_further_sources_are_cited_forms(revision, catalogues)
        assert len(revision.workbook_parity_refs) == 1
        parity = revision.workbook_parity_refs[0]
        # The parity id is authored per revision (the 2024 split names its two
        # halves early/late), so what it proves is asserted through the design
        # it names rather than through the shape of its id.
        assert parity.id.startswith("modelo-303-dr")
        assert parity.workbook_source == record_design_source
        assert parity.source_refs == (record_design_source,)


def test_modelo_303_snapshot_carries_legal_authority_and_record_design() -> None:
    modelo, catalogues = load_modelo_303()
    snapshot = build_snapshot(
        modelo, catalogues, source_root=bundled_path(), filing_year=_LAST_WHOLE_YEAR.valid_from.year, period="1T"
    )

    assert "orden-eha-3786-2008:art-1" in snapshot.legal
    assert "orden-eha-3786-2008:art-7" in snapshot.legal
    assert snapshot.legal["orden-eha-3786-2008:art-7"].article == "7"
    assert m303_record_design_source(str(_LAST_WHOLE_YEAR.id)) in snapshot.sources
    assert "aeat-modelo-303-procedure" in snapshot.sources
    assert "boe-modelo-303-2008-form" in snapshot.sources


def test_modelo_303_extraction_profile_legal_refs_match_target_casillas() -> None:
    modelo, _ = load_modelo_303()
    for revision_id in M303_SUPPORTED_EDITION_IDS:
        expected_refs = m303_extraction_profile_target_legal_refs(revision_id)
        revision = modelo.revisions[revision_id]
        casillas_by_id = {casilla.id: casilla for casilla in revision.casillas}

        assert revision.extraction_profiles, revision_id
        profile = next(item for item in revision.extraction_profiles if item.id == "modelo-303-declaracion-pdf")
        target_refs = frozenset(
            legal_ref
            for target in profile.target_casillas
            for legal_ref in casillas_by_id[target.casilla_id].legal_refs
        )

        assert target_refs == expected_refs
        assert set(profile.legal_refs) == expected_refs


def test_modelo_303_layout_modification_authority_starts_only_with_the_late_split_design() -> None:
    """Reject both the fabricated authority and any backdated layout grounding."""
    modelo, catalogues = load_modelo_303()

    assert "orden-hac-819-2024:art-1" not in catalogues.legal
    authority = catalogues.legal[M303_RECORD_DESIGN_LAYOUT_MODIFICATION_LEGAL_REF]
    assert authority.document_id == "BOE-A-2024-16129"
    assert authority.article == "único"
    order_page = (bundled_path() / authority.corpus_ref.partition("#")[0]).read_text(encoding="utf-8")
    ((day, month, year),) = re.findall(r"Fecha de entrada en vigor: (\d{2})/(\d{2})/(\d{4})", order_page)
    assert authority.effective_from == date(int(year), int(month), int(day))

    split_at = M303_SUPPORTED_EDITION_IDS.index(str(_SPLIT_2T_3T[1].id))
    for revision_id in M303_SUPPORTED_EDITION_IDS[:split_at]:
        construct = next(
            item for item in modelo.revisions[revision_id].constructs if item.id == "modelo-303-iva-autoliquidacion"
        )
        assert M303_RECORD_DESIGN_LAYOUT_MODIFICATION_LEGAL_REF not in construct.legal_refs

    for revision_id in M303_SUPPORTED_EDITION_IDS[split_at:]:
        construct = next(
            item for item in modelo.revisions[revision_id].constructs if item.id == "modelo-303-iva-autoliquidacion"
        )
        assert M303_RECORD_DESIGN_LAYOUT_MODIFICATION_LEGAL_REF in construct.legal_refs


def test_modelo_303_quarterly_deadlines_match_orden_eha_3786_2008_art_7() -> None:
    """1T-3T close on day 20; 4T closes on day 30 of January following."""
    modelo, _ = load_modelo_303()
    prior_year = _LAST_WHOLE_YEAR.valid_from.year
    current_year = _NEWEST.valid_from.year
    prior_windows = {w.id: w for w in modelo.revisions[str(_LAST_WHOLE_YEAR.id)].deadline_windows}
    # (month, day) each quarter opens and closes; the fourth quarter falls in the following year.
    prior_days = (((4, 1), (4, 21)), ((7, 1), (7, 21)), ((10, 1), (10, 20)), ((1, 1), (1, 30)))
    current_days = (((4, 1), (4, 20)), ((7, 1), (7, 20)), ((10, 1), (10, 20)), ((1, 1), (2, 1)))

    def expected_windows(year, days):
        return {
            f"modelo-303-{year}-{quarter}t": tuple(
                date(year + (quarter == 4), *month_day) for month_day in quarter_days
            )
            for quarter, quarter_days in enumerate(days, start=1)
        }

    for window_id, (opens, closes) in expected_windows(prior_year, prior_days).items():
        assert prior_windows[window_id].opens_on == opens
        assert prior_windows[window_id].closes_on == closes
    for window_id, (opens, closes) in expected_windows(current_year, current_days).items():
        period = window_id.rsplit("-", 1)[1].upper()
        owner = select_revision(modelo, filing_year=current_year, period=period)
        window = next(window for window in owner.deadline_windows if window.id == window_id)
        assert window.opens_on == opens
        assert window.closes_on == closes


# The exercise whose AEAT calendario del contribuyente grounds the deadline days checked
# below, found by the calendar's pinned bytes. Its fourth quarter and December are
# filed under the following exercise's calendar.
_CALENDAR_EXERCISE = source_first_exercise(
    source_with_sha256("4c3810a801129ea6651fd09de84ea628db9c984ec02b19d3c9fca6c7737a8eac")
)


def test_modelo_303_calendar_exercise_deadlines_exactly_cover_declared_quarterly_and_monthly_schedules() -> None:
    """The calendar exercise's owner carries one AEAT-grounded row per declared period token."""
    year = _CALENDAR_EXERCISE
    modelo, _ = load_modelo_303()
    revision = modelo.revisions[str(year)]
    windows_by_period = {window.period.registry_token: window for window in revision.deadline_windows}
    expected = {
        "1T": (date(year, 4, 1), date(year, 4, 20), date(year, 4, 15)),
        "2T": (date(year, 7, 1), date(year, 7, 20), date(year, 7, 15)),
        "3T": (date(year, 10, 1), date(year, 10, 20), date(year, 10, 15)),
        "4T": (date(year + 1, 1, 1), date(year + 1, 1, 30), date(year + 1, 1, 25)),
        "01": (date(year, 2, 1), date(year, 2, 28), date(year, 2, 23)),
        "02": (date(year, 3, 1), date(year, 3, 30), date(year, 3, 25)),
        "03": (date(year, 4, 1), date(year, 5, 2), date(year, 4, 25)),
        "04": (date(year, 5, 1), date(year, 5, 30), date(year, 5, 25)),
        "05": (date(year, 6, 1), date(year, 6, 30), date(year, 6, 25)),
        "06": (date(year, 7, 1), date(year, 7, 31), date(year, 7, 26)),
        "07": (date(year, 8, 1), date(year, 8, 30), date(year, 8, 25)),
        "08": (date(year, 9, 1), date(year, 10, 2), date(year, 9, 27)),
        "09": (date(year, 10, 1), date(year, 10, 30), date(year, 10, 25)),
        "10": (date(year, 11, 1), date(year, 11, 30), date(year, 11, 25)),
        "11": (date(year, 12, 1), date(year + 1, 1, 2), date(year, 12, 26)),
        "12": (date(year + 1, 1, 1), date(year + 1, 1, 30), date(year + 1, 1, 25)),
    }

    assert len(revision.deadline_windows) == len(expected) == 16
    assert set(windows_by_period) == set(expected)
    assert set(windows_by_period) == set(revision.period_selector.periods)
    for period, dates in expected.items():
        window = windows_by_period[period]
        assert (window.opens_on, window.closes_on, window.payment_cutoff_on) == dates
        assert window.filing_year == window.period.filing_year == year
        assert window.id == f"modelo-303-{year}-{period.lower()}{'-mensual' if period.isdigit() else ''}"
        calendar_source = (
            f"aeat-calendario-contribuyente-{year + 1}"
            if period in {"4T", "12"}
            else f"aeat-calendario-contribuyente-{year}"
        )
        assert calendar_source in window.source_refs


def test_modelo_303_calendar_exercise_deadline_coordinates_have_only_the_canonical_owner() -> None:
    year = _CALENDAR_EXERCISE
    modelo, _ = load_modelo_303()
    expected_periods = set(modelo.revisions[str(year)].period_selector.periods)
    owners_by_period = {
        period: [
            revision.id
            for revision in modelo.revisions.values()
            if any(
                window.filing_year == year and window.period.registry_token == period
                for window in revision.deadline_windows
            )
        ]
        for period in expected_periods
    }

    assert owners_by_period == {period: [str(year)] for period in expected_periods}


def test_modelo_303_historical_deadline_census_is_exact_and_canonically_owned() -> None:
    """Every published coordinate of the exercises the calendar tests do not ground has one owner and exact dates."""
    modelo, _ = load_modelo_303()
    # (year offset, month, day) of each period's opening, close and domiciled-payment cutoff, for the
    # supported exercises the calendar-exercise tests below do not ground, in envelope order.
    census_days = (
        {
            "1T": ((0, 4, 1), (0, 4, 20), (0, 4, 15)),
            "2T": ((0, 7, 1), (0, 7, 20), (0, 7, 15)),
            "3T": ((0, 10, 1), (0, 10, 20), (0, 10, 15)),
            "4T": ((1, 1, 1), (1, 1, 30), (1, 1, 25)),
        },
        {
            "1T": ((0, 4, 1), (0, 4, 22), (0, 4, 17)),
            "2T": ((0, 7, 1), (0, 7, 22), (0, 7, 17)),
            "3T": ((0, 10, 1), (0, 10, 21), (0, 10, 16)),
            "4T": ((1, 1, 1), (1, 1, 30), (1, 1, 27)),
            "01": ((0, 2, 1), (0, 2, 29), (0, 2, 26)),
            "02": ((0, 3, 1), (0, 4, 1), (0, 3, 25)),
            "03": ((0, 4, 1), (0, 4, 30), (0, 4, 25)),
            "04": ((0, 5, 1), (0, 5, 30), (0, 5, 27)),
            "05": ((0, 6, 1), (0, 7, 1), (0, 6, 26)),
            "06": ((0, 7, 1), (0, 7, 30), (0, 7, 25)),
            "07": ((0, 8, 1), (0, 8, 30), (0, 8, 27)),
            "08": ((0, 9, 1), (0, 9, 30), (0, 9, 25)),
            "09": ((0, 10, 1), (0, 10, 30), (0, 10, 25)),
            "10": ((0, 11, 1), (0, 12, 2), (0, 11, 27)),
            "11": ((0, 12, 1), (0, 12, 30), (0, 12, 25)),
            "12": ((1, 1, 1), (1, 1, 30), (1, 1, 27)),
        },
        {
            "1T": ((0, 4, 1), (0, 4, 21), (0, 4, 15)),
            "2T": ((0, 7, 1), (0, 7, 21), (0, 7, 16)),
            "3T": ((0, 10, 1), (0, 10, 20), (0, 10, 15)),
            "4T": ((1, 1, 1), (1, 1, 30), (1, 1, 27)),
            "01": ((0, 2, 1), (0, 2, 28), (0, 2, 25)),
            "02": ((0, 3, 1), (0, 3, 31), (0, 3, 26)),
            "03": ((0, 4, 1), (0, 4, 30), (0, 4, 25)),
            "04": ((0, 5, 1), (0, 5, 30), (0, 5, 27)),
            "05": ((0, 6, 1), (0, 6, 30), (0, 6, 25)),
            "06": ((0, 7, 1), (0, 7, 30), (0, 7, 25)),
            "07": ((0, 8, 1), (0, 9, 1), (0, 8, 27)),
            "08": ((0, 9, 1), (0, 9, 30), (0, 9, 25)),
            "09": ((0, 10, 1), (0, 10, 30), (0, 10, 27)),
            "10": ((0, 11, 1), (0, 12, 1), (0, 11, 26)),
            "11": ((0, 12, 1), (0, 12, 30), (0, 12, 25)),
            "12": ((1, 1, 1), (1, 1, 30), (1, 1, 27)),
        },
    )
    census_years = tuple(
        year for year in filing_year_envelope().years if year not in {_CALENDAR_EXERCISE, _SII_CALENDAR_EXERCISE}
    )
    expected = {
        filing_year: {
            period: tuple(date(filing_year + offset, month, day) for offset, month, day in triple)
            for period, triple in days.items()
        }
        for filing_year, days in zip(census_years, census_days, strict=True)
    }

    for filing_year, expected_by_period in expected.items():
        actual_by_period = {
            window.period.registry_token: window
            for revision in modelo.revisions.values()
            for window in revision.deadline_windows
            if window.filing_year == filing_year
        }
        # Coverage is the year's own declared periods -- both cadences -- while the
        # table below carries the dates that are grounded one by one.
        selector_periods = {
            period
            for revision in modelo.revisions.values()
            if revision.period_selector.includes_year(filing_year)
            for period in revision.period_selector.periods
        }
        assert set(actual_by_period) == selector_periods
        assert set(expected_by_period) <= selector_periods
        for period, dates in expected_by_period.items():
            owner = select_revision(modelo, filing_year=filing_year, period=period)
            window = actual_by_period[period]
            assert window in owner.deadline_windows
            assert (window.opens_on, window.closes_on, window.payment_cutoff_on) == dates


def test_modelo_303_open_ended_revision_supported_periods_are_fully_materialised() -> None:
    modelo, _ = load_modelo_303()
    revision = modelo.revisions[str(_NEWEST.id)]
    opening_year = revision.valid_from.year
    authored = {
        window.period.registry_token for window in revision.deadline_windows if window.filing_year == opening_year
    }

    assert authored == set(revision.period_selector.periods_for_year(opening_year))


# The exercise whose AEAT domiciliacion calendar grounds the SII monthly deadline
# days checked below, found by the calendar's pinned bytes.
_SII_CALENDAR_EXERCISE = source_first_exercise(
    source_with_sha256("02b6e745820b1083de32fb2c325ba465806987bf093c9a59e7e5782f42beb469")
)


def test_modelo_303_sii_monthly_deadlines_are_exactly_grounded() -> None:
    year = _SII_CALENDAR_EXERCISE
    modelo, _ = load_modelo_303()
    windows = {
        window.id: window
        for month in range(1, 13)
        for window in select_revision(modelo, filing_year=year, period=f"{month:02}").deadline_windows
    }
    expected = {
        f"modelo-303-{year}-01-mensual": (date(year, 2, 1), date(year, 3, 2), date(year, 2, 25)),
        f"modelo-303-{year}-02-mensual": (date(year, 3, 1), date(year, 3, 30), date(year, 3, 25)),
        f"modelo-303-{year}-03-mensual": (date(year, 4, 1), date(year, 4, 30), date(year, 4, 27)),
        f"modelo-303-{year}-04-mensual": (date(year, 5, 1), date(year, 6, 1), date(year, 5, 27)),
        f"modelo-303-{year}-05-mensual": (date(year, 6, 1), date(year, 6, 30), date(year, 6, 25)),
        f"modelo-303-{year}-06-mensual": (date(year, 7, 1), date(year, 7, 30), date(year, 7, 27)),
        f"modelo-303-{year}-07-mensual": (date(year, 8, 1), date(year, 8, 31), date(year, 8, 26)),
        f"modelo-303-{year}-08-mensual": (date(year, 9, 1), date(year, 9, 30), date(year, 9, 25)),
        f"modelo-303-{year}-09-mensual": (date(year, 10, 1), date(year, 10, 30), date(year, 10, 27)),
        f"modelo-303-{year}-10-mensual": (date(year, 11, 1), date(year, 11, 30), date(year, 11, 25)),
        f"modelo-303-{year}-11-mensual": (date(year, 12, 1), date(year, 12, 30), date(year, 12, 24)),
        # The calendar prints no direct-debit row for December; its cutoff waits on the next
        # year's calendar, so none is authored on the window.
        f"modelo-303-{year}-12-mensual": (date(year + 1, 1, 1), date(year + 1, 2, 1), None),
    }

    for window_id, (opens_on, closes_on, payment_cutoff_on) in expected.items():
        window = windows[window_id]
        assert window.opens_on == opens_on
        assert window.closes_on == closes_on
        assert window.payment_cutoff_on == payment_cutoff_on
        assert (
            "aeat-modelo-303-procedure"
            if window.id == f"modelo-303-{year}-12-mensual"
            else f"aeat-calendario-contribuyente-{year}-domiciliacion"
        ) in window.source_refs

    # With no authored cutoff, the Orden derives December's: Anexo II's 25 January, extended by
    # the two days the filing period runs past its Saturday close (art. 3.2.b).
    with bundled_indexed_authority().operation() as operation:
        resolved = resolve_payment_cutoff("303", windows[f"modelo-303-{year}-12-mensual"], operation=operation)
    assert isinstance(resolved, DerivedPaymentCutoff)
    assert resolved.extension_days == 2
    assert resolved.cutoff_on == date(year + 1, 1, 27)

    assert f"aeat-calendario-contribuyente-{year}-hasta-2-marzo" in windows[f"modelo-303-{year}-01-mensual"].source_refs
