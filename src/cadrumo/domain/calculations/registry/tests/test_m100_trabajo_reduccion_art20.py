"""Modelo 100 work income: the art. 19.2.f expense and the art. 20 reduction, calculated from dated registry parameters.

The expected figures are the ones the Manual practico de Renta prints in its worked examples for each
edition of the art. 20 table, and the printed tramos for every other base. They are keyed by semantic
role, never by box number, and are calculated through the real published registry, formula runtime and
dated parameter selection. Nothing is read back from the table under test.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pytest

from .....core.aggregation import BindingSourceKind
from .....core.authority_grade import RegistryAuthorityGrade
from ..authority import PinnedAuthorityOperation
from ..bindings import resolve_available_bound_inputs_by_casilla_id
from ..errors import RegistryValidationError
from ..formula_runtime import RegistryCalculationResult, calculate_registry_snapshot
from ..renta_inmueble_bindings import renta_inmueble_totals
from ..schema import RegistrySnapshot
from .authored_editions import filing_year_envelope, supported_exercises_with_projection
from .modelo_100_registry_support import neutral_binding_values

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]

_FAMILIES = ("capital-mobiliario", "capital-inmobiliario", "ganancias-patrimoniales")
#: The profile of the printed examples: work income and the dwelling rent, nothing else.
_WORK_AND_RENT = frozenset(_FAMILIES) - {"capital-inmobiliario"}
_EXCLUDED_BINDING = "renta-profile-income-family-excluded-"
_CONTRADICTION = "income-family-contradicts-profile"

_ROLE_DINERARIO = "irpf_rendimiento_trabajo_importe_integro_dinerario"
_ROLE_REDUCCION_INTEGRO = "irpf_rendimiento_trabajo_reduccion"
_ROLE_GASTO_SS = "irpf_rendimiento_trabajo_gasto_ss_mutualidad"
_ROLE_DISCAPACIDAD = "irpf_rendimiento_trabajo_incremento_discapacitado_activo"
_ROLE_NETO_PREVIO = "irpf_rendimiento_trabajo_suma_rendimientos_netos_previos"
_ROLE_OTROS_GASTOS = "irpf_rendimiento_trabajo_gasto_otros"
_ROLE_NETO = "irpf_rendimiento_trabajo_rendimiento_neto"
_ROLE_REDUCCION = "irpf_rendimiento_trabajo_reduccion_gastos_generales"
_ROLE_NETO_REDUCIDO = "irpf_rendimiento_trabajo_rendimiento_neto_reducido"
_ROLE_OTRAS_RENTAS = "irpf_trabajo_rentas_distintas_del_trabajo"
#: The let properties' net yield, which LIRPF art. 20 weighs net of expenses and before reductions.
_ROLE_ALQUILER = "irpf_rendimiento_capital_inmobiliario_rendimiento_neto"

#: The tramos each edition of the table prints: (upper bound of the flat tramo, flat amount, multiplier, ceiling).
#: 5.565 and 6.498 print one sloped tramo; the 7.302 table prints two, written out in `_printed_reduction`.
_PRINTED_FLAT = {"5565": (Decimal("13115"), Decimal("5565"), Decimal("1.5"), Decimal("16825"))}
_PRINTED_FLAT |= {"6498": (Decimal("14047.5"), Decimal("6498"), Decimal("1.14"), Decimal("19747.5"))}


def _printed_reduction(table: str, rendimiento: Decimal) -> Decimal:
    """The reduction the manual prints for a rendimiento neto del trabajo in the named table."""
    if table == "7302":
        if rendimiento <= Decimal("14852"):
            return Decimal("7302")
        if rendimiento <= Decimal("17673.52"):
            return Decimal("7302") - Decimal("1.75") * (rendimiento - Decimal("14852"))
        if rendimiento < Decimal("19747.5"):
            return Decimal("2364.34") - Decimal("1.14") * (rendimiento - Decimal("17673.52"))
        return Decimal("0")
    flat_until, amount, slope, ceiling = _PRINTED_FLAT[table]
    if rendimiento <= flat_until:
        return amount
    if rendimiento < ceiling:
        return amount - slope * (rendimiento - flat_until)
    return Decimal("0")


@dataclass(frozen=True)
class _Scenario:
    """One printed worked example: the inputs, and the figures the manual prints for them."""

    table: str
    gross: Decimal
    reducciones: Decimal
    contributions: Decimal
    other_income: Decimal
    neto_previo: Decimal
    reduction: Decimal
    neto_reducido: Decimal


#: The 2022 and 2023 manuals print the same taxpayer (their example 18.300 gross); the 2024 manual prints its own.
_EXAMPLES = {
    "5565": _Scenario(
        "5565",
        Decimal("18300"),
        Decimal("3060"),
        Decimal("610"),
        Decimal("5500"),
        Decimal("14630"),
        Decimal("3292.50"),
        Decimal("5837.50"),
    ),
    "6498": _Scenario(
        "6498",
        Decimal("18300"),
        Decimal("3060"),
        Decimal("610"),
        Decimal("5500"),
        Decimal("14630"),
        Decimal("5833.95"),
        Decimal("3296.05"),
    ),
    "7302": _Scenario(
        "7302",
        Decimal("20300"),
        Decimal("3060"),
        Decimal("3600"),
        Decimal("5500"),
        Decimal("13640"),
        Decimal("7302"),
        Decimal("838"),
    ),
}
_DISABILITY_INCREMENT = Decimal("3500")


def _table_for(year: int, authority: PinnedAuthorityOperation) -> str:
    """Which printed table governs an exercise, from the envelope's floor and the date the 7.302 text took effect."""
    seven_thousand_year = authority.legal_reference("ley-35-2006:art-20").effective_from.year
    floor = filing_year_envelope().floor
    if year >= seven_thousand_year:
        return "7302"
    return "5565" if year == floor else "6498"


def _casilla(snapshot: RegistrySnapshot, role: str) -> str:
    matches = [str(casilla.id) for casilla in snapshot.revision.casillas if casilla.semantic_role == role]
    assert len(matches) == 1, (role, matches)
    return matches[0]


def _snapshot(
    registry_snapshot: Callable[..., RegistrySnapshot],
    year: int,
    grade: RegistryAuthorityGrade = RegistryAuthorityGrade.CALCULATION,
) -> RegistrySnapshot:
    return registry_snapshot("100", year, "0A", grade=grade)


def _calculate(
    snapshot: RegistrySnapshot,
    year: int,
    figures: Mapping[str, Decimal],
    *,
    excluded: frozenset[str] = frozenset(_FAMILIES),
) -> RegistryCalculationResult:
    """Calculate one return whose inputs are named by role; ``excluded`` are the families the profile excludes."""
    bindings = tuple(
        binding for binding in snapshot.revision.bindings if binding.source is not BindingSourceKind.RELATION_PREFILL
    )
    decimals, booleans, dates, enums = neutral_binding_values(bindings)
    booleans["renta-modelo-100-estimacion-directa-es-normal"] = True
    decimals |= {"renta-profile-declaration-type": Decimal(1)}
    for family in _FAMILIES:
        booleans[_EXCLUDED_BINDING + family] = family in excluded
    column_totals = {
        str(provider.target_casilla_id): binding.id for binding, provider in renta_inmueble_totals(snapshot.revision)
    }
    inputs: dict[str, Decimal] = {}
    for role, value in figures.items():
        casilla = next(item for item in snapshot.revision.casillas if item.semantic_role == role)
        if casilla.binding is not None:
            # A box the registry binds to its source is stated through that source, never typed on the return.
            decimals[casilla.binding] = value
        elif str(casilla.id) in column_totals:
            # A let property's column is held per row; the calculation reads its total over the rows.
            decimals[column_totals[str(casilla.id)]] = value
        else:
            inputs[str(casilla.id)] = value
    return calculate_registry_snapshot(
        snapshot,
        inputs={**inputs, **resolve_available_bound_inputs_by_casilla_id(snapshot.revision, decimals)},
        date_context={"filing_period": date(year, 12, 31)},
        binding_values=decimals,
        enum_binding_values=enums,
        relation_values={
            "renta-modelo-130-pagos-fraccionados": Decimal(0),
            "renta-modelo-131-pagos-fraccionados": Decimal(0),
        },
        date_binding_values=dates,
        boolean_binding_values=booleans,
    )


def _example_figures(example: _Scenario) -> dict[str, Decimal]:
    return {
        _ROLE_DINERARIO: example.gross,
        _ROLE_REDUCCION_INTEGRO: example.reducciones,
        _ROLE_GASTO_SS: example.contributions,
        _ROLE_DISCAPACIDAD: _DISABILITY_INCREMENT,
        _ROLE_ALQUILER: example.other_income,
    }


def _value(snapshot: RegistrySnapshot, result: RegistryCalculationResult, role: str) -> Decimal:
    return result.values[_casilla(snapshot, role)]


def _exercise_for(table: str, authority: PinnedAuthorityOperation) -> int:
    envelope = filing_year_envelope()
    return next(year for year in envelope.years if _table_for(year, authority) == table)


@pytest.mark.parametrize("table", sorted(_EXAMPLES))
def test_manual_worked_example_of_each_art_20_table(
    table: str,
    registry_snapshot: Callable[..., RegistrySnapshot],
    registry_authority: PinnedAuthorityOperation,
) -> None:
    """Each edition's printed example: the reduction is applied to the base before the 19.2.f expenses.

    The other income of the example is a dwelling rent of 5.500 euros net, below the 6.500 limit, stated as
    the let properties' net yield before reductions; the other families are excluded by the profile.
    """
    example = _EXAMPLES[table]
    year = _exercise_for(table, registry_authority)
    snapshot = _snapshot(registry_snapshot, year)

    result = _calculate(snapshot, year, _example_figures(example), excluded=_WORK_AND_RENT)

    assert _value(snapshot, result, _ROLE_NETO_PREVIO) == example.neto_previo
    assert _value(snapshot, result, _ROLE_OTROS_GASTOS) == Decimal("2000.00")
    assert _value(snapshot, result, _ROLE_OTRAS_RENTAS) == example.other_income
    assert _value(snapshot, result, _ROLE_NETO) == example.neto_previo - Decimal("2000") - _DISABILITY_INCREMENT
    assert _value(snapshot, result, _ROLE_REDUCCION) == example.reduction
    assert _value(snapshot, result, _ROLE_NETO_REDUCIDO) == example.neto_reducido


@pytest.mark.parametrize("table", sorted(_EXAMPLES))
def test_other_income_above_the_limit_removes_the_reduction(
    table: str,
    registry_snapshot: Callable[..., RegistrySnapshot],
    registry_authority: PinnedAuthorityOperation,
) -> None:
    """Art. 20 loses the reduction when the other rentas are superiores a 6.500 euros; exactly 6.500 keeps it."""
    example = _EXAMPLES[table]
    year = _exercise_for(table, registry_authority)
    snapshot = _snapshot(registry_snapshot, year)

    at_limit = _calculate(
        snapshot, year, {**_example_figures(example), _ROLE_ALQUILER: Decimal("6500.00")}, excluded=_WORK_AND_RENT
    )
    above = _calculate(
        snapshot, year, {**_example_figures(example), _ROLE_ALQUILER: Decimal("6500.01")}, excluded=_WORK_AND_RENT
    )

    assert _value(snapshot, at_limit, _ROLE_REDUCCION) == example.reduction
    assert _value(snapshot, above, _ROLE_REDUCCION) == Decimal("0.00")
    assert _value(snapshot, above, _ROLE_NETO_REDUCIDO) == _value(snapshot, above, _ROLE_NETO)


@pytest.mark.parametrize("table", sorted(_EXAMPLES))
def test_a_base_past_the_last_tramo_has_no_reduction(
    table: str,
    registry_snapshot: Callable[..., RegistrySnapshot],
    registry_authority: PinnedAuthorityOperation,
) -> None:
    year = _exercise_for(table, registry_authority)
    snapshot = _snapshot(registry_snapshot, year)

    result = _calculate(snapshot, year, {_ROLE_DINERARIO: Decimal("30000")})

    assert _value(snapshot, result, _ROLE_NETO_PREVIO) == Decimal("30000.00")
    assert _value(snapshot, result, _ROLE_REDUCCION) == Decimal("0.00")
    assert _value(snapshot, result, _ROLE_NETO_REDUCIDO) == Decimal("28000.00")


@pytest.mark.parametrize("table", sorted(_EXAMPLES))
@pytest.mark.parametrize("base", ["0", "1500", "13000", "14500", "16000", "18000", "19000", "19700"])
def test_each_printed_tramo_of_each_table(
    table: str,
    base: str,
    registry_snapshot: Callable[..., RegistrySnapshot],
    registry_authority: PinnedAuthorityOperation,
) -> None:
    """The reduction follows the printed tramos; it never exceeds the rendimiento left after the 19.2.f expenses."""
    year = _exercise_for(table, registry_authority)
    snapshot = _snapshot(registry_snapshot, year)
    neto_previo = Decimal(base)

    result = _calculate(snapshot, year, {_ROLE_DINERARIO: neto_previo})

    expected = min(_printed_reduction(table, neto_previo), max(Decimal("0"), neto_previo - Decimal("2000")))
    if neto_previo <= 0:
        expected = Decimal("0")
    assert _value(snapshot, result, _ROLE_REDUCCION) == expected.quantize(Decimal("0.01"))
    assert _value(snapshot, result, _ROLE_NETO_REDUCIDO) >= 0


def test_the_fixed_expense_is_capped_by_the_base_and_never_leaves_the_balance_negative(
    registry_snapshot: Callable[..., RegistrySnapshot],
) -> None:
    """Art. 19.2.f limits the 2.000 euros to the gross left after the other expenses."""
    year = filing_year_envelope().horizon
    snapshot = _snapshot(registry_snapshot, year)

    small = _calculate(snapshot, year, {_ROLE_DINERARIO: Decimal("1200")})
    none = _calculate(snapshot, year, {_ROLE_DINERARIO: Decimal("0")})

    assert _value(snapshot, small, _ROLE_OTROS_GASTOS) == Decimal("1200.00")
    assert _value(snapshot, small, _ROLE_NETO) == Decimal("0.00")
    assert _value(snapshot, small, _ROLE_REDUCCION) == Decimal("0.00")
    assert _value(snapshot, none, _ROLE_OTROS_GASTOS) == Decimal("0.00")


def test_a_worker_whose_profile_states_only_work_income_gets_the_reduction(
    registry_snapshot: Callable[..., RegistrySnapshot],
    registry_authority: PinnedAuthorityOperation,
) -> None:
    """Every other family is a proven zero, so the other-income gate resolves and the reduction applies."""
    example = _EXAMPLES["7302"]
    year = _exercise_for("7302", registry_authority)
    snapshot = _snapshot(registry_snapshot, year)

    figures = {
        _ROLE_DINERARIO: example.gross,
        _ROLE_REDUCCION_INTEGRO: example.reducciones,
        _ROLE_GASTO_SS: example.contributions,
    }

    result = _calculate(snapshot, year, figures)

    assert _value(snapshot, result, _ROLE_OTRAS_RENTAS) == Decimal("0.00")
    assert _value(snapshot, result, _ROLE_REDUCCION) == Decimal("7302.00")


def test_figures_held_for_a_family_the_profile_excludes_leave_the_reduction_unresolved(
    registry_snapshot: Callable[..., RegistrySnapshot],
    registry_authority: PinnedAuthorityOperation,
) -> None:
    """A stated list that excludes a family contradicts a rent held for it: the gate is unresolved, never zero."""
    example = _EXAMPLES["7302"]
    year = _exercise_for("7302", registry_authority)
    snapshot = _snapshot(registry_snapshot, year)
    figures = {**_example_figures(example), _ROLE_ALQUILER: Decimal("100")}

    contradicted = _calculate(snapshot, year, figures, excluded=frozenset(_FAMILIES))
    declared = _calculate(snapshot, year, figures, excluded=frozenset(_FAMILIES) - {"capital-inmobiliario"})

    node = _casilla(snapshot, _ROLE_OTRAS_RENTAS)
    reduction = _casilla(snapshot, _ROLE_REDUCCION)
    unresolved = {str(outcome.casilla_id): outcome for outcome in contradicted.unresolved_outcomes}
    assert node in unresolved
    assert unresolved[node].reason.value == _CONTRADICTION
    # A target that reads an unresolved source is absent: it carries no value, and is never read as zero.
    assert reduction not in contradicted.values
    assert _casilla(snapshot, _ROLE_NETO_REDUCIDO) not in contradicted.values
    assert _value(snapshot, declared, _ROLE_REDUCCION) == Decimal("7302.00")


@pytest.mark.parametrize("excluded_family", _FAMILIES)
def test_each_excludable_family_is_checked_against_its_own_figures(
    excluded_family: str,
    registry_snapshot: Callable[..., RegistrySnapshot],
    registry_authority: PinnedAuthorityOperation,
) -> None:
    """The stated exclusion of one family does not hide figures of another family, which count as income."""
    example = _EXAMPLES["7302"]
    year = _exercise_for("7302", registry_authority)
    snapshot = _snapshot(registry_snapshot, year)
    figures = {**_example_figures(example), _ROLE_ALQUILER: Decimal("7000")}

    result = _calculate(snapshot, year, figures, excluded=frozenset({excluded_family}))

    if excluded_family == "capital-inmobiliario":
        assert _casilla(snapshot, _ROLE_REDUCCION) not in result.values
    else:
        assert _value(snapshot, result, _ROLE_OTRAS_RENTAS) == Decimal("7000.00")
        assert _value(snapshot, result, _ROLE_REDUCCION) == Decimal("0.00")


def test_every_supported_year_resolves_its_own_table(
    registry_snapshot: Callable[..., RegistrySnapshot],
    registry_authority: PinnedAuthorityOperation,
) -> None:
    """Each exercise of the envelope, projected ones included, is reduced by the table that governs it."""
    exercises = supported_exercises_with_projection("100")
    tables_seen: set[str] = set()
    for year in exercises:
        table = _table_for(year, registry_authority)
        tables_seen.add(table)
        snapshot = _snapshot(registry_snapshot, year)
        base = Decimal("15000")

        result = _calculate(snapshot, year, {_ROLE_DINERARIO: base})

        assert _value(snapshot, result, _ROLE_REDUCCION) == _printed_reduction(table, base).quantize(Decimal("0.01")), (
            year
        )
    assert tables_seen == set(_EXAMPLES)


def test_a_projected_year_reduces_by_the_nearest_table_without_promoting_its_grade(
    registry_snapshot: Callable[..., RegistrySnapshot],
    registry_authority: PinnedAuthorityOperation,
) -> None:
    """A year without its own edition is calculated, never filed: filing grade is refused for it."""
    envelope = filing_year_envelope()
    authored = set(_authored_exercises())
    projected = [year for year in envelope.years if year not in authored]
    if not projected:
        pytest.skip("the envelope has no projected exercise")
    for year in projected:
        calculation = _snapshot(registry_snapshot, year)
        result = _calculate(calculation, year, {_ROLE_DINERARIO: Decimal("15000")})
        assert _value(calculation, result, _ROLE_REDUCCION) == _printed_reduction(
            _table_for(year, registry_authority), Decimal("15000")
        ).quantize(Decimal("0.01"))
        with pytest.raises(RegistryValidationError) as refusal:
            _snapshot(registry_snapshot, year, RegistryAuthorityGrade.FILING)
        facts = dict(getattr(getattr(refusal.value, "registry_failure", None), "facts", {}) or {})
        assert "authored_filing_year" in facts


def _authored_exercises() -> tuple[int, ...]:
    from .authored_editions import supported_authored_exercises

    return supported_authored_exercises("100")
