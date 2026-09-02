"""Tests for the committed Modelo 303 (IVA autoliquidacion) registry foundation."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from .....core.resources.bundled_data import bundled_path
from .....tests.registry_snapshot import build_snapshot
from .._validate import RegistryValidator
from ..errors import NoRevisionForPeriodError
from ..temporal import select_revision
from ._modelo_303_registry_support import (
    _M303_ANNUAL_ORDEN_SOURCE_BY_REVISION,
    _M303_EXPLICIT_RECORD_DESIGN_REVISIONS,
    _M303_EXTRACTION_PROFILE_TARGET_LEGAL_REFS_BY_REVISION,
    _M303_RECORD_DESIGN_LAYOUT_MODIFICATION_LEGAL_REF,
    _M303_RECORD_DESIGN_SOURCE_BY_REVISION,
    load_modelo_303,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_modelo_303_registry_validator_accepts_committed_definition() -> None:
    modelo, catalogues = load_modelo_303()
    assert modelo.id == "303"
    assert modelo.revisions, "303 must declare at least one revision"
    assert any(rev.casillas for rev in modelo.revisions.values()), "303 must declare casillas"
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)


def test_modelo_303_metadata_matches_orden_eha_3786_2008() -> None:
    modelo, catalogues = load_modelo_303()

    assert modelo.title == "IVA. Autoliquidación (trimestral)"
    assert modelo.tax_domain == "iva"
    assert modelo.cadence == "quarterly"
    assert modelo.jurisdiction == "ES-AEAT"
    assert "orden-eha-3786-2008:art-1" in modelo.legal_refs
    assert "orden-eha-3786-2008:art-7" in modelo.legal_refs
    assert "aeat-dr-303-2025" in modelo.source_refs
    assert "aeat-modelo-303-procedure" in modelo.source_refs
    assert catalogues.sources["aeat-modelo-303-procedure"].evidence_tier == "official_source_guidance"
    assert catalogues.sources["boe-modelo-303-2008-form"].evidence_tier == "layout_authority"


def test_modelo_303_revision_period_selectors_cover_the_supported_span() -> None:
    """Each revision claims exactly the filing year(s) it is named for.

    The earliest revision used to span 2009-2022 and this asserted that. The
    pre-window span was deliberately retired when it was renamed to `2022`, so
    the supported floor is now filing year 2022. Eight bundled designs
    (2014 through 2021) currently have no revision citing them; that is a scope
    question about the supported floor, recorded rather than reverted here.
    """
    modelo, _ = load_modelo_303()

    rev_old = modelo.revisions["2022"]
    assert rev_old.valid_from == date(2022, 1, 1)
    assert rev_old.valid_to == date(2022, 12, 31)
    assert rev_old.period_selector.year_from == 2022
    assert rev_old.period_selector.year_to == 2022
    assert rev_old.period_selector.periods == ("1T", "2T", "3T", "4T")

    # The span is carried per revision rather than assumed to run January to
    # December. The 2024 pair is a MID-YEAR split -- AEAT re-laid the form from
    # period 09 / 3T -- so its two revisions meet at 31 August / 1 September, and
    # that boundary is the whole content of the split. Asserting a uniform
    # 1 January - 31 December span erased it and reddened on the revision the
    # split created.
    expected_selectors = {
        "2023": (
            date(2023, 1, 1),
            date(2023, 12, 31),
            2023,
            ("1T", "2T", "3T", "4T", "01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"),
        ),
        "2024-hasta-08-y-2t": (
            date(2024, 1, 1),
            date(2024, 8, 31),
            2024,
            ("1T", "2T", "01", "02", "03", "04", "05", "06", "07", "08"),
        ),
        "2024-desde-09-y-3t": (
            date(2024, 9, 1),
            date(2024, 12, 31),
            2024,
            ("3T", "4T", "09", "10", "11", "12"),
        ),
        "2025": (
            date(2025, 1, 1),
            date(2025, 12, 31),
            2025,
            ("1T", "2T", "3T", "4T", "01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"),
        ),
    }
    for revision_id, (valid_from, valid_to, year, periods) in expected_selectors.items():
        revision = modelo.revisions[revision_id]
        assert revision.valid_from == valid_from
        assert revision.valid_to == valid_to
        assert revision.period_selector.year_from == year
        assert revision.period_selector.year_to == year
        assert revision.period_selector.periods == periods

    # The two 2024 revisions must MEET, with no gap and no overlap: the day one
    # ends is the day before the other begins.
    early = modelo.revisions["2024-hasta-08-y-2t"]
    late = modelo.revisions["2024-desde-09-y-3t"]
    assert early.valid_to is not None
    assert late.valid_from - early.valid_to == timedelta(days=1)

    rev_current = modelo.revisions["2026-y-siguientes"]
    assert rev_current.valid_from == date(2026, 1, 1)
    assert rev_current.period_selector.year_from == 2026
    assert rev_current.period_selector.year_to is None
    assert "1T" in rev_current.period_selector.periods
    assert "4T" in rev_current.period_selector.periods
    assert "01" in rev_current.period_selector.periods
    assert "12" in rev_current.period_selector.periods


def test_modelo_303_snapshot_builds_for_each_quarter() -> None:
    modelo, catalogues = load_modelo_303()

    for period in ("1T", "2T", "3T", "4T"):
        snapshot = build_snapshot(
            modelo,
            catalogues,
            source_root=bundled_path(),
            filing_year=2025,
            period=period,
        )
        assert snapshot.revision.id == "2025"

    expected_2024_revisions = {
        "1T": "2024-hasta-08-y-2t",
        "2T": "2024-hasta-08-y-2t",
        "3T": "2024-desde-09-y-3t",
        "4T": "2024-desde-09-y-3t",
        "01": "2024-hasta-08-y-2t",
        "08": "2024-hasta-08-y-2t",
        "09": "2024-desde-09-y-3t",
        "12": "2024-desde-09-y-3t",
    }
    for period, expected_revision_id in expected_2024_revisions.items():
        snapshot = build_snapshot(
            modelo,
            catalogues,
            source_root=bundled_path(),
            filing_year=2024,
            period=period,
        )
        assert snapshot.revision.id == expected_revision_id

    for period in ("1T", "2T", "3T", "4T"):
        snapshot = build_snapshot(
            modelo,
            catalogues,
            source_root=bundled_path(),
            filing_year=2026,
            period=period,
        )
        assert snapshot.revision.id == "2026-y-siguientes"

    # Filing year 2022 resolves to the `2022` revision. This asked for 2021,
    # which the retired pre-window span used to cover and nothing covers now, so
    # it raised NoRevisionForPeriodError rather than asserting anything.
    for period in ("1T", "2T", "3T", "4T"):
        snapshot = build_snapshot(
            modelo,
            catalogues,
            source_root=bundled_path(),
            filing_year=2022,
            period=period,
        )
        assert snapshot.revision.id == "2022"

    # And the retirement is asserted, not merely worked around: the floor
    # refuses rather than silently resolving a 2021 filing under 2022's norms.
    with pytest.raises(NoRevisionForPeriodError):
        build_snapshot(
            modelo,
            catalogues,
            source_root=bundled_path(),
            filing_year=2021,
            period="1T",
        )


def test_modelo_303_explicit_record_design_revisions_have_one_exact_source() -> None:
    """Each post-2022 design has its own primary source, never a fallback."""
    modelo, _ = load_modelo_303()

    for revision_id in _M303_EXPLICIT_RECORD_DESIGN_REVISIONS:
        revision = modelo.revisions[revision_id]
        record_design_source = _M303_RECORD_DESIGN_SOURCE_BY_REVISION[revision_id]
        annual_orden_source = _M303_ANNUAL_ORDEN_SOURCE_BY_REVISION[revision_id]

        assert revision.source_refs == (
            record_design_source,
            "aeat-modelo-303-procedure",
            annual_orden_source,
            "boe-modelo-303-2008-form",
        )
        assert len(revision.workbook_parity_refs) == 1
        parity = revision.workbook_parity_refs[0]
        assert parity.id == f"modelo-303-dr-{record_design_source.removeprefix('aeat-dr-303-')}"
        assert parity.workbook_source == record_design_source
        assert parity.source_refs == (record_design_source,)


def test_modelo_303_snapshot_carries_legal_authority_and_record_design() -> None:
    modelo, catalogues = load_modelo_303()
    snapshot = build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2025, period="1T")

    assert "orden-eha-3786-2008:art-1" in snapshot.legal
    assert "orden-eha-3786-2008:art-7" in snapshot.legal
    assert snapshot.legal["orden-eha-3786-2008:art-7"].article == "7"
    assert "aeat-dr-303-2025" in snapshot.sources
    assert "aeat-modelo-303-procedure" in snapshot.sources
    assert "boe-modelo-303-2008-form" in snapshot.sources


def test_modelo_303_extraction_profile_legal_refs_match_target_casillas() -> None:
    modelo, _ = load_modelo_303()
    for revision_id, expected_refs in _M303_EXTRACTION_PROFILE_TARGET_LEGAL_REFS_BY_REVISION.items():
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


def test_modelo_303_hac_819_2024_authority_starts_only_with_late_2024_design() -> None:
    """Reject both the fabricated authority and any backdated layout grounding."""
    modelo, catalogues = load_modelo_303()

    assert "orden-hac-819-2024:art-1" not in catalogues.legal
    authority = catalogues.legal[_M303_RECORD_DESIGN_LAYOUT_MODIFICATION_LEGAL_REF]
    assert authority.document_id == "BOE-A-2024-16129"
    assert authority.article == "único"
    assert authority.effective_from == date(2024, 8, 6)

    for revision_id in ("2023", "2024-hasta-08-y-2t"):
        construct = next(
            item for item in modelo.revisions[revision_id].constructs if item.id == "modelo-303-iva-autoliquidacion"
        )
        assert _M303_RECORD_DESIGN_LAYOUT_MODIFICATION_LEGAL_REF not in construct.legal_refs

    for revision_id in ("2024-desde-09-y-3t", "2025", "2026-y-siguientes"):
        construct = next(
            item for item in modelo.revisions[revision_id].constructs if item.id == "modelo-303-iva-autoliquidacion"
        )
        assert _M303_RECORD_DESIGN_LAYOUT_MODIFICATION_LEGAL_REF in construct.legal_refs


def test_modelo_303_quarterly_deadlines_match_orden_eha_3786_2008_art_7() -> None:
    """1T-3T close on day 20; 4T closes on day 30 of January following."""
    modelo, _ = load_modelo_303()
    prior_windows = {w.id: w for w in modelo.revisions["2025"].deadline_windows}
    prior_expected = {
        "modelo-303-2025-1t": (date(2025, 4, 1), date(2025, 4, 21)),
        "modelo-303-2025-2t": (date(2025, 7, 1), date(2025, 7, 21)),
        "modelo-303-2025-3t": (date(2025, 10, 1), date(2025, 10, 20)),
        "modelo-303-2025-4t": (date(2026, 1, 1), date(2026, 1, 30)),
    }
    current_windows = {w.id: w for w in modelo.revisions["2026-y-siguientes"].deadline_windows}
    current_expected = {
        "modelo-303-2026-1t": (date(2026, 4, 1), date(2026, 4, 20)),
        "modelo-303-2026-2t": (date(2026, 7, 1), date(2026, 7, 20)),
        "modelo-303-2026-3t": (date(2026, 10, 1), date(2026, 10, 20)),
        "modelo-303-2026-4t": (date(2027, 1, 1), date(2027, 2, 1)),
    }

    for window_id, (opens, closes) in prior_expected.items():
        assert prior_windows[window_id].opens_on == opens
        assert prior_windows[window_id].closes_on == closes
    for window_id, (opens, closes) in current_expected.items():
        assert current_windows[window_id].opens_on == opens
        assert current_windows[window_id].closes_on == closes


def test_modelo_303_2023_deadlines_exactly_cover_declared_quarterly_and_monthly_schedules() -> None:
    """The 2023 owner carries one AEAT-grounded row per declared period token."""
    modelo, _ = load_modelo_303()
    revision = modelo.revisions["2023"]
    windows_by_period = {window.period.registry_token: window for window in revision.deadline_windows}
    expected = {
        "1T": (date(2023, 4, 1), date(2023, 4, 20), date(2023, 4, 15)),
        "2T": (date(2023, 7, 1), date(2023, 7, 20), date(2023, 7, 15)),
        "3T": (date(2023, 10, 1), date(2023, 10, 20), date(2023, 10, 15)),
        "4T": (date(2024, 1, 1), date(2024, 1, 30), date(2024, 1, 25)),
        "01": (date(2023, 2, 1), date(2023, 2, 28), date(2023, 2, 23)),
        "02": (date(2023, 3, 1), date(2023, 3, 30), date(2023, 3, 25)),
        "03": (date(2023, 4, 1), date(2023, 5, 2), date(2023, 4, 25)),
        "04": (date(2023, 5, 1), date(2023, 5, 30), date(2023, 5, 25)),
        "05": (date(2023, 6, 1), date(2023, 6, 30), date(2023, 6, 25)),
        "06": (date(2023, 7, 1), date(2023, 7, 31), date(2023, 7, 26)),
        "07": (date(2023, 8, 1), date(2023, 8, 30), date(2023, 8, 25)),
        "08": (date(2023, 9, 1), date(2023, 10, 2), date(2023, 9, 27)),
        "09": (date(2023, 10, 1), date(2023, 10, 30), date(2023, 10, 25)),
        "10": (date(2023, 11, 1), date(2023, 11, 30), date(2023, 11, 25)),
        "11": (date(2023, 12, 1), date(2024, 1, 2), date(2023, 12, 26)),
        "12": (date(2024, 1, 1), date(2024, 1, 30), date(2024, 1, 25)),
    }

    assert len(revision.deadline_windows) == len(expected) == 16
    assert set(windows_by_period) == set(expected)
    assert set(windows_by_period) == set(revision.period_selector.periods)
    for period, dates in expected.items():
        window = windows_by_period[period]
        assert (window.opens_on, window.closes_on, window.payment_cutoff_on) == dates
        assert window.filing_year == window.period.filing_year == 2023
        assert window.id == f"modelo-303-2023-{period.lower()}{'-mensual' if period.isdigit() else ''}"
        calendar_source = (
            "aeat-calendario-contribuyente-2024" if period in {"4T", "12"} else "aeat-calendario-contribuyente-2023"
        )
        assert calendar_source in window.source_refs


def test_modelo_303_2023_deadline_coordinates_have_only_the_canonical_2023_owner() -> None:
    modelo, _ = load_modelo_303()
    expected_periods = set(modelo.revisions["2023"].period_selector.periods)
    owners_by_period = {
        period: [
            revision.id
            for revision in modelo.revisions.values()
            if any(
                window.filing_year == 2023 and window.period.registry_token == period
                for window in revision.deadline_windows
            )
        ]
        for period in expected_periods
    }

    assert owners_by_period == {period: ["2023"] for period in expected_periods}


def test_modelo_303_historical_deadline_census_is_exact_and_canonically_owned() -> None:
    """Every published 2022/2024/2025 coordinate has one selected owner and exact dates."""
    modelo, _ = load_modelo_303()
    expected = {
        2022: {
            "1T": (date(2022, 4, 1), date(2022, 4, 20), date(2022, 4, 15)),
            "2T": (date(2022, 7, 1), date(2022, 7, 20), date(2022, 7, 15)),
            "3T": (date(2022, 10, 1), date(2022, 10, 20), date(2022, 10, 15)),
            "4T": (date(2023, 1, 1), date(2023, 1, 30), date(2023, 1, 25)),
        },
        2024: {
            "1T": (date(2024, 4, 1), date(2024, 4, 22), date(2024, 4, 17)),
            "2T": (date(2024, 7, 1), date(2024, 7, 22), date(2024, 7, 17)),
            "3T": (date(2024, 10, 1), date(2024, 10, 21), date(2024, 10, 16)),
            "4T": (date(2025, 1, 1), date(2025, 1, 30), date(2025, 1, 27)),
            "01": (date(2024, 2, 1), date(2024, 2, 29), date(2024, 2, 26)),
            "02": (date(2024, 3, 1), date(2024, 4, 1), date(2024, 3, 25)),
            "03": (date(2024, 4, 1), date(2024, 4, 30), date(2024, 4, 25)),
            "04": (date(2024, 5, 1), date(2024, 5, 30), date(2024, 5, 27)),
            "05": (date(2024, 6, 1), date(2024, 7, 1), date(2024, 6, 26)),
            "06": (date(2024, 7, 1), date(2024, 7, 30), date(2024, 7, 25)),
            "07": (date(2024, 8, 1), date(2024, 8, 30), date(2024, 8, 27)),
            "08": (date(2024, 9, 1), date(2024, 9, 30), date(2024, 9, 25)),
            "09": (date(2024, 10, 1), date(2024, 10, 30), date(2024, 10, 25)),
            "10": (date(2024, 11, 1), date(2024, 12, 2), date(2024, 11, 27)),
            "11": (date(2024, 12, 1), date(2024, 12, 30), date(2024, 12, 25)),
            "12": (date(2025, 1, 1), date(2025, 1, 30), date(2025, 1, 27)),
        },
        2025: {
            "1T": (date(2025, 4, 1), date(2025, 4, 21), date(2025, 4, 15)),
            "2T": (date(2025, 7, 1), date(2025, 7, 21), date(2025, 7, 16)),
            "3T": (date(2025, 10, 1), date(2025, 10, 20), date(2025, 10, 15)),
            "4T": (date(2026, 1, 1), date(2026, 1, 30), date(2026, 1, 27)),
            "01": (date(2025, 2, 1), date(2025, 2, 28), date(2025, 2, 25)),
            "02": (date(2025, 3, 1), date(2025, 3, 31), date(2025, 3, 26)),
            "03": (date(2025, 4, 1), date(2025, 4, 30), date(2025, 4, 25)),
            "04": (date(2025, 5, 1), date(2025, 5, 30), date(2025, 5, 27)),
            "05": (date(2025, 6, 1), date(2025, 6, 30), date(2025, 6, 25)),
            "06": (date(2025, 7, 1), date(2025, 7, 30), date(2025, 7, 25)),
            "07": (date(2025, 8, 1), date(2025, 9, 1), date(2025, 8, 27)),
            "08": (date(2025, 9, 1), date(2025, 9, 30), date(2025, 9, 25)),
            "09": (date(2025, 10, 1), date(2025, 10, 30), date(2025, 10, 27)),
            "10": (date(2025, 11, 1), date(2025, 12, 1), date(2025, 11, 26)),
            "11": (date(2025, 12, 1), date(2025, 12, 30), date(2025, 12, 25)),
            "12": (date(2026, 1, 1), date(2026, 1, 30), date(2026, 1, 27)),
        },
    }

    for filing_year, expected_by_period in expected.items():
        actual_by_period = {
            window.period.registry_token: window
            for revision in modelo.revisions.values()
            for window in revision.deadline_windows
            if window.filing_year == filing_year
        }
        assert set(actual_by_period) == set(expected_by_period)
        for period, dates in expected_by_period.items():
            owner = select_revision(modelo, filing_year=filing_year, period=period)
            window = actual_by_period[period]
            assert window in owner.deadline_windows
            assert (window.opens_on, window.closes_on, window.payment_cutoff_on) == dates


def test_modelo_303_2026_supported_periods_are_fully_materialised() -> None:
    modelo, _ = load_modelo_303()
    revision = modelo.revisions["2026-y-siguientes"]
    authored = {window.period.registry_token for window in revision.deadline_windows if window.filing_year == 2026}

    assert authored == set(revision.period_selector.periods)


def test_modelo_303_sii_2026_monthly_deadlines_are_exactly_grounded() -> None:
    modelo, _ = load_modelo_303()
    revision = modelo.revisions["2026-y-siguientes"]
    windows = {w.id: w for w in revision.deadline_windows}
    expected = {
        "modelo-303-2026-01-mensual": (date(2026, 2, 1), date(2026, 3, 2), date(2026, 2, 25)),
        "modelo-303-2026-02-mensual": (date(2026, 3, 1), date(2026, 3, 30), date(2026, 3, 25)),
        "modelo-303-2026-03-mensual": (date(2026, 4, 1), date(2026, 4, 30), date(2026, 4, 27)),
        "modelo-303-2026-04-mensual": (date(2026, 5, 1), date(2026, 6, 1), date(2026, 5, 27)),
        "modelo-303-2026-05-mensual": (date(2026, 6, 1), date(2026, 6, 30), date(2026, 6, 25)),
        "modelo-303-2026-06-mensual": (date(2026, 7, 1), date(2026, 7, 30), date(2026, 7, 27)),
        "modelo-303-2026-07-mensual": (date(2026, 8, 1), date(2026, 8, 31), date(2026, 8, 26)),
        "modelo-303-2026-08-mensual": (date(2026, 9, 1), date(2026, 9, 30), date(2026, 9, 25)),
        "modelo-303-2026-09-mensual": (date(2026, 10, 1), date(2026, 10, 30), date(2026, 10, 27)),
        "modelo-303-2026-10-mensual": (date(2026, 11, 1), date(2026, 11, 30), date(2026, 11, 25)),
        "modelo-303-2026-11-mensual": (date(2026, 12, 1), date(2026, 12, 30), date(2026, 12, 24)),
        "modelo-303-2026-12-mensual": (date(2027, 1, 1), date(2027, 2, 1), date(2027, 1, 27)),
    }

    for window_id, (opens_on, closes_on, payment_cutoff_on) in expected.items():
        window = windows[window_id]
        assert window.opens_on == opens_on
        assert window.closes_on == closes_on
        assert window.payment_cutoff_on == payment_cutoff_on
        assert (
            "aeat-modelo-303-procedure"
            if window.id == "modelo-303-2026-12-mensual"
            else "aeat-calendario-contribuyente-2026-domiciliacion"
        ) in window.source_refs

    assert "aeat-calendario-contribuyente-2026-hasta-2-marzo" in windows["modelo-303-2026-01-mensual"].source_refs
