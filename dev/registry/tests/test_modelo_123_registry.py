"""Modelo 123 registry behaviour for quarterly capital-income withholding filings."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, RegistrySnapshot
from cadrumo.domain.calculations.registry.schema_catalogues import RegistryCatalogues
from cadrumo.domain.calculations.registry.temporal import select_revision
from cadrumo.domain.calculations.registry.tests.authored_editions import (
    authored_revisions,
    filing_year_envelope,
    open_ended_revision,
    revision_last_exercise,
)
from cadrumo.domain.calculations.registry.tests.snapshot_support import build_snapshot
from dev.registry.compiler.authority import compiled_bundled_authority

from .profile_schema_support import committed_supported_filing_years
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

_SUPPORT = committed_supported_filing_years()
# The revision whose casilla 06 sums retenciones and regularizacion, and the
# Orden HAC/56/2024 revision that replaces it with split base sub-totals.
_RETENCIONES_SUM_REVISION = str(authored_revisions("123")[0].id)
_SPLIT_BASE_REVISION = str(open_ended_revision("123").id)
_SPLIT_BASE_YEAR = open_ended_revision("123").valid_from.year


_M123_RENTAS_DIVIDENDOS_CASILLA: CasillaId = validated_casilla_id("01")
_M123_RENTAS_RESTO_CASILLA: CasillaId = validated_casilla_id("02")
_M123_RENTAS_TOTAL_CASILLA: CasillaId = validated_casilla_id("03")
_M123_BASE_DIVIDENDOS_CASILLA: CasillaId = validated_casilla_id("04")
_M123_BASE_RESTO_CASILLA: CasillaId = validated_casilla_id("05")
_M123_BASE_TOTAL_CASILLA: CasillaId = validated_casilla_id("06")
_M123_RETENCIONES_DIVIDENDOS_CASILLA: CasillaId = validated_casilla_id("07")
_M123_RETENCIONES_RESTO_CASILLA: CasillaId = validated_casilla_id("08")
_M123_PREVIOUS_RESULT_CASILLA: CasillaId = validated_casilla_id("10")
_M123_PREVIOUS_PERIOD_WITHHELD_CASILLA: CasillaId = validated_casilla_id("11")
_M123_A_INGRESAR_CASILLA: CasillaId = validated_casilla_id("13")
_M123_2019_2023_NPERCEPTORES_CASILLA: CasillaId = validated_casilla_id("01")
_M123_2019_2023_BASE_CASILLA: CasillaId = validated_casilla_id("02")
_M123_2019_2023_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("03")
_M123_2019_2023_REGULARIZACION_CASILLA: CasillaId = validated_casilla_id("04")
_M123_2019_2023_PREVIOUS_RESULT_CASILLA: CasillaId = validated_casilla_id("05")
_M123_2019_2023_RESULTADO_CASILLA: CasillaId = validated_casilla_id("06")
_M123_2019_2023_INGRESO_CASILLA: CasillaId = validated_casilla_id("07")


def test_modelo_123_guidance_and_layout_sources_are_separated() -> None:
    authority = compiled_bundled_authority()
    modelo, catalogues = authority.modelo("123"), authority.catalogues

    procedure = catalogues.sources["aeat-modelo-123-procedure"]
    assert "aeat-modelo-123-procedure" in modelo.source_refs
    assert procedure.evidence_tier == "official_source_guidance"
    assert procedure.authority == "aeat"
    assert procedure.kind == "instructions"
    assert (bundled_path() / procedure.corpus_path).is_file()

    assert catalogues.sources["aeat-dr-123-2024-v20"].evidence_tier == "layout_authority"
    assert catalogues.sources["aeat-dr-123-2019-2023-v13"].evidence_tier == "layout_authority"
    assert catalogues.sources["aeat-dr-123-2024-v20-form-text"].evidence_tier == "layout_authority"
    assert catalogues.sources["aeat-dr-123-2019-2023-v13-form-text"].evidence_tier == "layout_authority"
    assert catalogues.sources["boe-modelo-123-2007-form"].evidence_tier == "layout_authority"
    assert catalogues.sources["boe-modelo-123-2024-form"].evidence_tier == "layout_authority"

    formula_sources = {
        _RETENCIONES_SUM_REVISION: "boe-modelo-123-2007-form-text",
        _SPLIT_BASE_REVISION: "boe-modelo-123-2024-form-text",
    }
    for revision_id, source_ref in formula_sources.items():
        source = catalogues.sources[source_ref]
        assert source.evidence_tier == "official_source_guidance"
        assert source.authority == "boe"
        assert source.kind == "form_spec"
        assert (bundled_path() / source.corpus_path).is_file()

        revision = modelo.revisions[revision_id]
        assert source_ref in revision.source_refs
        for formula in revision.formulas:
            assert source_ref in formula.source_refs
            assert not any(str(ref).startswith("aeat-dr-123-") for ref in formula.source_refs)
            for citation in formula.source_citations:
                assert citation.source_ref == source_ref


@pytest.mark.parametrize(
    ("filing_year", "required_surfaces"),
    [
        (
            revision_last_exercise("123", _RETENCIONES_SUM_REVISION),
            {
                "calculation",
                "filing",
                "export",
                "review",
                "approval",
                "reconciliation",
                "extractor",
                "portal",
                "workflow",
            },
        ),
        (
            filing_year_envelope().horizon,
            {
                "calculation",
                "filing",
                "export",
                "review",
                "approval",
                "reconciliation",
                "extractor",
                "portal",
                "deadline",
                "workflow",
            },
        ),
    ],
)
def test_modelo_123_validated_snapshot_owns_workflow_surfaces(
    filing_year: int,
    required_surfaces: set[str],
) -> None:
    authority = compiled_bundled_authority()
    modelo, catalogues = authority.modelo("123"), authority.catalogues

    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=filing_year,
        period="1T",
    )

    construct = snapshot.revision.constructs[0]
    linked_by_surface = {
        link.surface: link for link in snapshot.revision.application_links if link.id in construct.application_links
    }
    assert required_surfaces <= set(linked_by_surface)
    assert all(link.requires_snapshot for link in linked_by_surface.values())


def test_modelo_123_supported_year_deadline_census_dates_sources_and_ownership() -> None:
    with bundled_indexed_authority().operation() as operation:
        _check_supported_year_deadlines(operation)


def _check_supported_year_deadlines(operation: PinnedAuthorityOperation) -> None:
    authority = compiled_bundled_authority()
    modelo = authority.modelo("123")
    windows = {
        (window.filing_year, window.period.registry_token): (revision, window)
        for revision in modelo.revisions.values()
        for window in revision.deadline_windows
    }

    assert (
        sum(len(revision.deadline_windows) for revision in modelo.revisions.values())
        == len(windows)
        == len(RETENCION_PERIODS) * len(filing_year_envelope().years)
    )
    current_revision = modelo.revisions[_SPLIT_BASE_REVISION]
    assert set(current_revision.constructs[0].deadline_windows) == {
        window.id for window in current_revision.deadline_windows
    }

    for filing_year in filing_year_envelope().years:
        expected_periods = set(RETENCION_PERIODS)
        assert {period for year, period in windows if year == filing_year} == expected_periods
        projected = compiled_bundled_authority().deadline_windows(filing_year, modelos=("123",))
        assert len(projected) == 16
        assert {window.period.registry_token for _, _, window in projected} == expected_periods

        for period in RETENCION_PERIODS:
            revision, window = windows[(filing_year, period)]
            assert select_revision(modelo, filing_year=filing_year, period=period) is revision
            assert window.id == f"modelo-123-{filing_year}-{period.lower()}"
            assert window.filing_year == window.period.filing_year == filing_year
            assert window.opens_on == date(window.closes_on.year, window.closes_on.month, 1)
            assert window.closes_on == expected_close(operation, "123", filing_year, period)
            expected_sources = {"aeat-modelo-123-procedure"}
            if calendar_is_bundled(window.closes_on.year):
                expected_sources.add(f"aeat-calendario-contribuyente-{window.closes_on.year}")
            assert set(window.source_refs) == expected_sources

        # The quarterly cadence authors its domiciliación day; the monthly one
        # does not, because the governed deadlines.domiciliation-cutoff-clause
        # fact already declares this modelo's monthly Anexo II day. Asserting
        # the absence keeps a later per-month restatement from passing silently.
        for period in QUARTERLY_PERIODS:
            assert windows[(filing_year, period)][1].payment_cutoff_on == expected_cutoff(filing_year, period)
        for period in MONTHLY_PERIODS:
            assert windows[(filing_year, period)][1].payment_cutoff_on is None

    assert windows[(filing_year_envelope().horizon, "4T")][1].payment_cutoff_on is None


# ---------------------------------------------------------------------------
# Casilla 06 arithmetic oracle (Aitor #211)
#
# Authority: Orden HAC/56/2024 Anexo II + BOE annex form text.
# "Base de retenciones e ingresos a cuenta" in the Totales column = [04] + [05].
# Casilla 06 must equal the sum of the two base sub-totals only.
# Perceptor counts (casillas 01, 02, 03) must NOT contribute to casilla 06.
# ---------------------------------------------------------------------------


def _snapshot_split_base(filing_year: int = _SPLIT_BASE_YEAR) -> RegistrySnapshot:
    return compiled_bundled_authority().snapshot("123", filing_year=filing_year, period="1T")


def _calculate_split_base(
    snapshot: RegistrySnapshot,
    *,
    nperceptores_dividendos: int,
    nperceptores_resto: int,
    base_dividendos: Decimal,
    base_resto: Decimal,
):
    """Drive calculate_registry_snapshot with M123 2024+ manual inputs.

    All retenciones, periodificacion, and liquidacion inputs are zeroed so
    only casilla 06 (base_total = [04] + [05]) varies under test.
    """
    return calculate_registry_snapshot(
        snapshot,
        inputs={
            _M123_RENTAS_DIVIDENDOS_CASILLA: Decimal(nperceptores_dividendos),
            _M123_RENTAS_RESTO_CASILLA: Decimal(nperceptores_resto),
            _M123_BASE_DIVIDENDOS_CASILLA: base_dividendos,
            _M123_BASE_RESTO_CASILLA: base_resto,
            _M123_RETENCIONES_DIVIDENDOS_CASILLA: Decimal("0"),
            _M123_RETENCIONES_RESTO_CASILLA: Decimal("0"),
            _M123_PREVIOUS_RESULT_CASILLA: Decimal("0"),
            _M123_PREVIOUS_PERIOD_WITHHELD_CASILLA: Decimal("0"),
            _M123_A_INGRESAR_CASILLA: Decimal("0"),
        },
        date_context={"filing_period": date(_SPLIT_BASE_YEAR, 12, 31)},
    )


def test_m123_casilla_06_equals_base_dividendos_plus_base_resto() -> None:
    """Casilla 06 = [04] + [05] (base total).

    Oracle authority: Orden HAC/56/2024 BOE annex text, field label
    "Base de retenciones e ingresos a cuenta" in the Totales column.

    With base_dividendos=42000 and base_resto=0, casilla 06 must be 42000.
    The perceptor count (nperceptores=7 split as 01=4, 02=3) must not
    contribute to casilla 06.
    """
    snapshot = _snapshot_split_base()
    result = _calculate_split_base(
        snapshot,
        nperceptores_dividendos=4,
        nperceptores_resto=3,
        base_dividendos=Decimal("42000.00"),
        base_resto=Decimal("0.00"),
    )
    casilla_03 = result.values[_M123_RENTAS_TOTAL_CASILLA]
    casilla_06 = result.values[_M123_BASE_TOTAL_CASILLA]
    assert casilla_03 == Decimal("7"), f"precondition: casilla 03 (total count) should be 7, got {casilla_03}"
    assert casilla_06 == Decimal("42000.00"), (
        f"casilla 06 (base total) should be 42000.00 (= base_dividendos + base_resto), "
        f"got {casilla_06}; if this is 42007 the formula incorrectly includes perceptor count"
    )


def test_m123_casilla_06_base_resto_only() -> None:
    """Casilla 06 = base_dividendos + base_resto also holds when base is in base_resto.

    Oracle: nperceptores=1 (01=1, 02=0), base=5000 in casilla 05 (base_resto).
    Casilla 06 must be 5000, not 5001.
    """
    snapshot = _snapshot_split_base()
    result = _calculate_split_base(
        snapshot,
        nperceptores_dividendos=1,
        nperceptores_resto=0,
        base_dividendos=Decimal("0.00"),
        base_resto=Decimal("5000.00"),
    )
    casilla_03 = result.values[_M123_RENTAS_TOTAL_CASILLA]
    casilla_06 = result.values[_M123_BASE_TOTAL_CASILLA]
    assert casilla_03 == Decimal("1"), f"precondition: casilla 03 should be 1, got {casilla_03}"
    assert casilla_06 == Decimal("5000.00"), (
        f"casilla 06 must be 5000.00, got {casilla_06}; if 5001 then perceptor count is leaking into casilla 06"
    )


def test_m123_casilla_06_invariant_to_nperceptores() -> None:
    """Changing nperceptores must NOT change casilla 06 (anti-tautology).

    Authority: perceptor counts (casillas 01, 02) feed only casilla 03
    (numero_rentas_total). They have no path into casilla 06 (base_total).
    With base fixed at 42000 in casilla 04, casilla 06 must remain 42000
    regardless of whether nperceptores is 1, 7, or 100.
    """
    snapshot = _snapshot_split_base()
    base_fixed = Decimal("42000.00")
    results = [
        _calculate_split_base(
            snapshot,
            nperceptores_dividendos=n,
            nperceptores_resto=0,
            base_dividendos=base_fixed,
            base_resto=Decimal("0.00"),
        ).values[_M123_BASE_TOTAL_CASILLA]
        for n in (1, 7, 100)
    ]
    assert results[0] == results[1] == results[2] == base_fixed, (
        f"casilla 06 must be invariant to nperceptores; got {results}"
    )


# ---------------------------------------------------------------------------
# 2019-2023 revision: casilla 06 semantic is different
# ("Suma de retenciones y regularizacion" = [03] + [05]).
# Perceptor count (01) and base (02) must NOT contribute.
# ---------------------------------------------------------------------------


def test_m123_retenciones_sum_revision_casilla_06_invariant_to_nperceptores_and_base() -> None:
    """Retenciones-sum revision: casilla 06 is retenciones+regularizacion, not base.

    Authority: BOE Modelo 123 annex text citation "( 03 + 05 )".
    Inputs 01 (nperceptores) and 02 (base retenciones) are
    manual pass-through casillas with no formula; they must not affect
    casilla 06 (Suma de retenciones y regularizacion = [03] + [05]).
    """
    authority = compiled_bundled_authority()
    modelo, catalogues = authority.modelo("123"), authority.catalogues
    revision = modelo.revisions[_RETENCIONES_SUM_REVISION]
    covered_years = tuple(
        year
        for year in _SUPPORT.years
        if revision.valid_from.year <= year and (revision.valid_to is None or year <= revision.valid_to.year)
    )
    assert covered_years
    for filing_year in covered_years:
        _assert_casilla_06_sums_retenciones(modelo, catalogues, filing_year)


def _assert_casilla_06_sums_retenciones(
    modelo: ModeloDefinition, catalogues: RegistryCatalogues, filing_year: int
) -> None:
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=filing_year,
        period="1T",
    )
    assert snapshot.revision.id == _RETENCIONES_SUM_REVISION
    result = calculate_registry_snapshot(
        snapshot,
        inputs={
            _M123_2019_2023_NPERCEPTORES_CASILLA: Decimal("7"),
            _M123_2019_2023_BASE_CASILLA: Decimal("42000.00"),
            _M123_2019_2023_RETENCIONES_CASILLA: Decimal("100.00"),
            _M123_2019_2023_REGULARIZACION_CASILLA: Decimal("0.00"),
            _M123_2019_2023_PREVIOUS_RESULT_CASILLA: Decimal("0.00"),
            _M123_2019_2023_INGRESO_CASILLA: Decimal("0.00"),
        },
        date_context={"filing_period": date(filing_year, 12, 31)},
    )
    casilla_06 = result.values[_M123_2019_2023_RESULTADO_CASILLA]
    assert casilla_06 == Decimal("100.00"), (
        f"{filing_year}: casilla 06 (suma retenciones+regularizacion = [03]+[05]) "
        f"should be 100.00 (= retenciones + 0), got {casilla_06}; "
        f"nperceptores (01=7) and base (02=42000) must not contribute"
    )


# ---------------------------------------------------------------------------
# No-silent-under-declaration advisory: the base total implies the retenciones
# total -- modelo verify nonzero guards, on every edition.
# ---------------------------------------------------------------------------

# The guard's operands per edition: the Orden HAC/56/2024 annex renumbers the
# base and retenciones totals but leaves the rule itself unchanged.
_BASE_IMPLIES_RETENCIONES_OPERANDS: dict[str, tuple[CasillaId, CasillaId]] = {
    _RETENCIONES_SUM_REVISION: (_M123_2019_2023_BASE_CASILLA, _M123_2019_2023_RETENCIONES_CASILLA),
    _SPLIT_BASE_REVISION: (_M123_BASE_TOTAL_CASILLA, validated_casilla_id("09")),
}


def test_m123_every_supported_year_carries_base_total_implies_retenciones_total_advisory() -> None:
    """Every supported M123 year guards the base-to-retenciones handoff.

    A positive withholding base with a zero withholding has no legitimate cause
    under RD 439/2007 arts. 75 and 90: art. 75 identifies capital-mobiliario
    rents subject to withholding and the type-based exceptions, while art. 90
    sets the positive rate for the withholding base. Neither depends on the
    form edition, so the ADVISORY `implies_nonzero` predicate is authored once
    and inherited; the split-base edition only renumbers its operands (base
    total [06] = [04] + [05], retenciones total [09] = [07] + [08]).
    """
    assert _SUPPORT.years
    for filing_year in _SUPPORT.years:
        snapshot = compiled_bundled_authority().snapshot("123", filing_year=filing_year, period="1T")
        _assert_base_total_implies_retenciones_total(snapshot)


def _assert_base_total_implies_retenciones_total(snapshot: RegistrySnapshot) -> None:
    revision_id = str(snapshot.revision.id)
    base, retenciones = _BASE_IMPLIES_RETENCIONES_OPERANDS[revision_id]
    predicate_id = f"modelo-123-{revision_id}-base-total-implica-retenciones-total"
    predicate = next(p for p in snapshot.revision.verification_predicates if p.predicate_id == predicate_id)

    assert predicate.expression == f'implies_nonzero(["{base}", "{retenciones}"])'
    assert predicate.finding_kind == "ADVISORY", (
        "must stay non-blocking: a category whose payer applied no withholding "
        "in one leaf while the other leaf covers it must not refuse the draft"
    )
    legal_refs = tuple(str(r) for r in predicate.legal_refs)
    assert "rd-439-2007:art-90" in legal_refs
    assert "rd-439-2007:art-75" in legal_refs
    assert "ley-35-2006:art-101" in legal_refs
