"""Modelo 123 registry behaviour for quarterly capital-income withholding filings."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.casilla_id import CasillaId, validated_casilla_id
from .....core.resources.bundled_data import bundled_path
from .._validate import RegistryValidator
from ..authority import bundled_authority
from ..formula_runtime import calculate_registry_snapshot
from ..schema import RegistrySnapshot
from ..snapshot import build_snapshot
from ..temporal import select_revision
from ._registry_schema_support import _committed_modelo, _committed_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SUPPORTED_DEADLINES = {
    2022: (
        ("2022-04-20", "2022-04-15"),
        ("2022-07-20", "2022-07-15"),
        ("2022-10-20", "2022-10-15"),
        ("2023-01-20", "2023-01-15"),
    ),
    2023: (
        ("2023-04-20", "2023-04-15"),
        ("2023-07-20", "2023-07-15"),
        ("2023-10-20", "2023-10-15"),
        ("2024-01-22", "2024-01-17"),
    ),
    2024: (
        ("2024-04-22", "2024-04-17"),
        ("2024-07-22", "2024-07-17"),
        ("2024-10-21", "2024-10-16"),
        ("2025-01-20", "2025-01-15"),
    ),
    2025: (
        ("2025-04-21", "2025-04-15"),
        ("2025-07-21", "2025-07-16"),
        ("2025-10-20", "2025-10-15"),
        ("2026-01-20", "2026-01-15"),
    ),
    2026: (
        ("2026-04-20", "2026-04-15"),
        ("2026-07-20", "2026-07-15"),
        ("2026-10-20", "2026-10-15"),
        ("2027-01-20", None),
    ),
}


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
    modelo, catalogues = _committed_modelo("123")

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
        "2019-2023": "boe-modelo-123-2007-form-text",
        "2024-y-siguientes": "boe-modelo-123-2024-form-text",
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
            2023,
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
            2026,
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
    modelo, catalogues = _committed_modelo("123")

    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)
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
    modelo, _ = _committed_modelo("123")
    windows = {
        (window.filing_year, window.period.registry_token): (revision, window)
        for revision in modelo.revisions.values()
        for window in revision.deadline_windows
    }

    assert sum(len(revision.deadline_windows) for revision in modelo.revisions.values()) == len(windows) == 20
    current_revision = modelo.revisions["2024-y-siguientes"]
    assert set(current_revision.constructs[0].deadline_windows) == {
        window.id for window in current_revision.deadline_windows
    }

    for filing_year, expected_year in _SUPPORTED_DEADLINES.items():
        expected_periods = {"1T", "2T", "3T", "4T"}
        assert {period for year, period in windows if year == filing_year} == expected_periods
        projected = bundled_authority().deadline_windows(filing_year, modelos=("123",))
        assert len(projected) == 4
        assert {window.period.registry_token for _, _, window in projected} == expected_periods

        for quarter, (close_text, payment_text) in enumerate(expected_year, start=1):
            period = f"{quarter}T"
            revision, window = windows[(filing_year, period)]
            assert select_revision(modelo, filing_year=filing_year, period=period) is revision
            assert window.id == f"modelo-123-{filing_year}-{period.lower()}"
            assert window.filing_year == window.period.filing_year == filing_year
            assert window.opens_on == date(window.closes_on.year, window.closes_on.month, 1)
            assert window.closes_on == date.fromisoformat(close_text)
            assert window.payment_cutoff_on == (None if payment_text is None else date.fromisoformat(payment_text))
            expected_sources = {"aeat-modelo-123-procedure"}
            if window.closes_on.year <= 2026:
                expected_sources.add(f"aeat-calendario-contribuyente-{window.closes_on.year}")
            assert set(window.source_refs) == expected_sources

    assert windows[(2026, "4T")][1].payment_cutoff_on is None


# ---------------------------------------------------------------------------
# Casilla 06 arithmetic oracle (Aitor #211)
#
# Authority: Orden HAC/56/2024 Anexo II + BOE annex form text.
# "Base de retenciones e ingresos a cuenta" in the Totales column = [04] + [05].
# Casilla 06 must equal the sum of the two base sub-totals only.
# Perceptor counts (casillas 01, 02, 03) must NOT contribute to casilla 06.
# ---------------------------------------------------------------------------


def _snapshot_2024(filing_year: int = 2024) -> RegistrySnapshot:
    return _committed_snapshot("123", filing_year, "1T")


def _calculate_2024(
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
        date_context={"filing_period": date(2024, 12, 31)},
    )


def test_m123_casilla_06_equals_base_dividendos_plus_base_resto() -> None:
    """Casilla 06 = [04] + [05] (base total).

    Oracle authority: Orden HAC/56/2024 BOE annex text, field label
    "Base de retenciones e ingresos a cuenta" in the Totales column.

    With base_dividendos=42000 and base_resto=0, casilla 06 must be 42000.
    The perceptor count (nperceptores=7 split as 01=4, 02=3) must not
    contribute to casilla 06.
    """
    snapshot = _snapshot_2024()
    result = _calculate_2024(
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
    snapshot = _snapshot_2024()
    result = _calculate_2024(
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
    snapshot = _snapshot_2024()
    base_fixed = Decimal("42000.00")
    results = [
        _calculate_2024(
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


def test_m123_2019_2023_casilla_06_invariant_to_nperceptores_and_base() -> None:
    """2019-2023 revision: casilla 06 is retenciones+regularizacion, not base.

    Authority: BOE Modelo 123 annex text citation "( 03 + 05 )".
    Inputs 01 (nperceptores) and 02 (base retenciones) are
    manual pass-through casillas with no formula; they must not affect
    casilla 06 (Suma de retenciones y regularizacion = [03] + [05]).
    """
    modelo, catalogues = _committed_modelo("123")
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2022,
        period="1T",
    )
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
        date_context={"filing_period": date(2022, 12, 31)},
    )
    casilla_06 = result.values[_M123_2019_2023_RESULTADO_CASILLA]
    assert casilla_06 == Decimal("100.00"), (
        f"casilla 06 (suma retenciones+regularizacion = [03]+[05]) "
        f"should be 100.00 (= retenciones + 0), got {casilla_06}; "
        f"nperceptores (01=7) and base (02=42000) must not contribute"
    )


# ---------------------------------------------------------------------------
# No-silent-under-declaration advisory: casilla 06 (base total) implies
# casilla 09 (retenciones total) -- modelo verify nonzero guards.
# ---------------------------------------------------------------------------


def test_m123_2024_carries_base_total_implies_retenciones_total_advisory() -> None:
    """The M123 2024-y-siguientes revision guards the base-to-retenciones handoff.

    Casilla 06 (base total = [04] + [05]) and casilla 09 (retenciones total =
    [07] + [08]) are both formula-computed from independently manual leaf
    casillas. A positive base total with a zero retenciones total has no
    legitimate cause under RD 439/2007 arts. 75 and 90: art. 75 identifies
    capital-mobiliario rents subject to withholding and the type-based
    exceptions, while art. 90 sets the positive rate for the withholding base.
    The ADVISORY `implies_nonzero` predicate therefore surfaces a finding
    rather than silently granting VERIFICADO_COMPLETO.
    """
    snapshot = _snapshot_2024()

    # Named for the revision it lives on, matching its sibling
    # `modelo-123-2024-y-siguientes-base-declarada-cuando-rentas-positivas`;
    # the revision is `2024-y-siguientes`, not `2024`.
    predicate_id = "modelo-123-2024-y-siguientes-base-total-implica-retenciones-total"
    predicate = next(p for p in snapshot.revision.verification_predicates if p.predicate_id == predicate_id)

    assert predicate.expression == 'implies_nonzero(["06", "09"])'
    assert predicate.finding_kind == "ADVISORY", (
        "must stay non-blocking: a category whose payer applied no withholding "
        "in one leaf while the other leaf covers it must not refuse the draft"
    )
    legal_refs = tuple(str(r) for r in predicate.legal_refs)
    assert "rd-439-2007:art-90" in legal_refs
    assert "rd-439-2007:art-75" in legal_refs
    assert "ley-35-2006:art-101" in legal_refs
