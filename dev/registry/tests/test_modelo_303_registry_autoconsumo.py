"""Tests for Modelo 303 autoconsumo calculations and record-design authorities."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.period import Period
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.bindings import resolve_available_bound_inputs_by_casilla_id
from cadrumo.domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from cadrumo.domain.calculations.registry.ledger_iva_bindings import resolve_ledger_iva_aggregation_binding_values
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_verification import VerificationFindingKind
from cadrumo.domain.calculations.registry.tests.snapshot_support import build_snapshot
from cadrumo.domain.period import calculation_filing_date

from ._modelo_303_registry_support import load_modelo_303

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# The statutory rate of each régimen general row, from Ley 37/1992 itself and
# not from the registry under test: art. 91.Dos 4 per cent (viviendas de
# protección oficial de régimen especial o de promoción pública delivered by
# their promotor, art. 91.Dos.1.6º), art. 91.Uno 10 per cent (edificios aptos
# para vivienda, art. 91.Uno.1.7º) and art. 90.Uno 21 per cent for any other
# building. Each row is (autoconsumo base casilla, base box, cuota box, rate).
_RATE_ROWS = {
    "super-reducido": ("iva.autoconsumo.promotor.super-reducido.base", "01", "03", Decimal("0.04")),
    "reducido": ("iva.autoconsumo.promotor.reducido.base", "04", "06", Decimal("0.10")),
    "general": ("iva.autoconsumo.promotor.general.base", "07", "09", Decimal("0.21")),
}
_PROFILE_BASE_BINDING = "modelo-303-autoconsumo-promotor-base"
_BASE_POR_TIPO: CasillaId = validated_casilla_id("iva.autoconsumo.promotor.base.por-tipo")
_RECONCILING_PREDICATE = "equals:iva-autoconsumo-promotor-base-equals-por-tipo"


def _revisions() -> tuple[ModeloRevision, ...]:
    modelo, _ = load_modelo_303()
    return tuple(sorted(modelo.revisions.values(), key=lambda revision: revision.valid_from))


def _calculate(
    revision: ModeloRevision, *, profile_base: Decimal, row_bases: dict[str, Decimal]
) -> dict[CasillaId, Decimal]:
    """Calculate one edition with an empty ledger and the promotor's autoconsumo as stated."""
    modelo, catalogues = load_modelo_303()
    assert revision.period_selector is not None
    period = revision.period_selector.periods[0]
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=revision.valid_from.year,
        period=period,
        revision_id=revision.id,
    )
    declared = {binding.id for binding in snapshot.revision.bindings}
    binding_values = {
        binding_id: value
        for binding_id, value in {
            "modelo-303-compensacion-pendiente-anteriores": Decimal("0"),
            _PROFILE_BASE_BINDING: profile_base,
            "modelo-303-profile-state-attribution-ratio": Decimal("100"),
            **resolve_ledger_iva_aggregation_binding_values(snapshot.revision, ()),
        }.items()
        if binding_id in declared
    }
    inputs: dict[CasillaId, Decimal] = {
        **resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values),
        **{validated_casilla_id(_RATE_ROWS[row][0]): base for row, base in row_bases.items()},
    }
    filing_period = calculation_filing_date(Period.from_year_and_code(revision.valid_from.year, period))
    result = calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        binding_values=binding_values,
        date_context={"filing_period": filing_period},
    )
    return dict(result.values)


def _box(values: dict[CasillaId, Decimal], casilla_id: str) -> Decimal:
    return values[validated_casilla_id(casilla_id)]


def _derives_rate_row_cuota(revision: ModeloRevision, box: str) -> bool:
    return next(casilla for casilla in revision.casillas if str(casilla.id) == box).formula is not None


@pytest.mark.parametrize("row", sorted(_RATE_ROWS))
def test_the_promotor_autoconsumo_is_declared_in_the_row_of_its_rate_in_every_edition(row: str) -> None:
    """Oracle: 1,400,000 of construction cost self-supplied at one rate, nothing else in the period.

    Ley 37/1992 art. 9.1º makes the self-supply an entrega de bienes, art.
    79.Tres sets its base at cost, and every design prints the régimen general
    rows by rate, so the base lands in that row's base box and its cuota,
    1,400,000 times the row's statutory rate, in that row's cuota and in [27].
    No other row moves and no edition keeps a cuota outside the printed rows.
    """
    _base_casilla, base_box, cuota_box, rate = _RATE_ROWS[row]
    base = Decimal("1400000")
    cuota = (base * rate).quantize(Decimal("0.01"))
    for revision in _revisions():
        values = _calculate(revision, profile_base=base, row_bases={row: base})
        assert _box(values, base_box) == base, revision.id
        assert _box(values, f"iva.cuota-devengada.{row}") == cuota, revision.id
        assert _box(values, "27") == cuota, revision.id
        assert _box(values, "iva.cuota-devengada-total") == cuota, revision.id
        if _derives_rate_row_cuota(revision, cuota_box):
            assert _box(values, cuota_box) == cuota, revision.id
        for other, (_, other_base_box, _, _) in _RATE_ROWS.items():
            if other != row:
                assert _box(values, other_base_box) == Decimal("0"), (revision.id, other)
                assert _box(values, f"iva.cuota-devengada.{other}") == Decimal("0"), (revision.id, other)
        assert validated_casilla_id("iva.autoconsumo.promotor.cuota") not in values, revision.id


def test_the_rate_row_cuota_is_proportional_to_the_base_it_is_given() -> None:
    """Anti-tautology: one base in two rows yields cuotas in the ratio of their statutory rates."""
    revision = _revisions()[-1]
    base = Decimal("700000")
    reducido = _calculate(revision, profile_base=base, row_bases={"reducido": base})
    general = _calculate(revision, profile_base=base, row_bases={"general": base})
    assert _box(reducido, "iva.cuota-devengada.reducido") == Decimal("70000.00")
    assert _box(general, "iva.cuota-devengada.general") == Decimal("147000.00")
    doubled = _calculate(revision, profile_base=base * 2, row_bases={"general": base * 2})
    assert _box(doubled, "iva.cuota-devengada.general") == Decimal("2") * _box(general, "iva.cuota-devengada.general")


def test_every_edition_refuses_a_profile_base_the_rate_rows_do_not_account_for() -> None:
    """The profile's rate-less base cannot reach [27] alone; the reconciling guard is blocking.

    With the base stated only on the profile, no row carries it, so the
    devengado total stays at zero and the two sides of the blocking equality
    differ; stating it in the rate rows closes the gap.
    """
    base = Decimal("1400000")
    split_rows = {"reducido": Decimal("1000000"), "general": Decimal("400000")}
    for revision in _revisions():
        predicate = next(item for item in revision.verification_predicates if str(item.id) == _RECONCILING_PREDICATE)
        assert predicate.expression == (
            'equals(["iva.autoconsumo.promotor.base", "iva.autoconsumo.promotor.base.por-tipo"])'
        )
        assert predicate.finding_kind is VerificationFindingKind.BLOCKING_RULE, revision.id
        unsplit = _calculate(revision, profile_base=base, row_bases={})
        assert _box(unsplit, "iva.autoconsumo.promotor.base") == base, revision.id
        assert unsplit[_BASE_POR_TIPO] == Decimal("0"), revision.id
        assert _box(unsplit, "27") == Decimal("0"), revision.id
        split = _calculate(revision, profile_base=base, row_bases=split_rows)
        assert split[_BASE_POR_TIPO] == base, revision.id
        # 1,000,000 x 10 % + 400,000 x 21 %
        assert _box(split, "27") == Decimal("184000.00"), revision.id


def test_modelo_303_workbook_parity_ref_anchors_record_design_layout() -> None:
    modelo, _ = load_modelo_303()
    revision = modelo.revisions["2022"]
    parity = next(p for p in revision.workbook_parity_refs if p.id == "modelo-303-dr")

    assert parity.workbook_source == "aeat-dr-303-2022"
    assert parity.formula_coverage == "record_design_layout"
    assert parity.fixture_id == "modelo-303-2022-record-design-layout"


def _prorrata_cnae_width(revision: ModeloRevision, casilla_id: str = "500") -> int | None:
    casilla = next((c for c in revision.casillas if c.id == casilla_id), None)
    return None if casilla is None or casilla.constraints is None else casilla.constraints.max_length


def test_modelo_303_four_digit_cnae_width_has_a_distinct_authority_role() -> None:
    modelo, _ = load_modelo_303()
    # The first design the registry authors with four-digit prorrata CNAE rows, compared
    # with the design authored immediately before it.
    ordered = sorted(modelo.revisions.values(), key=lambda revision: revision.valid_from)
    widened_index = next(index for index, revision in enumerate(ordered) if _prorrata_cnae_width(revision) == 4)
    assert widened_index > 0, "the four-digit CNAE design must have a three-digit predecessor"
    historical, current = ordered[widened_index - 1], ordered[widened_index]
    widened_year = current.valid_from.year
    prior_year = historical.valid_from.year

    for row, casilla_id in enumerate(("500", "505", "510", "515", "520"), start=1):
        prior = next(c for c in historical.casillas if c.id == casilla_id)
        widened = next(c for c in current.casillas if c.id == casilla_id)
        assert prior.constraints is not None and prior.constraints.min_length == prior.constraints.max_length == 3
        assert widened.constraints is not None and widened.constraints.min_length == widened.constraints.max_length == 4
        assert prior.semantic_role == f"m303_prorrata_actividad_fila_{row}_cnae"
        assert widened.semantic_role == f"m303_prorrata_actividad_fila_{row}_cnae_{widened_year}_four_digit"
        assert f"aeat-dr-303-{prior_year}" in prior.source_refs
        assert f"aeat-dr-303-{widened_year}" in widened.source_refs


# The defect-C2 regression that pinned the no-volume prorrata default used one
# filing-year sample. It is retired rather than widened because a dedicated
# two-revision gate now owns the claim: measured by mutation, breaking the
# branch on either live revision reds that gate. Its distinct mid-year axis was
# carried across before this test was removed.
