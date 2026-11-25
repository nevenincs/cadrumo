"""Registry formula runtime seeding from saved formula observations.

An amendment replays a filing by installing the formula observations the filing
recorded (retained seeds) and the operator's authored formula values
(overrides), then reevaluates only the dependency closure of what changed. These
tests pin that channel against a full calculation of the committed Modelo 130.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal

import pytest

from .....core.casilla_id import CasillaId, validated_casilla_id
from ..bindings import CasillaObservation
from ..errors import RegistryValidationError
from ..formula_runtime import RegistryCalculationResult, calculate_registry_snapshot
from ..schema import RegistrySnapshot
from .formula_runtime_support import (
    M130_AGRARIAN_VOLUME_CASILLA,
    M130_AGRARIAN_WITHHELD_CASILLA,
    M130_DIFERENCIA_AGRARIA_CASILLA,
    M130_DIFERENCIA_CASILLA,
    M130_GASTOS_PREVIOS_CASILLA,
    M130_HOME_DEDUCTION_CASILLA,
    M130_INGRESOS_CASILLA,
    M130_MINORACION_CASILLA,
    M130_NORMAL_MODALITY,
    M130_PAGO_FRACCIONADO_CASILLA,
    M130_PRIOR_RETURN_RESULT_CASILLA,
    M130_RESULTADO_FINAL_CASILLA,
    M130_RESULTADO_POSITIVO_CASILLA,
    M130_RESULTADO_PREVIO_CASILLA,
    M130_RETENCIONES_CASILLA,
    PREVIOUS_PERIOD_NEGATIVE_RESULT_BINDING,
    PREVIOUS_YEAR_NET_INCOME_BINDING,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

INGRESOS_CUMULATIVE_BINDING = "modelo-130-actividad-economica-ingresos-cumulative"
M130_RENDIMIENTO_NETO_CASILLA: CasillaId = validated_casilla_id("03")
OVERRIDE_TARGET_INVALID = "errors.calc.formula_override_target_invalid"


def _inputs() -> dict[CasillaId, Decimal]:
    return {
        M130_INGRESOS_CASILLA: Decimal("10000"),
        M130_GASTOS_PREVIOS_CASILLA: Decimal("4000"),
        M130_RETENCIONES_CASILLA: Decimal("100"),
        M130_AGRARIAN_VOLUME_CASILLA: Decimal("2000"),
        M130_AGRARIAN_WITHHELD_CASILLA: Decimal("10"),
        M130_HOME_DEDUCTION_CASILLA: Decimal("0"),
        M130_PRIOR_RETURN_RESULT_CASILLA: Decimal("0"),
    }


def _bindings(previous_year_net_income: Decimal) -> dict[str, Decimal]:
    return {
        PREVIOUS_YEAR_NET_INCOME_BINDING: previous_year_net_income,
        PREVIOUS_PERIOD_NEGATIVE_RESULT_BINDING: Decimal("0"),
    }


def _calculate(
    snapshot: RegistrySnapshot,
    *,
    previous_year_net_income: Decimal = Decimal("13000"),
    formula_overrides: Mapping[CasillaId, CasillaObservation] | None = None,
    retained_formula_observations: Mapping[CasillaId, CasillaObservation] | None = None,
    recalculate_from_casilla_ids: frozenset[CasillaId] = frozenset(),
    recalculate_from_binding_ids: frozenset[str] = frozenset(),
) -> RegistryCalculationResult:
    return calculate_registry_snapshot(
        snapshot,
        inputs=_inputs(),
        date_context={"filing_period": date(snapshot.filing_year, 3, 31)},
        enum_binding_values=M130_NORMAL_MODALITY,
        binding_values=_bindings(previous_year_net_income),
        formula_overrides=formula_overrides,
        retained_formula_observations=retained_formula_observations,
        recalculate_from_casilla_ids=recalculate_from_casilla_ids,
        recalculate_from_binding_ids=recalculate_from_binding_ids,
    )


def _calculate_with_saved_channel(
    snapshot: RegistrySnapshot,
    channel: str,
    saved: Mapping[CasillaId, CasillaObservation],
) -> RegistryCalculationResult:
    if channel == "formula_overrides":
        return _calculate(snapshot, formula_overrides=saved)
    return _calculate(snapshot, retained_formula_observations=saved)


def _formula_observations(result: RegistryCalculationResult) -> dict[CasillaId, CasillaObservation]:
    return {
        observation.casilla_id: observation for observation in result.observations if observation.formula_id is not None
    }


def _observations(result: RegistryCalculationResult) -> Mapping[CasillaId, CasillaObservation]:
    return {observation.casilla_id: observation for observation in result.observations}


def test_formula_override_feeds_dependents_and_keeps_its_observation(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    baseline = _calculate(committed_modelo_130_snapshot)
    authored = _formula_observations(baseline)[M130_RESULTADO_POSITIVO_CASILLA].model_copy(
        update={"value": Decimal("777")}
    )

    result = _calculate(
        committed_modelo_130_snapshot,
        formula_overrides={M130_RESULTADO_POSITIVO_CASILLA: authored},
    )

    observations = _observations(result)
    assert observations[M130_RESULTADO_POSITIVO_CASILLA] == authored
    minoracion = baseline.values[M130_MINORACION_CASILLA]
    assert result.values[M130_RESULTADO_PREVIO_CASILLA] == Decimal("777") - minoracion
    assert result.values[M130_RESULTADO_FINAL_CASILLA] != baseline.values[M130_RESULTADO_FINAL_CASILLA]
    assert result.values[M130_DIFERENCIA_AGRARIA_CASILLA] == baseline.values[M130_DIFERENCIA_AGRARIA_CASILLA]


def test_retained_observations_without_a_change_set_are_recalculated_in_full(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    baseline = _calculate(committed_modelo_130_snapshot)
    stale = {
        target: observation.model_copy(update={"value": Decimal("-1")})
        for target, observation in _formula_observations(baseline).items()
    }

    result = _calculate(committed_modelo_130_snapshot, retained_formula_observations=stale)

    assert result.observations == baseline.observations


def test_amendment_reevaluates_only_the_binding_closure_and_unrecorded_formulas(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    baseline = _calculate(committed_modelo_130_snapshot)
    changed = _calculate(committed_modelo_130_snapshot, previous_year_net_income=Decimal("5000"))
    retained = _formula_observations(baseline)
    # A retained figure outside the change's reach keeps its recorded value,
    # proving that the replay does not reevaluate it.
    retained[M130_PAGO_FRACCIONADO_CASILLA] = retained[M130_PAGO_FRACCIONADO_CASILLA].model_copy(
        update={"value": Decimal("4321")}
    )
    # A formula the filing never recorded is evaluated like a first calculation.
    del retained[M130_DIFERENCIA_AGRARIA_CASILLA]

    result = _calculate(
        committed_modelo_130_snapshot,
        previous_year_net_income=Decimal("5000"),
        retained_formula_observations=retained,
        recalculate_from_binding_ids=frozenset({PREVIOUS_YEAR_NET_INCOME_BINDING}),
    )

    observations = _observations(result)
    assert observations[M130_PAGO_FRACCIONADO_CASILLA] == retained[M130_PAGO_FRACCIONADO_CASILLA]
    assert observations[M130_DIFERENCIA_AGRARIA_CASILLA] == _observations(changed)[M130_DIFERENCIA_AGRARIA_CASILLA]
    for target in (M130_MINORACION_CASILLA, M130_RESULTADO_PREVIO_CASILLA, M130_DIFERENCIA_CASILLA):
        assert observations[target] == _observations(changed)[target]
    assert result.values[M130_MINORACION_CASILLA] != baseline.values[M130_MINORACION_CASILLA]


def test_amendment_override_is_not_reevaluated_inside_the_closure(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    baseline = _calculate(committed_modelo_130_snapshot)
    authored = _formula_observations(baseline)[M130_RESULTADO_PREVIO_CASILLA].model_copy(
        update={"value": Decimal("55")}
    )
    retained = {
        target: observation
        for target, observation in _formula_observations(baseline).items()
        if target != M130_RESULTADO_PREVIO_CASILLA
    }

    result = _calculate(
        committed_modelo_130_snapshot,
        previous_year_net_income=Decimal("5000"),
        formula_overrides={M130_RESULTADO_PREVIO_CASILLA: authored},
        retained_formula_observations=retained,
        recalculate_from_binding_ids=frozenset({PREVIOUS_YEAR_NET_INCOME_BINDING}),
    )

    full = _calculate(
        committed_modelo_130_snapshot,
        previous_year_net_income=Decimal("5000"),
        formula_overrides={M130_RESULTADO_PREVIO_CASILLA: authored},
    )
    assert _observations(result)[M130_RESULTADO_PREVIO_CASILLA] == authored
    for target in (M130_MINORACION_CASILLA, M130_DIFERENCIA_CASILLA, M130_RESULTADO_FINAL_CASILLA):
        assert _observations(result)[target] == _observations(full)[target]


@pytest.mark.parametrize("channel", ["formula_overrides", "retained_formula_observations"])
def test_saved_observation_for_a_non_formula_casilla_is_refused(
    committed_modelo_130_snapshot: RegistrySnapshot,
    channel: str,
) -> None:
    baseline = _calculate(committed_modelo_130_snapshot)
    observation = _observations(baseline)[M130_INGRESOS_CASILLA]

    with pytest.raises(RegistryValidationError) as refused:
        _calculate_with_saved_channel(committed_modelo_130_snapshot, channel, {M130_INGRESOS_CASILLA: observation})

    assert refused.value.translated_message == OVERRIDE_TARGET_INVALID
    assert refused.value.context == {"casilla_ids": M130_INGRESOS_CASILLA}


@pytest.mark.parametrize("channel", ["formula_overrides", "retained_formula_observations"])
def test_saved_observation_keyed_under_another_casilla_is_refused(
    committed_modelo_130_snapshot: RegistrySnapshot,
    channel: str,
) -> None:
    observation = _formula_observations(_calculate(committed_modelo_130_snapshot))[M130_RESULTADO_FINAL_CASILLA]

    with pytest.raises(RegistryValidationError, match="does not match target") as refused:
        _calculate_with_saved_channel(
            committed_modelo_130_snapshot, channel, {M130_RESULTADO_PREVIO_CASILLA: observation}
        )

    assert refused.value.translated_message == OVERRIDE_TARGET_INVALID
    assert refused.value.context == {"casilla_ids": M130_RESULTADO_PREVIO_CASILLA}


def test_formula_override_with_a_text_value_is_refused(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    observation = _formula_observations(_calculate(committed_modelo_130_snapshot))[M130_RESULTADO_FINAL_CASILLA]
    text = observation.model_copy(update={"value": "texto", "value_kind": "text"})

    with pytest.raises(RegistryValidationError, match="must carry a Decimal value") as refused:
        _calculate(committed_modelo_130_snapshot, formula_overrides={M130_RESULTADO_FINAL_CASILLA: text})

    assert refused.value.translated_message == OVERRIDE_TARGET_INVALID
    assert refused.value.context == {"casilla_id": M130_RESULTADO_FINAL_CASILLA}


def test_retained_text_observation_outside_the_closure_is_not_materialised(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    baseline = _calculate(committed_modelo_130_snapshot)
    retained = _formula_observations(baseline)
    retained[M130_PAGO_FRACCIONADO_CASILLA] = retained[M130_PAGO_FRACCIONADO_CASILLA].model_copy(
        update={"value": "texto", "value_kind": "text"}
    )

    result = _calculate(
        committed_modelo_130_snapshot,
        retained_formula_observations=retained,
        recalculate_from_casilla_ids=frozenset({M130_HOME_DEDUCTION_CASILLA}),
    )

    # A non-Decimal retained figure seeds nothing, yet it counts as recorded, so a
    # replay that does not reach it leaves it without an observation.
    observations = _observations(result)
    assert M130_PAGO_FRACCIONADO_CASILLA not in observations
    assert observations[M130_RESULTADO_FINAL_CASILLA] == _observations(baseline)[M130_RESULTADO_FINAL_CASILLA]


def test_amendment_reaching_a_formula_through_an_unrecorded_binding_names_the_binding(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    retained = _formula_observations(_calculate(committed_modelo_130_snapshot))

    with pytest.raises(RegistryValidationError) as refused:
        calculate_registry_snapshot(
            committed_modelo_130_snapshot,
            inputs={M130_HOME_DEDUCTION_CASILLA: Decimal("0"), M130_PRIOR_RETURN_RESULT_CASILLA: Decimal("0")},
            date_context={"filing_period": date(committed_modelo_130_snapshot.filing_year, 3, 31)},
            enum_binding_values=M130_NORMAL_MODALITY,
            binding_values={PREVIOUS_PERIOD_NEGATIVE_RESULT_BINDING: Decimal("0")},
            unresolved_binding_ids=(PREVIOUS_YEAR_NET_INCOME_BINDING, INGRESOS_CUMULATIVE_BINDING),
            retained_formula_observations=retained,
            recalculate_from_binding_ids=frozenset({PREVIOUS_YEAR_NET_INCOME_BINDING}),
        )

    assert refused.value.translated_message == "errors.calc.formula_recalculation_binding_unrecorded"
    context = refused.value.context
    assert context is not None
    assert context["binding_ids"] == PREVIOUS_YEAR_NET_INCOME_BINDING
    assert M130_MINORACION_CASILLA in str(context["casilla_ids"]).split(", ")


def test_unrecorded_binding_read_through_a_bound_casilla_is_named(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    retained = _formula_observations(_calculate(committed_modelo_130_snapshot))
    inputs = {key: value for key, value in _inputs().items() if key != M130_INGRESOS_CASILLA}

    with pytest.raises(RegistryValidationError) as refused:
        calculate_registry_snapshot(
            committed_modelo_130_snapshot,
            inputs=inputs,
            date_context={"filing_period": date(committed_modelo_130_snapshot.filing_year, 3, 31)},
            enum_binding_values=M130_NORMAL_MODALITY,
            binding_values=_bindings(Decimal("13000")),
            unresolved_binding_ids=(INGRESOS_CUMULATIVE_BINDING,),
            retained_formula_observations=retained,
            recalculate_from_casilla_ids=frozenset({M130_INGRESOS_CASILLA}),
        )

    assert refused.value.translated_message == "errors.calc.formula_recalculation_binding_unrecorded"
    context = refused.value.context
    assert context is not None
    assert context["binding_ids"] == INGRESOS_CUMULATIVE_BINDING
    assert M130_RENDIMIENTO_NETO_CASILLA in str(context["casilla_ids"]).split(", ")
