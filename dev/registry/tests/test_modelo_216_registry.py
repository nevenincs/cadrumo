"""Tests for the committed Modelo 216 IRNR retención registry foundation.

Modelo 216 is the quarterly IRNR withholding autoliquidación (retenciones e
ingresos a cuenta) approved by Orden EHA/3290/2008 (BOE-A-2008-18497), with the
current form layout carried by Orden HAC/56/2024. The trimestral filing plazo is
grounded in Orden EHA/3290/2008 art 4: the first twenty natural days of April,
July, October and January for the immediately preceding natural quarter.

See Also:
    :func:`~domain.calculations.registry.tests._registry_schema_support._committed_modelo`
        Test loader for the committed registry definition and legal catalogue.
    :class:`~dev.registry.compiler.validator.RegistryValidator`
        Registry validator that checks the authored legal/source references.
    :func:`~domain.calculations.registry.authority.compiled_bundled_authority`
        Authority facade used to resolve the trimestral deadline windows.
    :func:`~domain.calculations.registry._snapshot.build_snapshot`
        Snapshot builder feeding the Modelo 216 formula runtime proof.
    :func:`~domain.calculations.registry._formula_runtime.calculate_registry_snapshot`
        Formula evaluator used to verify the retained-total arithmetic.
    :class:`~domain.calculations.registry._ids.CasillaId`
        Typed casilla identifier used for the Modelo 216 calculation inputs.
    :class:`~core.TaxDomain`
        Closed tax-family enum whose IRNR member classifies the registration.
    :data:`~domain.calculations.registry.modelo_obligation_scope.UNMODELED_OBLIGATIONS`
        Former recognized-unmodeled set reduced by the Modelo 216 promotion.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

import pytest

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.period import PeriodKind, registry_period_kind
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from cadrumo.domain.calculations.registry.modelo_inception import UnauthoredBefore
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.temporal import select_revision
from cadrumo.domain.calculations.registry.tests.snapshot_support import build_snapshot
from dev.registry.compiler.authority import compiled_bundled_authority
from dev.registry.compiler.loader import load_modelo_directory, load_shared_catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_BASE_DINERARIA: CasillaId = validated_casilla_id("08", surface="_BASE_DINERARIA")
_BASE_ESPECIE: CasillaId = validated_casilla_id("09", surface="_BASE_ESPECIE")
_BASE_TOTAL: CasillaId = validated_casilla_id("10", surface="_BASE_TOTAL")
_RET_DINERARIA: CasillaId = validated_casilla_id("11", surface="_RET_DINERARIA")
_RET_ESPECIE: CasillaId = validated_casilla_id("12", surface="_RET_ESPECIE")
_RET_TOTAL: CasillaId = validated_casilla_id("13", surface="_RET_TOTAL")
_ANTERIORES: CasillaId = validated_casilla_id("20", surface="_ANTERIORES")
_RESULTADO: CasillaId = validated_casilla_id("21", surface="_RESULTADO")

_EXPECTED_DEADLINES = {
    (2022, "1T"): (date(2022, 4, 1), date(2022, 4, 20), date(2022, 4, 15)),
    (2022, "2T"): (date(2022, 7, 1), date(2022, 7, 20), date(2022, 7, 15)),
    (2022, "3T"): (date(2022, 10, 1), date(2022, 10, 20), date(2022, 10, 15)),
    (2022, "4T"): (date(2023, 1, 1), date(2023, 1, 20), date(2023, 1, 15)),
    (2023, "1T"): (date(2023, 4, 1), date(2023, 4, 20), date(2023, 4, 15)),
    (2023, "2T"): (date(2023, 7, 1), date(2023, 7, 20), date(2023, 7, 15)),
    (2023, "3T"): (date(2023, 10, 1), date(2023, 10, 20), date(2023, 10, 15)),
    (2023, "4T"): (date(2024, 1, 1), date(2024, 1, 22), date(2024, 1, 17)),
    (2024, "1T"): (date(2024, 4, 1), date(2024, 4, 22), date(2024, 4, 17)),
    (2024, "2T"): (date(2024, 7, 1), date(2024, 7, 22), date(2024, 7, 17)),
    (2024, "3T"): (date(2024, 10, 1), date(2024, 10, 21), date(2024, 10, 16)),
    (2024, "4T"): (date(2025, 1, 1), date(2025, 1, 20), date(2025, 1, 15)),
    (2025, "1T"): (date(2025, 4, 1), date(2025, 4, 21), date(2025, 4, 15)),
    (2025, "2T"): (date(2025, 7, 1), date(2025, 7, 21), date(2025, 7, 16)),
    (2025, "3T"): (date(2025, 10, 1), date(2025, 10, 20), date(2025, 10, 15)),
    (2025, "4T"): (date(2026, 1, 1), date(2026, 1, 20), date(2026, 1, 15)),
    (2026, "1T"): (date(2026, 4, 1), date(2026, 4, 20), date(2026, 4, 15)),
    (2026, "2T"): (date(2026, 7, 1), date(2026, 7, 20), date(2026, 7, 15)),
    (2026, "3T"): (date(2026, 10, 1), date(2026, 10, 20), date(2026, 10, 15)),
    (2026, "4T"): (date(2027, 1, 1), date(2027, 1, 20), None),
}


def _load_modelo_216():
    authority = compiled_bundled_authority()
    return authority.modelo("216"), authority.catalogues


def test_modelo_216_validator_accepts_committed_definition() -> None:
    modelo, _catalogues = _load_modelo_216()
    assert modelo.id == "216"
    assert modelo.revisions, "216 must declare at least one revision"


def test_modelo_216_formulas_owned_by_construct() -> None:
    modelo, _ = _load_modelo_216()
    revision = modelo.revisions["2024-y-siguientes"]
    owned = set().union(*(set(c.formulas) for c in revision.constructs))
    assert {"modelo-216-base-total", "modelo-216-retenciones-total", "modelo-216-resultado"} <= owned


def test_modelo_216_deadline_provision_is_orden_eha_3290_2008_art_4() -> None:
    """Every trimestral window cites the binding Orden EHA/3290/2008 art 4 plazo."""
    modelo, catalogues = _load_modelo_216()
    revision = modelo.revisions["2024-y-siguientes"]
    assert revision.deadline_windows, "216 must declare quarterly deadline windows"
    for window in revision.deadline_windows:
        assert window.period_kind == "quarterly"
        assert "orden-eha-3290-2008:art-4" in window.legal_refs
    # The plazo article resolves in the shared legal catalogue as legal authority,
    # cross-checked against the bundled BOE corpus at build.
    plazo = catalogues.legal["orden-eha-3290-2008:art-4"]
    assert plazo.evidence_tier == "legal_authority"
    assert plazo.document_id == "BOE-A-2008-18497"


def test_modelo_216_has_exact_supported_deadline_census_and_dates() -> None:
    modelo, _catalogues = _load_modelo_216()
    observed = {
        (window.period.filing_year, window.period.registry_token): (
            window.opens_on,
            window.closes_on,
            window.payment_cutoff_on,
        )
        for revision in modelo.revisions.values()
        for window in revision.deadline_windows
        if 2022 <= window.period.filing_year <= 2026
    }
    assert observed == _EXPECTED_DEADLINES


def test_modelo_216_windows_use_canonical_periods_sources_and_owner() -> None:
    modelo, catalogues = _load_modelo_216()
    owned = [(revision, window) for revision in modelo.revisions.values() for window in revision.deadline_windows]
    assert len(owned) == len(_EXPECTED_DEADLINES)

    for revision, window in owned:
        filing_year = window.period.filing_year
        period = window.period.registry_token
        physical_calendar_year = window.closes_on.year
        calendar_ref = f"aeat-calendario-contribuyente-{physical_calendar_year}"

        assert window.id == f"modelo-216-{filing_year}-{period.lower()}"
        assert window.filing_year == filing_year
        assert registry_period_kind(period) is PeriodKind.QUARTERLY
        assert window.period.kind is PeriodKind.QUARTERLY
        assert window.period_kind == "quarterly"
        assert select_revision(modelo, filing_year=filing_year, period=period) is revision

        if physical_calendar_year <= 2026:
            assert calendar_ref in window.source_refs
            assert calendar_ref in revision.source_refs
            assert calendar_ref in revision.constructs[0].source_refs
            source = catalogues.sources[calendar_ref]
            assert (source.authority, source.evidence_tier) == ("aeat", "official_source_guidance")
            assert (bundled_path() / source.corpus_path).is_file()
        else:
            assert window.payment_cutoff_on is None


def test_modelo_216_resultado_is_retenciones_total_minus_anteriores() -> None:
    """Casilla 21 = casilla 13 (total retenciones) - casilla 20 (anteriores).

    Base total (10) = 08 + 09, retenciones total (13) = 11 + 12, resultado a
    ingresar (21) = 13 - 20, per the AEAT Modelo 216 instructions' own printed
    total rows.
    """
    modelo, catalogues = _load_modelo_216()
    snapshot = build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2025, period="1T")
    result = calculate_registry_snapshot(
        snapshot,
        inputs={
            _BASE_DINERARIA: Decimal("1000.00"),
            _BASE_ESPECIE: Decimal("500.00"),
            _RET_DINERARIA: Decimal("190.00"),
            _RET_ESPECIE: Decimal("95.00"),
            _ANTERIORES: Decimal("40.00"),
        },
        date_context={"filing_period": date(2025, 3, 31)},
    )
    assert result.values[_BASE_TOTAL] == Decimal("1500.00")
    assert result.values[_RET_TOTAL] == Decimal("285.00")
    assert result.values[_RESULTADO] == Decimal("245.00")


def _pre_redesign_years() -> tuple[tuple[int, ...], ModeloRevision]:
    modelo, _catalogues = _load_modelo_216()
    support = load_shared_catalogues(bundled_path("registry", "aeat")).supported_filing_years
    assert support is not None
    redesign = select_revision(modelo, filing_year=support.horizon, period="1T", support=support)
    years = tuple(year for year in support.years if year < redesign.valid_from.year)
    assert years, "no supported year precedes the 2024 redesign"
    return years, redesign


def test_modelo_216_years_before_the_redesign_answer_from_the_design_that_governed_them() -> None:
    """The 2024 design refuses an earlier devengo year, so those years resolve to the 2020-2023 design."""
    modelo, catalogues = _load_modelo_216()
    support = load_shared_catalogues(bundled_path("registry", "aeat")).supported_filing_years
    years, redesign = _pre_redesign_years()
    for year in years:
        for period in redesign.period_selector.declared_periods:
            revision = select_revision(modelo, filing_year=year, period=period, support=support)
            assert revision is not redesign
            assert revision.effective_authority_grade is RegistryAuthorityGrade.APPLICABILITY
            designs = [ref for ref in revision.source_refs if catalogues.sources[ref].kind == "record_design"]
            assert len(designs) == 1
            design = catalogues.sources[designs[0]]
            assert design.applies_from is not None and design.applies_to is not None
            assert design.applies_from.year <= year <= design.applies_to.year


def test_modelo_216_pre_redesign_edition_declares_only_the_partidas_its_design_prints() -> None:
    modelo, catalogues = _load_modelo_216()
    years, _redesign = _pre_redesign_years()
    revision = select_revision(modelo, filing_year=years[0], period="1T")
    (design_ref,) = [ref for ref in revision.source_refs if catalogues.sources[ref].kind == "record_design"]
    corpus = bundled_path() / catalogues.sources[design_ref].corpus_path
    text = corpus.with_name(f"{corpus.name}.extracted.md").read_text(encoding="utf-8")
    printed = sorted(set(re.findall(r"Liquidación - Partida (\d)", text)))
    assert printed
    assert sorted(str(casilla.id) for casilla in revision.casillas) == [f"partida-{n}" for n in printed]
    assert revision.formulas == ()
    assert revision.export_layouts == ()


def test_modelo_216_inception_names_its_earliest_authored_edition() -> None:
    declared = load_modelo_directory(bundled_path("registry", "aeat", "modelos", "216"))
    assert isinstance(declared.inception, UnauthoredBefore)
    assert declared.inception.earliest_authored == min(
        revision.valid_from.year for revision in declared.revisions.values()
    )
