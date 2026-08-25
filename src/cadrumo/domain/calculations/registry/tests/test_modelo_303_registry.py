"""Tests for the committed Modelo 303 (IVA autoliquidacion) registry foundation."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from .....core import (
    CasillaId,
    IvaDeductionEvidenceAuthority,
    IvaDeductionFactKind,
    validated_casilla_id,
)
from .....core.aggregation import BindingAggregationOp, BindingSourceKind
from .....core.resources import bundled_path
from .....tests.aeat_literal_fixtures import aeat_host
from .....tests.registry_observations import registry_grounded_modelo_observation
from ....iva import (
    IvaDeductionClassificationProvenance,
    IvaLedgerObservationRole,
)
from .. import (
    InputKind,
    ModeloDefinition,
    NoRevisionForPeriodError,
    RegistryCatalogues,
    RegistryValidator,
    binding_aggregation_op,
    build_snapshot,
    bundled_authority,
    expression_casilla_refs,
    resolve_available_bound_inputs_by_casilla_id,
    select_revision,
    selector_as_dict,
)
from .._bindings import binding_source_casilla_ids, binding_source_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]
_WWW1_HOST = aeat_host("www1")
_WWW6_HOST = aeat_host("www6")


_M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA: CasillaId = validated_casilla_id(
    "iva.compensacion-pendiente-periodos-anteriores"
)
_M303_COMPENSACION_APLICADA_CASILLA: CasillaId = validated_casilla_id("iva.compensacion-aplicada-periodo")
_M303_POSTERIOR_CASILLA: CasillaId = validated_casilla_id("iva.compensacion-pendiente-periodos-posteriores")
_M303_RESULTADO_CASILLA: CasillaId = validated_casilla_id("iva.resultado")
_M303_GENERADA_CASILLA: CasillaId = validated_casilla_id("iva.compensacion-generada-periodo")
_M303_DISPONIBLE_CASILLA: CasillaId = validated_casilla_id("iva.compensacion-disponible-fin-periodo")
_M303_AUTOCONSUMO_PROMOTOR_BASE_CASILLA: CasillaId = validated_casilla_id("iva.autoconsumo.promotor.base")
_M303_AUTOCONSUMO_PROMOTOR_CUOTA_CASILLA: CasillaId = validated_casilla_id("iva.autoconsumo.promotor.cuota")
_M303_CUOTA_DEVENGADA_TOTAL_CASILLA: CasillaId = validated_casilla_id("iva.cuota-devengada-total")
_M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA: CasillaId = validated_casilla_id("iva.cuota-deducible-total")
_M303_PRORRATA_VOLUMEN_CON_DERECHO_CASILLA: CasillaId = validated_casilla_id("iva.prorrata-volumen-con-derecho")
_M303_PRORRATA_VOLUMEN_TOTAL_CASILLA: CasillaId = validated_casilla_id("iva.prorrata-volumen-total")
_M303_PRORRATA_PORCENTAJE_CASILLA: CasillaId = validated_casilla_id("iva.prorrata-porcentaje")
_M303_BIENES_INVERSION_REGULARIZACION_CASILLA: CasillaId = validated_casilla_id("43")
_M303_BIENES_INVERSION_REGULARIZACION_BINDING = "modelo-303-bienes-inversion-regularizacion-casilla-43"
_M303_PRORRATA_REGULARIZACION_CASILLA: CasillaId = validated_casilla_id("44")
_M303_PRORRATA_REGULARIZACION_BINDING = "modelo-303-prorrata-regularizacion-casilla-44"
_M303_PRORRATA_REGULARIZACION_SOURCE_CASILLAS: tuple[CasillaId, ...] = (
    _M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA,
    _M303_PRORRATA_VOLUMEN_CON_DERECHO_CASILLA,
    _M303_PRORRATA_VOLUMEN_TOTAL_CASILLA,
    _M303_PRORRATA_PORCENTAJE_CASILLA,
)
_M303_PRORRATA_REGULARIZACION_SOURCE_PERIODS = ("1T", "2T", "3T", "4T")
_M303_EXPLICIT_RECORD_DESIGN_REVISIONS = (
    "2023",
    "2024-hasta-08-y-2t",
    "2024-desde-09-y-3t",
    "2025",
    "2026-y-siguientes",
)
_M303_RECORD_DESIGN_SOURCE_BY_REVISION = {
    # `aeat-dr-303-2022`, not 2025. The 2022 revision borrowed a later design
    # while it was still the open-ended 2009-2022 span with none of its own;
    # it now cites the 2022 diseno, which is the one that governs its year.
    "2022": "aeat-dr-303-2022",
    "2023": "aeat-dr-303-2023",
    "2024-hasta-08-y-2t": "aeat-dr-303-2024-early",
    "2024-desde-09-y-3t": "aeat-dr-303-2024-late",
    "2025": "aeat-dr-303-2025",
    "2026-y-siguientes": "aeat-dr-303-2026",
}
_M303_ANNUAL_ORDEN_SOURCE_BY_REVISION = {
    "2023": "boe-orden-hfp-1172-2022-iva-authority",
    "2024-hasta-08-y-2t": "boe-orden-hfp-1359-2023-iva-authority",
    "2024-desde-09-y-3t": "boe-orden-hfp-1359-2023-iva-authority",
    "2025": "boe-orden-hac-1347-2024-iva-authority",
    "2026-y-siguientes": "boe-orden-hac-1425-2025-iva-authority",
}
_M303_EXTRACTION_PROFILE_TARGET_LEGAL_REFS_BY_REVISION = {
    "2022": frozenset(
        {
            "ley-37-1992:art-88",
            "ley-37-1992:art-90",
            "ley-37-1992:art-91",
            "ley-37-1992:art-92",
            "ley-37-1992:art-94",
            "ley-37-1992:art-95",
            "orden-eha-3786-2008:art-1",
            "rd-1624-1992:art-71",
        }
    ),
}
_M303_CURRENT_RECORD_DESIGN_LEGAL_REFS = frozenset(
    {
        "ley-37-1992:art-88",
        "ley-37-1992:art-90",
        "ley-37-1992:art-91",
        "ley-37-1992:art-92",
        "ley-37-1992:art-94",
        "ley-37-1992:art-95",
        "ley-37-1992:art-99",
        "ley-37-1992:art-115",
        "ley-37-1992:art-116",
        "ley-37-1992:art-122",
        "ley-37-1992:art-123",
        "ley-37-1992:art-124",
        "orden-eha-3786-2008:art-1",
        "rd-1624-1992:art-29",
        "rd-1624-1992:art-30",
        "rd-1624-1992:art-71",
    }
)
_M303_RECORD_DESIGN_LAYOUT_MODIFICATION_LEGAL_REF = "orden-hac-819-2024:art-unico"
for _revision_id in _M303_EXPLICIT_RECORD_DESIGN_REVISIONS:
    _M303_EXTRACTION_PROFILE_TARGET_LEGAL_REFS_BY_REVISION[_revision_id] = _M303_CURRENT_RECORD_DESIGN_LEGAL_REFS


def _load_modelo_303() -> tuple[ModeloDefinition, RegistryCatalogues]:
    authority = bundled_authority()
    return authority.modelo("303"), authority.catalogues


def test_modelo_303_registry_validator_accepts_committed_definition() -> None:
    modelo, catalogues = _load_modelo_303()
    assert modelo.id == "303"
    assert modelo.revisions, "303 must declare at least one revision"
    assert any(rev.casillas for rev in modelo.revisions.values()), "303 must declare casillas"
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)


def test_modelo_303_metadata_matches_orden_eha_3786_2008() -> None:
    modelo, catalogues = _load_modelo_303()

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
    modelo, _ = _load_modelo_303()

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
    modelo, catalogues = _load_modelo_303()

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
    modelo, _ = _load_modelo_303()

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
    modelo, catalogues = _load_modelo_303()
    snapshot = build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2025, period="1T")

    assert "orden-eha-3786-2008:art-1" in snapshot.legal
    assert "orden-eha-3786-2008:art-7" in snapshot.legal
    assert snapshot.legal["orden-eha-3786-2008:art-7"].article == "7"
    assert "aeat-dr-303-2025" in snapshot.sources
    assert "aeat-modelo-303-procedure" in snapshot.sources
    assert "boe-modelo-303-2008-form" in snapshot.sources


def test_modelo_303_extraction_profile_legal_refs_match_target_casillas() -> None:
    modelo, _ = _load_modelo_303()
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
    modelo, catalogues = _load_modelo_303()

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
    modelo, _ = _load_modelo_303()
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
        "modelo-303-2026-4t": (date(2027, 1, 1), date(2027, 1, 30)),
    }

    for window_id, (opens, closes) in prior_expected.items():
        assert prior_windows[window_id].opens_on == opens
        assert prior_windows[window_id].closes_on == closes
    for window_id, (opens, closes) in current_expected.items():
        assert current_windows[window_id].opens_on == opens
        assert current_windows[window_id].closes_on == closes


def test_modelo_303_2023_deadlines_exactly_cover_declared_quarterly_and_monthly_schedules() -> None:
    """The 2023 owner carries one AEAT-grounded row per declared period token."""
    modelo, _ = _load_modelo_303()
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
    modelo, _ = _load_modelo_303()
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
    modelo, _ = _load_modelo_303()
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
    modelo, _ = _load_modelo_303()
    revision = modelo.revisions["2026-y-siguientes"]
    authored = {window.period.registry_token for window in revision.deadline_windows if window.filing_year == 2026}

    assert authored == set(revision.period_selector.periods)


def test_modelo_303_sii_2026_monthly_deadlines_are_exactly_grounded() -> None:
    modelo, _ = _load_modelo_303()
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
            if window.period.registry_token == "12"
            else "aeat-calendario-contribuyente-2026-domiciliacion"
        ) in window.source_refs

    assert "aeat-calendario-contribuyente-2026-hasta-2-marzo" in windows["modelo-303-2026-01-mensual"].source_refs


def test_modelo_303_live_cross_references_forbid_writes() -> None:
    modelo, _ = _load_modelo_303()
    revision = modelo.revisions["2022"]
    cross_refs = {ref.id: ref for ref in revision.live_cross_references}

    static_ref = cross_refs["modelo-303-static-documentation"]
    assert static_ref.surface == "static_official_documentation"
    assert static_ref.requires_authentication is False

    filed_ref = cross_refs["modelo-303-filed-declarations-read"]
    assert filed_ref.surface == "authenticated_read_surface"
    assert filed_ref.requires_authentication is True
    assert filed_ref.requires_aeat_authorization is True
    assert set(filed_ref.allowed_methods) == {"GET", "HEAD", "OPTIONS"}
    assert set(filed_ref.allowed_hosts) == {
        _WWW1_HOST,
        _WWW6_HOST,
    }
    forbidden = set(filed_ref.forbidden_actions)
    assert {
        "presentation",
        "signing",
        "amendment",
        "payment",
        "cancellation",
        "declaration-submission",
        "document-submission",
        "server-side-save",
    }.issubset(forbidden)


def test_modelo_303_construct_links_living_filing_and_extractor_surfaces() -> None:
    modelo, _ = _load_modelo_303()
    revision = modelo.revisions["2022"]
    construct = next(c for c in revision.constructs if c.id == "modelo-303-iva-autoliquidacion")

    assert "modelo-303-filing" in construct.application_links
    assert "modelo-303-extractor" in construct.application_links
    assert "modelo-303-deadline" in construct.application_links
    assert construct.filing_schedules == ("modelo-303-trimestral",)
    assert "modelo-303-dr-2022" in construct.workbook_parity_refs


def test_modelo_303_declares_iva_repercutido_soportado_autorepercutido_bindings() -> None:
    """Modelo 303 must declare ledger_iva_aggregation bindings for the
    three IVA flow directions so the runtime can resolve cuota
    devengada / cuota deducible / INVERSION_SUJETO_PASIVO cross-modelo."""
    modelo, _ = _load_modelo_303()
    revision = modelo.revisions["2022"]

    iva_bindings = {binding.id: binding for binding in revision.bindings if binding.source == "ledger_iva_aggregation"}
    assert "modelo-303-iva-repercutido-general-cuota" in iva_bindings
    assert "modelo-303-iva-repercutido-reducido-cuota" in iva_bindings
    assert "modelo-303-iva-repercutido-super-reducido-cuota" in iva_bindings
    assert "modelo-303-iva-soportado-interiores-cuota" in iva_bindings
    assert "modelo-303-iva-autorepercutido-intracomunitaria-cuota" in iva_bindings


def test_modelo_303_iva_bindings_resolve_end_to_end_with_substrate_observations() -> None:
    """End-to-end: a small ledger of substrate-classified observations
    aggregates to the expected per-binding totals via the
    ledger_iva_aggregation runtime resolver."""
    from decimal import Decimal

    from ....iva import (
        IvaCategory,
        IvaFlowDirection,
        IvaRateKind,
    )
    from .. import (
        IvaLedgerObservation,
        resolve_ledger_iva_aggregation_binding_values,
    )

    modelo, _ = _load_modelo_303()
    revision = modelo.revisions["2022"]

    observations = [
        IvaLedgerObservation(
            ledger_id="rep-general-1",
            transaction_date=date(2025, 6, 1),
            category=IvaCategory.DOMESTIC_GENERAL,
            rate_kind=IvaRateKind.GENERAL,
            flow_direction=IvaFlowDirection.REPERCUTIDO,
            base_amount=Decimal("1000"),
            iva_amount=Decimal("210"),
            observation_role=IvaLedgerObservationRole.SETTLEMENT,
        ),
        IvaLedgerObservation(
            ledger_id="rep-reducido-1",
            transaction_date=date(2025, 6, 3),
            category=IvaCategory.DOMESTIC_REDUCED,
            rate_kind=IvaRateKind.REDUCED,
            flow_direction=IvaFlowDirection.REPERCUTIDO,
            base_amount=Decimal("200"),
            iva_amount=Decimal("20"),
            observation_role=IvaLedgerObservationRole.SETTLEMENT,
        ),
        IvaLedgerObservation(
            ledger_id="rep-super-1",
            transaction_date=date(2025, 6, 4),
            category=IvaCategory.DOMESTIC_SUPER_REDUCED,
            rate_kind=IvaRateKind.SUPER_REDUCED,
            flow_direction=IvaFlowDirection.REPERCUTIDO,
            base_amount=Decimal("100"),
            iva_amount=Decimal("4"),
            observation_role=IvaLedgerObservationRole.SETTLEMENT,
        ),
        IvaLedgerObservation(
            ledger_id="sop-interior-1",
            transaction_date=date(2025, 6, 5),
            category=IvaCategory.DOMESTIC_GENERAL,
            rate_kind=IvaRateKind.GENERAL,
            flow_direction=IvaFlowDirection.SOPORTADO,
            base_amount=Decimal("300"),
            iva_amount=Decimal("63"),
            deduction_fact_kind=IvaDeductionFactKind.DOMESTIC_CURRENT,
            deduction_provenance=IvaDeductionClassificationProvenance(
                authority=IvaDeductionEvidenceAuthority.INVOICE_EVIDENCE,
                source_locator="test-ledger:sop-interior-1",
                evidence_digest="a" * 64,
            ),
            observation_role=IvaLedgerObservationRole.SETTLEMENT,
        ),
        IvaLedgerObservation(
            ledger_id="auto-ica-1",
            transaction_date=date(2025, 6, 6),
            category=IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
            rate_kind=IvaRateKind.GENERAL,
            flow_direction=IvaFlowDirection.INVERSION_SUJETO_PASIVO,
            base_amount=Decimal("400"),
            iva_amount=Decimal("84"),
            deduction_fact_kind=IvaDeductionFactKind.INTRA_EU_CURRENT,
            deduction_provenance=IvaDeductionClassificationProvenance(
                authority=IvaDeductionEvidenceAuthority.INTRA_EU_SELF_ASSESSMENT,
                source_locator="test-ledger:auto-ica-1",
                evidence_digest="a" * 64,
            ),
            observation_role=IvaLedgerObservationRole.SETTLEMENT,
        ),
    ]

    result = resolve_ledger_iva_aggregation_binding_values(revision, observations)
    assert result == {
        "modelo-303-iva-repercutido-general-base": Decimal("1000"),
        "modelo-303-iva-repercutido-general-cuota": Decimal("210"),
        "modelo-303-iva-repercutido-reducido-base": Decimal("200"),
        "modelo-303-iva-repercutido-reducido-cuota": Decimal("20"),
        "modelo-303-iva-repercutido-super-reducido-base": Decimal("100"),
        "modelo-303-iva-repercutido-super-reducido-cuota": Decimal("4"),
        "modelo-303-iva-soportado-interiores-base": Decimal("300"),
        "modelo-303-iva-soportado-interiores-cuota": Decimal("63"),
        # This fixture has no recargo-charged repercutido rows, so the
        # recargo-equivalencia tier bindings resolve to zero.
        "modelo-303-recargo-equivalencia-general-cuota": Decimal("0"),
        "modelo-303-recargo-equivalencia-reducido-cuota": Decimal("0"),
        "modelo-303-recargo-equivalencia-super-reducido-cuota": Decimal("0"),
        # The reverse-charge AIC row is not an intra-community supply, and this
        # fixture has no export rows, so casillas 59/60 resolve to zero.
        "modelo-303-casilla-59-entregas-intracomunitarias-base": Decimal("0"),
        "modelo-303-casilla-60-exportaciones-base": Decimal("0"),
        # Casilla 122 is deliberately ABSENT here. This test resolves against
        # 2022, while the supplier-side inversión binding belongs
        # to the later explicit record-design revisions. Listing it here would
        # assert a resolution this revision cannot produce.
        # No third-country import rows in this observation set, so the import
        # deducible binding resolves to zero.
        "modelo-303-iva-soportado-importaciones-cuota": Decimal("0"),
        "modelo-303-iva-autorepercutido-intracomunitaria-cuota": Decimal("84"),
        # The AIC official-box parity bindings select the same AIC inversión row
        # as the semantic intracomunitaria binding, so they resolve to the same
        # self-assessed cuota (net-zero across the devengado/deducible pair).
        "modelo-303-iva-autorepercutido-intracomunitaria-devengado-cuota": Decimal("84"),
        "modelo-303-iva-autorepercutido-intracomunitaria-deducible-cuota": Decimal("84"),
        # No domestic inversión del sujeto pasivo rows in this observation
        # set, so both interior reverse-charge bindings resolve to zero.
        "modelo-303-iva-autorepercutido-interior-devengado-cuota": Decimal("0"),
        "modelo-303-iva-autorepercutido-interior-deducible-cuota": Decimal("0"),
        # No criterio-de-caja rows in this observation set (every observation
        # carries the default NONE treatment), so the art. 163 decies
        # informational bindings for casillas 62/63/74/75 resolve to zero.
        "modelo-303-criterio-caja-entregas-art75-base": Decimal("0"),
        "modelo-303-criterio-caja-entregas-art75-cuota": Decimal("0"),
        "modelo-303-criterio-caja-adquisiciones-base": Decimal("0"),
        "modelo-303-criterio-caja-adquisiciones-cuota": Decimal("0"),
    }


def test_modelo_303_construct_includes_iva_bindings() -> None:
    """The Modelo 303 construct must list each ledger_iva_aggregation
    binding so downstream consumers see a complete construct envelope."""
    modelo, _ = _load_modelo_303()
    revision = modelo.revisions["2022"]
    construct = next(c for c in revision.constructs if c.id == "modelo-303-iva-autoliquidacion")
    assert "modelo-303-iva-repercutido-general-cuota" in construct.bindings
    assert "modelo-303-iva-repercutido-reducido-cuota" in construct.bindings
    assert "modelo-303-iva-repercutido-super-reducido-cuota" in construct.bindings
    assert "modelo-303-iva-soportado-interiores-cuota" in construct.bindings
    assert "modelo-303-iva-autorepercutido-intracomunitaria-cuota" in construct.bindings


@pytest.mark.parametrize("revision_id", ["2022", *_M303_EXPLICIT_RECORD_DESIGN_REVISIONS])
def test_modelo_303_bienes_inversion_regularizacion_binding_is_declared_while_casilla_43_stays_manual(
    revision_id: str,
) -> None:
    """The live capital-goods resolver owns a binding slot; the official box remains operator-visible."""
    modelo, _ = _load_modelo_303()
    revision = modelo.revisions[revision_id]
    bindings = {binding.id: binding for binding in revision.bindings}
    casillas = {casilla.id: casilla for casilla in revision.casillas}

    binding = bindings[_M303_BIENES_INVERSION_REGULARIZACION_BINDING]
    assert binding.source == BindingSourceKind.BIENES_INVERSION_REGULARIZACION
    assert selector_as_dict(binding) == {
        "source_modelo": "303",
        "regularizacion_output": "modelo_303_casilla_43",
    }
    assert binding_source_modelo(binding) == "303"
    assert binding_source_casilla_ids(binding) == ()

    casilla_43 = casillas[_M303_BIENES_INVERSION_REGULARIZACION_CASILLA]
    assert casilla_43.input_kind is InputKind.MANUAL
    assert casilla_43.binding is None


@pytest.mark.parametrize("revision_id", ["2022", *_M303_EXPLICIT_RECORD_DESIGN_REVISIONS])
def test_modelo_303_prorrata_regularizacion_binding_is_declared_while_casilla_44_stays_manual(
    revision_id: str,
) -> None:
    modelo, _ = _load_modelo_303()
    revision = modelo.revisions[revision_id]
    casilla = {item.id: item for item in revision.casillas}[_M303_PRORRATA_REGULARIZACION_CASILLA]
    binding = {item.id: item for item in revision.bindings}[_M303_PRORRATA_REGULARIZACION_BINDING]

    assert casilla.input_kind is InputKind.MANUAL
    assert casilla.binding is None
    assert binding.source is BindingSourceKind.PRORRATA_REGULARIZACION
    assert binding_source_modelo(binding) == "303"
    assert binding_source_casilla_ids(binding) == _M303_PRORRATA_REGULARIZACION_SOURCE_CASILLAS
    assert selector_as_dict(binding) == {
        "source_modelo": "303",
        "source_casilla_ids": _M303_PRORRATA_REGULARIZACION_SOURCE_CASILLAS,
        "source_periods": _M303_PRORRATA_REGULARIZACION_SOURCE_PERIODS,
        "regularizacion_output": "modelo_303_casilla_44",
    }
    assert binding_aggregation_op(binding) is BindingAggregationOp.SUM
    assert {"ley-37-1992:art-104", "ley-37-1992:art-105"}.issubset(binding.legal_refs)
    assert binding.source_refs == (
        _M303_RECORD_DESIGN_SOURCE_BY_REVISION[revision_id],
        "aeat-modelo-303-procedure",
        "boe-modelo-303-2008-form",
    )
    citations_by_source = {citation.source_ref: citation for citation in binding.source_citations}
    assert citations_by_source["aeat-modelo-303-procedure"].required_text == ("modelo 303",)


@pytest.mark.parametrize("revision_id", ["2022", *_M303_EXPLICIT_RECORD_DESIGN_REVISIONS])
def test_modelo_303_construct_exposes_prorrata_regularizacion_binding(revision_id: str) -> None:
    modelo, _ = _load_modelo_303()
    revision = modelo.revisions[revision_id]
    construct = next(item for item in revision.constructs if item.id == "modelo-303-iva-autoliquidacion")

    assert _M303_PRORRATA_REGULARIZACION_CASILLA in construct.casilla_ids
    assert _M303_PRORRATA_REGULARIZACION_BINDING in construct.bindings
    assert "ley-37-1992:art-105" in construct.legal_refs


@pytest.mark.parametrize("revision_id", ["2022", *_M303_EXPLICIT_RECORD_DESIGN_REVISIONS])
def test_modelo_303_casilla_44_regularizacion_flows_to_total_deducible(revision_id: str) -> None:
    modelo, _ = _load_modelo_303()
    revision = modelo.revisions[revision_id]
    refs_by_formula_id = {formula.id: set(expression_casilla_refs(formula.expression)) for formula in revision.formulas}

    assert all(formula.target_casilla_id != _M303_PRORRATA_REGULARIZACION_CASILLA for formula in revision.formulas)
    assert all(
        formula.target_casilla_id != _M303_BIENES_INVERSION_REGULARIZACION_CASILLA for formula in revision.formulas
    )

    cuota_deducible_total = next(
        formula for formula in revision.formulas if formula.target_casilla_id == _M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA
    )
    refs = set(expression_casilla_refs(cuota_deducible_total.expression))
    assert _M303_BIENES_INVERSION_REGULARIZACION_CASILLA in refs
    assert _M303_PRORRATA_REGULARIZACION_CASILLA in refs
    assert refs_by_formula_id["modelo-303-iva-resultado-regimen-general"] == {
        _M303_CUOTA_DEVENGADA_TOTAL_CASILLA,
        _M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA,
    }

    if revision_id in _M303_EXPLICIT_RECORD_DESIGN_REVISIONS:
        projection = next(formula for formula in revision.formulas if formula.id == "modelo-303-dr303-45-projection")
        assert projection.expression.casilla_id == _M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA


def test_modelo_303_compensation_chain_uses_current_record_design_casillas() -> None:
    modelo, _ = _load_modelo_303()
    revision = modelo.revisions["2022"]
    casillas = {casilla.id: casilla for casilla in revision.casillas}
    relation = next(item for item in revision.relations if item.id == "modelo-303-rel-self-compensacion-anteriores")

    assert casillas[_M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA].number == "110"
    assert casillas[_M303_COMPENSACION_APLICADA_CASILLA].number == "78"
    assert casillas[_M303_POSTERIOR_CASILLA].number == "87"
    assert casillas[_M303_RESULTADO_CASILLA].number == "69"
    assert relation.target_periods == ("1T", "2T", "3T", "4T")
    assert relation.source_period_offset_from_target == -1
    assert relation.source_periods == ()
    assert relation.target_binding == "modelo-303-compensacion-pendiente-anteriores"


def test_modelo_303_previous_quarter_compensation_binding_resolves_from_source_casilla_id() -> None:
    from .. import (
        materialize_relation_binding_values,
        previous_filing_observation_requirements,
        relation_source_requirements,
        resolve_previous_filing_binding_values,
        resolve_relation_values_from_observations,
    )

    modelo, _ = _load_modelo_303()
    revision = modelo.revisions["2022"]
    observations = (
        registry_grounded_modelo_observation(
            modelo="303",
            filing_year=2025,
            period="1T",
            casilla_values={_M303_DISPONIBLE_CASILLA: Decimal("1200.00")},
        ),
    )

    binding_requirements = previous_filing_observation_requirements(revision, filing_year=2025, period="2T")
    assert [(item.periods, item.source_casilla_ids) for item in binding_requirements] == [
        (("1T",), (_M303_DISPONIBLE_CASILLA,)),
    ]

    relation_requirements = relation_source_requirements(revision, filing_year=2025, period="2T")
    assert [(item.periods, item.source_casilla_ids) for item in relation_requirements] == [
        (("1T",), (_M303_DISPONIBLE_CASILLA,)),
    ]

    assert resolve_previous_filing_binding_values(
        revision,
        observations,
        filing_year=2025,
        period="2T",
    ) == {"modelo-303-compensacion-pendiente-anteriores": Decimal("1200.00")}
    assert resolve_relation_values_from_observations(
        revision,
        observations,
        filing_year=2025,
        period="2T",
    ) == {"modelo-303-rel-self-compensacion-anteriores": Decimal("1200.00")}
    assert materialize_relation_binding_values(
        revision,
        {"modelo-303-rel-self-compensacion-anteriores": Decimal("1200.00")},
        period="2T",
    ) == {"modelo-303-compensacion-pendiente-anteriores": Decimal("1200.00")}


def test_modelo_303_first_quarter_compensation_resolves_from_previous_year_fourth_quarter() -> None:
    from .. import (
        materialize_relation_binding_values,
        previous_filing_observation_requirements,
        relation_source_requirements,
        resolve_previous_filing_binding_values,
        resolve_relation_values_from_observations,
    )

    modelo, _ = _load_modelo_303()
    revision = modelo.revisions["2022"]
    observations = (
        registry_grounded_modelo_observation(
            modelo="303",
            filing_year=2025,
            period="4T",
            casilla_values={_M303_DISPONIBLE_CASILLA: Decimal("450.00")},
        ),
    )

    binding_requirements = previous_filing_observation_requirements(revision, filing_year=2026, period="1T")
    assert [(item.filing_year, item.periods, item.source_casilla_ids) for item in binding_requirements] == [
        (2025, ("4T",), (_M303_DISPONIBLE_CASILLA,)),
    ]

    relation_requirements = relation_source_requirements(revision, filing_year=2026, period="1T")
    assert [(item.filing_year, item.periods, item.source_casilla_ids) for item in relation_requirements] == [
        (2025, ("4T",), (_M303_DISPONIBLE_CASILLA,)),
    ]

    assert resolve_previous_filing_binding_values(
        revision,
        observations,
        filing_year=2026,
        period="1T",
    ) == {"modelo-303-compensacion-pendiente-anteriores": Decimal("450.00")}
    assert resolve_relation_values_from_observations(
        revision,
        observations,
        filing_year=2026,
        period="1T",
    ) == {"modelo-303-rel-self-compensacion-anteriores": Decimal("450.00")}
    assert materialize_relation_binding_values(
        revision,
        {"modelo-303-rel-self-compensacion-anteriores": Decimal("450.00")},
        period="1T",
    ) == {"modelo-303-compensacion-pendiente-anteriores": Decimal("450.00")}


def test_modelo_303_compensation_calculation_applies_available_balance_and_carries_remainder() -> None:
    from .. import calculate_registry_snapshot

    modelo, catalogues = _load_modelo_303()
    snapshot = build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2025, period="2T")

    binding_values = {
        "modelo-303-iva-repercutido-general-cuota": Decimal("1000.00"),
        "modelo-303-iva-repercutido-reducido-cuota": Decimal("0.00"),
        "modelo-303-iva-repercutido-super-reducido-cuota": Decimal("0.00"),
        "modelo-303-iva-soportado-interiores-cuota": Decimal("0.00"),
        "modelo-303-iva-soportado-importaciones-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-intracomunitaria-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-intracomunitaria-devengado-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-intracomunitaria-devengado-base": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-intracomunitaria-deducible-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-interior-devengado-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-interior-deducible-cuota": Decimal("0.00"),
        "modelo-303-casilla-59-entregas-intracomunitarias-base": Decimal("0"),
        "modelo-303-casilla-60-exportaciones-base": Decimal("0"),
        # No issued domestic reverse charge in this fixture either, so the
        # supplier-side base for casilla 122 resolves to zero. Supplied for the
        # same reason 59 and 60 are: a bound casilla demands its fact, and the
        # absence of contributing rows is stated rather than left missing.
        "modelo-303-casilla-122-inversion-sujeto-pasivo-base": Decimal("0"),
        # And no EU B2B service located outside the TAI, so the sibling
        # informacion-adicional box 120 resolves to zero for the same reason.
        "modelo-303-casilla-120-no-sujetas-localizacion-base": Decimal("0"),
        "modelo-303-iva-repercutido-general-base": Decimal("0"),
        "modelo-303-iva-repercutido-reducido-base": Decimal("0"),
        "modelo-303-iva-repercutido-super-reducido-base": Decimal("0"),
        "modelo-303-iva-soportado-interiores-base": Decimal("0"),
        "modelo-303-recargo-equivalencia-general-cuota": Decimal("0"),
        "modelo-303-recargo-equivalencia-reducido-cuota": Decimal("0"),
        "modelo-303-recargo-equivalencia-super-reducido-cuota": Decimal("0"),
        "modelo-303-compensacion-pendiente-anteriores": Decimal("1200.00"),
        # No autoconsumo promotor in this period; zero disables the formula path.
        "modelo-303-autoconsumo-promotor-base": Decimal("0.00"),
        "modelo-303-profile-state-attribution-ratio": Decimal("100"),
        # No criterio-de-caja operations in this fixture, so the art. 163
        # decies informational bindings (casillas 62/63/74/75) resolve to zero.
        "modelo-303-criterio-caja-entregas-art75-base": Decimal("0"),
        "modelo-303-criterio-caja-entregas-art75-cuota": Decimal("0"),
        "modelo-303-criterio-caja-adquisiciones-base": Decimal("0"),
        "modelo-303-criterio-caja-adquisiciones-cuota": Decimal("0"),
    }
    bound_inputs = resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values)
    result = calculate_registry_snapshot(
        snapshot,
        inputs=bound_inputs,
        binding_values=binding_values,
        date_context={"filing_period": date(2025, 6, 30)},
    )

    # Structural wiring: all compensation casillas must be present in the result.
    compensation_casillas = {
        _M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA,
        _M303_COMPENSACION_APLICADA_CASILLA,
        _M303_POSTERIOR_CASILLA,
        _M303_RESULTADO_CASILLA,
        _M303_GENERADA_CASILLA,
        _M303_DISPONIBLE_CASILLA,
    }
    for casilla_id in compensation_casillas:
        assert casilla_id in result.values, f"{casilla_id!r} must be computed by the compensation chain"

    # Compensation balance constraint: applied + remainder must equal the incoming balance.
    # This is a structural invariant of the compensation mechanism, not a hand-computed value.
    pendiente_anteriores = result.values[_M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA]
    aplicada = result.values[_M303_COMPENSACION_APLICADA_CASILLA]
    pendiente_posteriores = result.values[_M303_POSTERIOR_CASILLA]
    assert aplicada + pendiente_posteriores == pendiente_anteriores, "applied + remainder must equal incoming balance"

    # When compensation exceeds IVA output, resultado must be zero (no tax due).
    # The binding carries compensacion_pendiente_anteriores=1200 > repercutido=1000,
    # so the full repercutido is absorbed and resultado must be 0.
    assert result.values[_M303_RESULTADO_CASILLA] == Decimal("0.00"), (
        "resultado must be zero when compensation balance exceeds IVA output"
    )

    # Applied amount must not exceed the IVA output for this period.
    assert aplicada <= binding_values["modelo-303-iva-repercutido-general-cuota"]

    # Disponible at end of period equals the remainder carried forward.
    assert result.values[_M303_DISPONIBLE_CASILLA] == pendiente_posteriores


def test_modelo_303_monthly_snapshot_resolves_for_each_period() -> None:
    """Each explicit current record-design revision resolves its monthly periods.

    REDEME and large-company taxpayers use monthly Modelo 303 schedules. The
    revision selector still has to resolve those monthly periods directly
    via select_revision so ``bindings list --period 01`` resolves without a
    RegistrySnapshotError."""
    modelo, catalogues = _load_modelo_303()

    for period in ("01", "06", "12"):
        snapshot = build_snapshot(
            modelo,
            catalogues,
            source_root=bundled_path(),
            filing_year=2025,
            period=period,
        )
        assert snapshot.revision.id == "2025"
        schedule_ids = {s.id for s in snapshot.revision.filing_schedules}
        assert "modelo-303-mensual" in schedule_ids, f"monthly schedule absent for period {period}"


def test_modelo_303_monthly_filing_schedule_matches_monthly_liquidation_profiles() -> None:
    """The monthly schedule fires for monthly IVA-liquidation triggers only."""
    from ....deadlines import (
        IVARegime,
        M303RegimeComposition,
        M303TaxTerritory,
        ModeloEnrollment,
        ModeloIVAProfile,
        TaxpayerProfile,
    )
    from .. import applicable_filing_schedules

    modelo, _catalogues = _load_modelo_303()
    revision = modelo.revisions["2025"]

    monthly_profiles = (
        TaxpayerProfile(
            tax_id="B12345674",
            iva_regime=IVARegime.GENERAL,
            iva=ModeloIVAProfile(
                tax_territory=M303TaxTerritory.COMMON_REGIME,
                regime_composition=M303RegimeComposition.GENERAL,
                cash_accounting_regime_enrolled=False,
                voluntary_sii_enrolled=False,
                hydrocarbon_deposit_advance_payment_deduction_entitled=False,
                redeme_enrolled=True,
            ),
        ),
        TaxpayerProfile(
            tax_id="C12345674",
            iva_regime=IVARegime.GENERAL,
            iva=ModeloIVAProfile(
                tax_territory=M303TaxTerritory.COMMON_REGIME,
                regime_composition=M303RegimeComposition.GENERAL,
                redeme_enrolled=False,
                cash_accounting_regime_enrolled=False,
                voluntary_sii_enrolled=False,
                hydrocarbon_deposit_advance_payment_deduction_entitled=False,
            ),
            enrollment=ModeloEnrollment(large_company=True),
        ),
    )
    voluntary_sii_profile = TaxpayerProfile(
        tax_id="A12345674",
        iva_regime=IVARegime.GENERAL,
        iva=ModeloIVAProfile(
            tax_territory=M303TaxTerritory.COMMON_REGIME,
            regime_composition=M303RegimeComposition.GENERAL,
            cash_accounting_regime_enrolled=False,
            voluntary_sii_enrolled=True,
            hydrocarbon_deposit_advance_payment_deduction_entitled=False,
            sii_enrolled=True,
            redeme_enrolled=False,
        ),
        enrollment=ModeloEnrollment(large_company=False),
    )
    ordinary_quarterly_profile = TaxpayerProfile(
        tax_id="D98765431",
        iva_regime=IVARegime.GENERAL,
        iva=ModeloIVAProfile(
            tax_territory=M303TaxTerritory.COMMON_REGIME,
            regime_composition=M303RegimeComposition.GENERAL,
            cash_accounting_regime_enrolled=False,
            voluntary_sii_enrolled=False,
            hydrocarbon_deposit_advance_payment_deduction_entitled=False,
            sii_enrolled=False,
            redeme_enrolled=False,
        ),
        enrollment=ModeloEnrollment(large_company=False),
    )

    for profile in monthly_profiles:
        monthly_schedules = applicable_filing_schedules(revision, profile)
        monthly_ids = {s.id for s in monthly_schedules}
        assert "modelo-303-mensual" in monthly_ids
        assert "modelo-303-trimestral" not in monthly_ids

    for profile in (voluntary_sii_profile, ordinary_quarterly_profile):
        quarterly_schedules = applicable_filing_schedules(revision, profile)
        quarterly_ids = {s.id for s in quarterly_schedules}
        assert "modelo-303-trimestral" in quarterly_ids, "quarterly schedule must match non-monthly profile"
        assert "modelo-303-mensual" not in quarterly_ids, "monthly schedule must NOT match non-monthly profile"


def test_modelo_303_autoconsumo_promotor_art9_oracle_1400k_base_yields_294k_cuota() -> None:
    """Oracle: Ramón has construction cost €1,400,000 and converts the building
    to his rental estate.  Art. 9.1.c LISIVA triggers the autoconsumo; Art. 79.4
    LISIVA sets the base at cost; Art. 90 LISIVA sets the tipo at 21%.

    Expected cuota = 1,400,000 x 0.21 = 294,000.00.

    The expected value is derived from the statutory formula (Art. 90 LISIVA:
    tipo general = 21%), NOT from the registry implementation under test; this
    test would fail if the formula were mis-wired or the tipo were wrong.
    """
    from .. import calculate_registry_snapshot

    modelo, catalogues = _load_modelo_303()
    snapshot = build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2025, period="1T")

    binding_values = {
        "modelo-303-iva-repercutido-general-cuota": Decimal("0.00"),
        "modelo-303-iva-repercutido-reducido-cuota": Decimal("0.00"),
        "modelo-303-iva-repercutido-super-reducido-cuota": Decimal("0.00"),
        "modelo-303-iva-soportado-interiores-cuota": Decimal("0.00"),
        "modelo-303-iva-soportado-importaciones-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-intracomunitaria-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-intracomunitaria-devengado-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-intracomunitaria-devengado-base": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-intracomunitaria-deducible-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-interior-devengado-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-interior-deducible-cuota": Decimal("0.00"),
        "modelo-303-casilla-59-entregas-intracomunitarias-base": Decimal("0"),
        "modelo-303-casilla-60-exportaciones-base": Decimal("0"),
        # No issued domestic reverse charge in this fixture either, so the
        # supplier-side base for casilla 122 resolves to zero. Supplied for the
        # same reason 59 and 60 are: a bound casilla demands its fact, and the
        # absence of contributing rows is stated rather than left missing.
        "modelo-303-casilla-122-inversion-sujeto-pasivo-base": Decimal("0"),
        # And no EU B2B service located outside the TAI, so the sibling
        # informacion-adicional box 120 resolves to zero for the same reason.
        "modelo-303-casilla-120-no-sujetas-localizacion-base": Decimal("0"),
        "modelo-303-iva-repercutido-general-base": Decimal("0"),
        "modelo-303-iva-repercutido-reducido-base": Decimal("0"),
        "modelo-303-iva-repercutido-super-reducido-base": Decimal("0"),
        "modelo-303-iva-soportado-interiores-base": Decimal("0"),
        "modelo-303-recargo-equivalencia-general-cuota": Decimal("0"),
        "modelo-303-recargo-equivalencia-reducido-cuota": Decimal("0"),
        "modelo-303-recargo-equivalencia-super-reducido-cuota": Decimal("0"),
        "modelo-303-compensacion-pendiente-anteriores": Decimal("0.00"),
        "modelo-303-autoconsumo-promotor-base": Decimal("1400000"),
        "modelo-303-profile-state-attribution-ratio": Decimal("100"),
        # No criterio-de-caja operations in this fixture, so the art. 163
        # decies informational bindings (casillas 62/63/74/75) resolve to zero.
        "modelo-303-criterio-caja-entregas-art75-base": Decimal("0"),
        "modelo-303-criterio-caja-entregas-art75-cuota": Decimal("0"),
        "modelo-303-criterio-caja-adquisiciones-base": Decimal("0"),
        "modelo-303-criterio-caja-adquisiciones-cuota": Decimal("0"),
    }
    bound_inputs = resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values)
    result = calculate_registry_snapshot(
        snapshot,
        inputs=bound_inputs,
        binding_values=binding_values,
        date_context={"filing_period": date(2025, 3, 31)},
    )

    # Art. 90 LISIVA tipo general 21%: 1,400,000 x 0.21 = 294,000.00
    assert result.values[_M303_AUTOCONSUMO_PROMOTOR_BASE_CASILLA] == Decimal("1400000"), (
        "base casilla must carry the supplied construction cost"
    )
    assert result.values[_M303_AUTOCONSUMO_PROMOTOR_CUOTA_CASILLA] == Decimal("294000.00"), (
        "cuota must equal 1,400,000 x 21% = 294,000.00 per Art. 90 LISIVA"
    )
    # The autoconsumo cuota must also flow into the total devengada.
    cuota_devengada_total = result.values[_M303_CUOTA_DEVENGADA_TOTAL_CASILLA]
    assert cuota_devengada_total == Decimal("294000.00"), (
        "cuota-devengada-total must include the autoconsumo promotor cuota"
    )


def test_modelo_303_autoconsumo_promotor_cuota_proportional_to_base() -> None:
    """Anti-tautology: halving the construction base must halve the cuota.

    The assertion is derived from the statutory multiplication (Art. 90 LISIVA
    tipo 21%), not from a second call to the same formula.  If the formula
    constant were changed to, say, 0.10, this test would catch it immediately.
    """
    from .. import calculate_registry_snapshot

    modelo, catalogues = _load_modelo_303()
    snapshot = build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2025, period="1T")

    zero_bindings: dict[str, Decimal] = {
        "modelo-303-iva-repercutido-general-cuota": Decimal("0.00"),
        "modelo-303-iva-repercutido-reducido-cuota": Decimal("0.00"),
        "modelo-303-iva-repercutido-super-reducido-cuota": Decimal("0.00"),
        "modelo-303-iva-soportado-interiores-cuota": Decimal("0.00"),
        "modelo-303-iva-soportado-importaciones-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-intracomunitaria-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-intracomunitaria-devengado-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-intracomunitaria-devengado-base": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-intracomunitaria-deducible-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-interior-devengado-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-interior-deducible-cuota": Decimal("0.00"),
        "modelo-303-casilla-59-entregas-intracomunitarias-base": Decimal("0"),
        "modelo-303-casilla-60-exportaciones-base": Decimal("0"),
        # No issued domestic reverse charge in this fixture either, so the
        # supplier-side base for casilla 122 resolves to zero. Supplied for the
        # same reason 59 and 60 are: a bound casilla demands its fact, and the
        # absence of contributing rows is stated rather than left missing.
        "modelo-303-casilla-122-inversion-sujeto-pasivo-base": Decimal("0"),
        # And no EU B2B service located outside the TAI, so the sibling
        # informacion-adicional box 120 resolves to zero for the same reason.
        "modelo-303-casilla-120-no-sujetas-localizacion-base": Decimal("0"),
        "modelo-303-iva-repercutido-general-base": Decimal("0"),
        "modelo-303-iva-repercutido-reducido-base": Decimal("0"),
        "modelo-303-iva-repercutido-super-reducido-base": Decimal("0"),
        "modelo-303-iva-soportado-interiores-base": Decimal("0"),
        "modelo-303-recargo-equivalencia-general-cuota": Decimal("0"),
        "modelo-303-recargo-equivalencia-reducido-cuota": Decimal("0"),
        "modelo-303-recargo-equivalencia-super-reducido-cuota": Decimal("0"),
        "modelo-303-compensacion-pendiente-anteriores": Decimal("0.00"),
        "modelo-303-profile-state-attribution-ratio": Decimal("100"),
        # No criterio-de-caja operations in this fixture, so the art. 163
        # decies informational bindings (casillas 62/63/74/75) resolve to zero.
        "modelo-303-criterio-caja-entregas-art75-base": Decimal("0"),
        "modelo-303-criterio-caja-entregas-art75-cuota": Decimal("0"),
        "modelo-303-criterio-caja-adquisiciones-base": Decimal("0"),
        "modelo-303-criterio-caja-adquisiciones-cuota": Decimal("0"),
    }

    def _run(base: Decimal) -> Decimal:
        bv = {**zero_bindings, "modelo-303-autoconsumo-promotor-base": base}
        bound = resolve_available_bound_inputs_by_casilla_id(snapshot.revision, bv)
        r = calculate_registry_snapshot(
            snapshot,
            inputs=bound,
            binding_values=bv,
            date_context={"filing_period": date(2025, 3, 31)},
        )
        return r.values[_M303_AUTOCONSUMO_PROMOTOR_CUOTA_CASILLA]

    # Statutory expectation from Art. 90 LISIVA (tipo general 21%):
    #   700,000 x 0.21 = 147,000.00
    assert _run(Decimal("700000")) == Decimal("147000.00")
    # Cross-check: result at 1,400,000 is exactly double — if the registry formula
    # were wrong the ratio would differ.
    assert _run(Decimal("1400000")) == Decimal("2") * _run(Decimal("700000"))


def test_modelo_303_workbook_parity_ref_anchors_record_design_layout() -> None:
    modelo, _ = _load_modelo_303()
    revision = modelo.revisions["2022"]
    parity = next(p for p in revision.workbook_parity_refs if p.id == "modelo-303-dr-2022")

    assert parity.workbook_source == "aeat-dr-303-2022"
    assert parity.formula_coverage == "record_design_layout"
    assert parity.fixture_id == "modelo-303-2022-record-design-layout"


def test_modelo_303_2026_cnae_width_has_a_distinct_authority_role() -> None:
    modelo, _ = _load_modelo_303()
    historical = modelo.revisions["2025"]
    current = modelo.revisions["2026-y-siguientes"]

    for row, casilla_id in enumerate(("500", "505", "510", "515", "520"), start=1):
        prior = next(c for c in historical.casillas if c.id == casilla_id)
        widened = next(c for c in current.casillas if c.id == casilla_id)
        assert prior.constraints is not None and prior.constraints.min_length == prior.constraints.max_length == 3
        assert widened.constraints is not None and widened.constraints.min_length == widened.constraints.max_length == 4
        assert prior.semantic_role == f"m303_prorrata_actividad_fila_{row}_cnae"
        assert widened.semantic_role == f"m303_prorrata_actividad_fila_{row}_cnae_2026_four_digit"
        assert "aeat-dr-303-2025" in prior.source_refs
        assert "aeat-dr-303-2026" in widened.source_refs


# The defect-C2 regression that pinned the no-volume prorrata default used one
# filing-year sample. It is retired rather than widened because a dedicated
# two-revision gate now owns the claim: measured by mutation, breaking the
# branch on either live revision reds that gate. Its distinct mid-year axis was
# carried across before this test was removed.
