"""Tests for registry-backed formula runtime."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import cast

import pytest
from pydantic import ValidationError

from .....core.resources import bundled_path
from .._authority import ValidatedRegistryAuthority
from .._bindings import (
    CasillaObservation,
    RegistryModeloObservation,
    _PreviousModeloSelector,
    previous_filing_observation_requirements,
    resolve_previous_filing_binding_values,
)
from .._errors import RegistryValidationError
from .._formula_runtime import calculate_registry_snapshot
from .._relations import relation_source_requirements, resolve_relation_values_from_observations
from .._schema import DataBindingDefinition, RegistrySnapshot
from .._snapshot import build_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PREVIOUS_YEAR_NET_INCOME_BINDING = "irpf.previous_year_economic_activity_net_income"
_PREVIOUS_PERIOD_NEGATIVE_RESULT_BINDING = "modelo-130-resultados-negativos-anteriores"


@pytest.fixture
def committed_modelo_130_snapshot(
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> RegistrySnapshot:
    return registry_snapshot("130", 2026, "1T")


@pytest.fixture
def committed_modelo_180_snapshot(
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> RegistrySnapshot:
    return registry_snapshot("180", 2026, "0A")


def _modelo_180_snapshot_with_inactive_relation_period(
    registry_authority: ValidatedRegistryAuthority,
) -> RegistrySnapshot:
    modelo = registry_authority.modelo("180")
    revision = modelo.revisions["2023-y-siguientes"]
    selector = revision.period_selector.model_copy(update={"periods": ("0A", "1T")})
    widened_revision = revision.model_copy(update={"period_selector": selector})
    widened_modelo = modelo.model_copy(update={"revisions": {**modelo.revisions, revision.id: widened_revision}})
    return build_snapshot(
        widened_modelo,
        registry_authority.catalogues,
        source_root=bundled_path(),
        filing_year=2026,
        period="1T",
    )


def test_registry_formula_runtime_calculates_committed_modelo_in_dependency_order(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    result = calculate_registry_snapshot(
        committed_modelo_130_snapshot,
        inputs={
            "01": Decimal("10000"),
            "02": Decimal("4000"),
            "05": Decimal("250"),
            "06": Decimal("100"),
            "08": Decimal("2000"),
            "10": Decimal("10"),
            "16": Decimal("0"),
            "18": Decimal("0"),
        },
        date_context={"filing_period": date(2026, 3, 31)},
        binding_values={
            _PREVIOUS_YEAR_NET_INCOME_BINDING: Decimal("13000"),
            _PREVIOUS_PERIOD_NEGATIVE_RESULT_BINDING: Decimal("0"),
            # C03 (rendimiento neto) was converted from computed to
            # bound by a parallel campaign; supply the actividad-
            # economica cumulative binding value so the bound
            # casilla resolves.
            "modelo-130-actividad-economica-rendimiento-neto-cumulative": Decimal("6000"),
        },
    )

    # C03 is now bound (not computed) so it does not appear in
    # result.entries. Order assertions adjusted to exclude C03.
    order = {entry.target: index for index, entry in enumerate(result.entries)}
    assert order["04"] < order["07"] < order["12"] < order["14"] < order["17"] < order["19"]
    assert order["09"] < order["11"] < order["12"]
    assert "19" in result.values
    assert "rd-439-2007:art-110" in result.entries[0].legal_refs


def test_registry_formula_runtime_rejects_inputs_for_computed_casillas(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    # C04 (Total ingresos) is a computed casilla in the M130 1T
    # snapshot; previously C03 was used but a parallel campaign
    # changed C03 to input_kind="bound" via an actividad-economica
    # cumulative-rendimiento-neto binding.
    with pytest.raises(RegistryValidationError, match="computed registry casillas cannot be supplied"):
        calculate_registry_snapshot(
            committed_modelo_130_snapshot,
            inputs={"04": Decimal("6000")},
            date_context={"filing_period": date(2026, 3, 31)},
            binding_values={_PREVIOUS_YEAR_NET_INCOME_BINDING: Decimal("13000")},
        )


def test_registry_formula_runtime_preserves_signed_intermediate_results_from_official_instructions(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    """Structural sign-propagation assertion — not a numeric tautology.

    This test asserts no hand-computed Decimal. It exercises two
    structural contracts of the modelo-130 pago-fraccionado graph that
    hold regardless of the exact arithmetic:

    * Sign propagation: the modelo-130 form (AEAT *Diseño de registros*
      modelo 130) carries explicitly signable "diferencia" casillas —
      a pago-fraccionado period whose deductible amounts (05/06/08/10)
      and prior payments outweigh the period's gross liability must
      drive its intermediate "diferencia" casillas (07, 11) negative.
      A formula that clamped these or flipped a subtraction would fail
      the strict-negative assertion.
    * Floor contract: casilla 12 carries a ``MAX(_, 0)`` floor in the
      registry (the period result the operator pays is never negative;
      a refund is carried elsewhere). The ``>= 0`` assertion exercises
      that declared floor, not a derived value.

    Per the no-tautological-calculation-tests rule this is the
    "structural assertion" alternative: it would fail if the registry
    formula graph were wrong against AEAT, yet manufactures no Decimal
    expectation from the formula under test.
    """

    result = calculate_registry_snapshot(
        committed_modelo_130_snapshot,
        inputs={
            "01": Decimal("1000"),
            "02": Decimal("0"),
            "05": Decimal("300"),
            "06": Decimal("50"),
            "08": Decimal("100"),
            "10": Decimal("10"),
            "16": Decimal("0"),
            "18": Decimal("0"),
        },
        date_context={"filing_period": date(2026, 3, 31)},
        binding_values={
            _PREVIOUS_YEAR_NET_INCOME_BINDING: Decimal("13000"),
            _PREVIOUS_PERIOD_NEGATIVE_RESULT_BINDING: Decimal("0"),
        },
    )

    assert result.values["07"] < Decimal("0")
    assert result.values["11"] < Decimal("0")
    assert result.values["12"] >= Decimal("0")


def test_registry_formula_runtime_calculates_income_reduction_from_previous_year_binding(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    result = calculate_registry_snapshot(
        committed_modelo_130_snapshot,
        inputs={
            "01": Decimal("10000"),
            "02": Decimal("4000"),
            "05": Decimal("250"),
            "06": Decimal("100"),
            "08": Decimal("2000"),
            "10": Decimal("10"),
            "16": Decimal("0"),
            "18": Decimal("0"),
        },
        date_context={"filing_period": date(2026, 3, 31)},
        binding_values={
            _PREVIOUS_YEAR_NET_INCOME_BINDING: Decimal("9500"),
            _PREVIOUS_PERIOD_NEGATIVE_RESULT_BINDING: Decimal("0"),
        },
    )

    assert {"13", "19"} <= set(result.values)
    entries = {entry.target: entry for entry in result.entries}
    assert "13" in entries and "19" in entries


def test_previous_filing_binding_resolves_from_observed_irpf_casillas(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    binding = _previous_year_net_income_binding(committed_modelo_130_snapshot)
    selector = binding.selector
    source_casillas = selector["source_casillas"]
    assert isinstance(source_casillas, tuple)
    observed_values = {casilla_id: Decimal(index + 1) for index, casilla_id in enumerate(source_casillas)}

    result = resolve_previous_filing_binding_values(
        committed_modelo_130_snapshot.revision,
        (
            RegistryModeloObservation(
                modelo=str(selector["source_modelo"]),
                filing_year=2025,
                period=str(selector["period"]),
                observations=tuple(
                    CasillaObservation(casilla_id=cid, value=val) for cid, val in observed_values.items()
                ),
            ),
        ),
        filing_year=2026,
        period="1T",
    )

    assert _PREVIOUS_YEAR_NET_INCOME_BINDING in result
    assert isinstance(result[_PREVIOUS_YEAR_NET_INCOME_BINDING], Decimal)


def test_previous_filing_requirements_are_declared_from_registry_binding_selector(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    binding = _previous_year_net_income_binding(committed_modelo_130_snapshot)
    selector = binding.selector

    requirements = previous_filing_observation_requirements(
        committed_modelo_130_snapshot.revision,
        filing_year=2026,
        period="1T",
    )

    assert len(requirements) == 1
    requirement = requirements[0]
    assert requirement.modelo == selector["source_modelo"]
    assert requirement.filing_year == 2025
    assert requirement.period == selector["period"]
    assert requirement.binding_ids == (_PREVIOUS_YEAR_NET_INCOME_BINDING,)
    source_casillas = selector["source_casillas"]
    assert isinstance(source_casillas, tuple)
    assert requirement.source_casillas == tuple(sorted(source_casillas))


def test_relation_requirements_cover_all_source_periods_for_annual_summary(
    committed_modelo_180_snapshot: RegistrySnapshot,
) -> None:
    # M180 ← M115 is canonically a RELATION fold-in (aggregation-taxonomy ADR
    # ruling 2): the slot bindings declare source = "relation_prefill" and the
    # requirement set is produced by the relation requirement resolver, not the
    # previous-filing one (which now skips relation_prefill slots by design).
    requirements = relation_source_requirements(
        committed_modelo_180_snapshot.revision,
        filing_year=2026,
        period="0A",
    )

    # The three 180 annual_summary relations share one source quadruple
    # (115/2026/[1T-4T]) grouped per source_output; assert the periods cover all
    # four quarters and the relation source modelo/year are correct.
    assert {requirement.source_modelo for requirement in requirements} == {"115"}
    assert {requirement.filing_year for requirement in requirements} == {2026}
    assert all(tuple(requirement.periods) == ("1T", "2T", "3T", "4T") for requirement in requirements)
    target_bindings = {tb for requirement in requirements for tb in requirement.target_bindings}
    assert target_bindings == {
        "modelo-180-115-base-anual",
        "modelo-180-115-perceptores-anual",
        "modelo-180-115-retenciones-anual",
    }
    assert {requirement.source_output for requirement in requirements} == {"01", "02", "03"}


def test_relation_resolves_annual_summary_from_all_source_periods(
    committed_modelo_180_snapshot: RegistrySnapshot,
) -> None:
    # Per .claude/rules/no-tautological-calculation-tests.md, we do not assert
    # base-anual / retenciones-anual equal the author's hand-summation of the
    # synthetic inputs; the runtime's `op = "sum"` aggregator and the author
    # would share the same arithmetic. Instead this test asserts the canonical
    # RELATION resolver (now live) produces:
    #   1. graph-wiring: the three expected relation ids appear in result;
    #   2. structural: perceptores = number of observations (count, not
    #      arithmetic on input values);
    #   3. type: the summed relations are Decimal-valued, sign-preserving.
    observations = tuple(
        RegistryModeloObservation(
            modelo="115",
            filing_year=2026,
            period=period,
            observations=(
                CasillaObservation(casilla_id="01", value=Decimal("1")),
                CasillaObservation(casilla_id="02", value=base),
                CasillaObservation(casilla_id="03", value=retention),
            ),
        )
        for period, base, retention in (
            ("1T", Decimal("100.00"), Decimal("19.00")),
            ("2T", Decimal("200.00"), Decimal("38.00")),
            ("3T", Decimal("300.00"), Decimal("57.00")),
            ("4T", Decimal("-50.00"), Decimal("0.00")),
        )
    )

    result = resolve_relation_values_from_observations(
        committed_modelo_180_snapshot.revision,
        observations,
        filing_year=2026,
        period="0A",
    )

    assert set(result.keys()) == {
        "modelo-180-rel-115-perceptores-anual",
        "modelo-180-rel-115-base-anual",
        "modelo-180-rel-115-retenciones-anual",
    }
    assert result["modelo-180-rel-115-perceptores-anual"] == Decimal(len(observations))
    assert isinstance(result["modelo-180-rel-115-base-anual"], Decimal)
    assert isinstance(result["modelo-180-rel-115-retenciones-anual"], Decimal)


def test_previous_filing_binding_requires_complete_observed_casillas(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    binding = _previous_year_net_income_binding(committed_modelo_130_snapshot)
    selector = binding.selector
    source_casillas = selector["source_casillas"]
    assert isinstance(source_casillas, tuple)

    with pytest.raises(RegistryValidationError, match="requires observed casilla"):
        resolve_previous_filing_binding_values(
            committed_modelo_130_snapshot.revision,
            (
                RegistryModeloObservation(
                    modelo=str(selector["source_modelo"]),
                    filing_year=2025,
                    period=str(selector["period"]),
                    observations=(CasillaObservation(casilla_id=source_casillas[0], value=Decimal("1")),),
                ),
            ),
            filing_year=2026,
            period="1T",
        )


def test_previous_modelo_selector_max_year_delta_unset_preserves_unbounded_anchors() -> None:
    selector = _PreviousModeloSelector(
        source_modelo="130",
        source_output="saldo-negativo-fin-periodo",
        source_period_offset_from_target=-1,
    )

    assert selector.max_year_delta is None
    assert selector.required_period_anchors_for_target("1T") == ((-1, "4T"),)
    assert selector.required_period_anchors_for_target("2T") == ((0, "1T"),)


def test_previous_modelo_selector_max_year_delta_zero_drops_cross_ejercicio_offset_anchor() -> None:
    selector = _PreviousModeloSelector(
        source_modelo="130",
        source_output="saldo-negativo-fin-periodo",
        source_period_offset_from_target=-1,
        max_year_delta=0,
    )

    assert selector.required_period_anchors_for_target("1T") == ()


def test_previous_modelo_selector_max_year_delta_zero_admits_same_ejercicio_offset_anchors() -> None:
    selector = _PreviousModeloSelector(
        source_modelo="130",
        source_output="saldo-negativo-fin-periodo",
        source_period_offset_from_target=-1,
        max_year_delta=0,
    )

    assert selector.required_period_anchors_for_target("2T") == ((0, "1T"),)
    assert selector.required_period_anchors_for_target("3T") == ((0, "2T"),)
    assert selector.required_period_anchors_for_target("4T") == ((0, "3T"),)


def test_previous_modelo_selector_max_year_delta_one_admits_one_year_cross_ejercicio_anchor() -> None:
    selector = _PreviousModeloSelector(
        source_modelo="130",
        source_output="saldo-negativo-fin-periodo",
        source_period_offset_from_target=-1,
        max_year_delta=1,
    )

    assert selector.required_period_anchors_for_target("1T") == ((-1, "4T"),)
    assert selector.required_period_anchors_for_target("2T") == ((0, "1T"),)


def test_previous_modelo_selector_max_year_delta_rejects_negative_values() -> None:
    with pytest.raises(ValidationError, match="max_year_delta must be non-negative"):
        _PreviousModeloSelector(
            source_modelo="130",
            source_output="saldo-negativo-fin-periodo",
            source_period_offset_from_target=-1,
            max_year_delta=-1,
        )


def test_previous_filing_requirements_walker_skips_cap_suppressed_binding(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    base_binding = _previous_year_net_income_binding(committed_modelo_130_snapshot)
    capped_binding = base_binding.model_copy(
        update={
            "id": "test-cap-suppressed-binding",
            "selector": {
                "source": "previous_filing",
                "source_modelo": "130",
                "source_output": "saldo-negativo-fin-periodo",
                "source_period_offset_from_target": -1,
                "max_year_delta": 0,
            },
            "aggregation": {"op": "copy"},
        }
    )
    extended_revision = committed_modelo_130_snapshot.revision.model_copy(
        update={"bindings": (*committed_modelo_130_snapshot.revision.bindings, capped_binding)},
    )

    requirements_first_period = previous_filing_observation_requirements(
        extended_revision, filing_year=2026, period="1T"
    )
    assert all(
        "test-cap-suppressed-binding" not in requirement.binding_ids for requirement in requirements_first_period
    )

    requirements_second_period = previous_filing_observation_requirements(
        extended_revision, filing_year=2026, period="2T"
    )
    matching = [
        requirement
        for requirement in requirements_second_period
        if "test-cap-suppressed-binding" in requirement.binding_ids
    ]
    assert len(matching) == 1
    assert matching[0].modelo == "130"
    assert matching[0].filing_year == 2026
    assert matching[0].period == "1T"


def test_previous_filing_resolver_skips_cap_suppressed_binding(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    base_binding = _previous_year_net_income_binding(committed_modelo_130_snapshot)
    capped_binding = base_binding.model_copy(
        update={
            "id": "test-cap-suppressed-binding-resolve",
            "selector": {
                "source": "previous_filing",
                "source_modelo": "130",
                "source_output": "saldo-negativo-fin-periodo",
                "source_period_offset_from_target": -1,
                "max_year_delta": 0,
            },
            "aggregation": {"op": "copy"},
        }
    )
    extended_revision = committed_modelo_130_snapshot.revision.model_copy(
        update={"bindings": (*committed_modelo_130_snapshot.revision.bindings, capped_binding)},
    )

    m100_observation = RegistryModeloObservation(
        modelo="100",
        filing_year=2025,
        period="0A",
        observations=tuple(
            CasillaObservation(casilla_id=cid, value=Decimal("1")) for cid in ("0224", "1479", "1553", "1577")
        ),
    )

    resolved = resolve_previous_filing_binding_values(
        extended_revision, observations=(m100_observation,), filing_year=2026, period="1T"
    )

    assert "test-cap-suppressed-binding-resolve" not in resolved
    assert _PREVIOUS_YEAR_NET_INCOME_BINDING in resolved


def test_registry_formula_runtime_rejects_non_decimal_input(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    with pytest.raises(Exception, match="must be a Decimal"):
        calculate_registry_snapshot(
            committed_modelo_130_snapshot,
            inputs=cast("dict[str, Decimal]", {"01": 100}),
            date_context={"filing_period": date(2026, 3, 31)},
        )


def test_registry_formula_runtime_rejects_unknown_binding_values(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    with pytest.raises(RegistryValidationError, match="unknown registry binding ids"):
        calculate_registry_snapshot(
            committed_modelo_130_snapshot,
            inputs={},
            date_context={"filing_period": date(2026, 3, 31)},
            binding_values={
                _PREVIOUS_YEAR_NET_INCOME_BINDING: Decimal("13000"),
                "unknown-binding": Decimal("1"),
            },
        )


def test_registry_formula_runtime_rejects_unknown_relation_values(
    committed_modelo_180_snapshot: RegistrySnapshot,
) -> None:
    with pytest.raises(RegistryValidationError, match="unknown registry relation ids"):
        calculate_registry_snapshot(
            committed_modelo_180_snapshot,
            inputs={},
            date_context={"filing_period": date(2026, 12, 31)},
            relation_values={
                "modelo-180-rel-115-perceptores-anual": Decimal("4"),
                "modelo-180-rel-115-base-anual": Decimal("550.00"),
                "modelo-180-rel-115-retenciones-anual": Decimal("114.00"),
                "unknown-relation": Decimal("1"),
            },
        )


def test_registry_formula_runtime_rejects_relation_values_inactive_for_snapshot_period(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    snapshot = _modelo_180_snapshot_with_inactive_relation_period(registry_authority)

    with pytest.raises(RegistryValidationError, match="unknown registry relation ids"):
        calculate_registry_snapshot(
            snapshot,
            inputs={},
            date_context={"filing_period": date(2026, 4, 20)},
            relation_values={"modelo-180-rel-115-base-anual": Decimal("1")},
        )


def test_registry_formula_runtime_defaults_filing_period_axis_from_snapshot(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    result = calculate_registry_snapshot(
        committed_modelo_130_snapshot,
        inputs={
            "01": Decimal("100"),
            "02": Decimal("0"),
            "05": Decimal("0"),
            "06": Decimal("0"),
            "08": Decimal("0"),
            "10": Decimal("0"),
            "16": Decimal("0"),
            "18": Decimal("0"),
        },
        date_context={},
        binding_values={
            _PREVIOUS_YEAR_NET_INCOME_BINDING: Decimal("13000"),
            _PREVIOUS_PERIOD_NEGATIVE_RESULT_BINDING: Decimal("0"),
        },
    )

    assert "04" in result.values
    assert "04" in {entry.target for entry in result.entries}


def test_registry_formula_runtime_rejects_missing_non_snapshot_parameter_axis(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    target = committed_modelo_130_snapshot.revision.parameters[0]
    values = tuple(value.model_copy(update={"date_axis": "devengo_date"}) for value in target.values)
    parameters = (
        target.model_copy(update={"values": values}),
        *committed_modelo_130_snapshot.revision.parameters[1:],
    )
    mutated_revision = committed_modelo_130_snapshot.revision.model_copy(update={"parameters": parameters})
    mutated_snapshot = committed_modelo_130_snapshot.model_copy(update={"revision": mutated_revision})

    with pytest.raises(Exception, match="requires date axis 'devengo_date'"):
        calculate_registry_snapshot(
            mutated_snapshot,
            inputs={
                "01": Decimal("100"),
                "02": Decimal("0"),
                "05": Decimal("0"),
                "06": Decimal("0"),
                "08": Decimal("0"),
                "10": Decimal("0"),
                "16": Decimal("0"),
                "18": Decimal("0"),
            },
            date_context={},
            binding_values={
                _PREVIOUS_YEAR_NET_INCOME_BINDING: Decimal("13000"),
                _PREVIOUS_PERIOD_NEGATIVE_RESULT_BINDING: Decimal("0"),
            },
        )


def _previous_year_net_income_binding(snapshot: RegistrySnapshot) -> DataBindingDefinition:
    return next(binding for binding in snapshot.revision.bindings if binding.id == _PREVIOUS_YEAR_NET_INCOME_BINDING)
