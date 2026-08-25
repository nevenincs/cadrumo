"""Tests for filed-state comparison against registry calculations."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from .....core import CasillaId, validated_casilla_id
from .....core.resources import bundled_path
from .._bindings import CasillaObservation, RegistryModeloObservation
from ..errors import RegistryValidationError
from .._filed_state import (
    RegistryFiledStateComparison,
    RegistryFiledStateDrift,
    compare_calculation_to_filed_observation,
)
from .._formula_runtime import RegistryCalculationResult, calculate_registry_snapshot
from .._schema import RegistrySnapshot
from .._snapshot import build_snapshot
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PREVIOUS_YEAR_NET_INCOME_BINDING = "irpf.previous_year_economic_activity_net_income"
_PREVIOUS_PERIOD_NEGATIVE_RESULT_BINDING = "modelo-130-resultados-negativos-anteriores"
_M130_INGRESOS_CASILLA: CasillaId = validated_casilla_id("01", surface="_M130_INGRESOS_CASILLA")
_M130_GASTOS_CASILLA: CasillaId = validated_casilla_id("02", surface="_M130_GASTOS_CASILLA")
_M130_RENDIMIENTO_NETO_CASILLA: CasillaId = validated_casilla_id("03", surface="_M130_RENDIMIENTO_NETO_CASILLA")
_M130_PAGO_FRACCIONADO_CASILLA: CasillaId = validated_casilla_id("04", surface="_M130_PAGO_FRACCIONADO_CASILLA")
_M130_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("06", surface="_M130_RETENCIONES_CASILLA")
_M130_RESULTADO_PARCIAL_CASILLA: CasillaId = validated_casilla_id("07", surface="_M130_RESULTADO_PARCIAL_CASILLA")
_M130_AGRARIAN_VOLUME_CASILLA: CasillaId = validated_casilla_id("08", surface="_M130_AGRARIAN_VOLUME_CASILLA")
_M130_DIFERENCIA_AGRARIA_CASILLA: CasillaId = validated_casilla_id("09", surface="_M130_DIFERENCIA_AGRARIA_CASILLA")
_M130_AGRARIAN_WITHHELD_CASILLA: CasillaId = validated_casilla_id("10", surface="_M130_AGRARIAN_WITHHELD_CASILLA")
_M130_DIFERENCIA_TOTAL_CASILLA: CasillaId = validated_casilla_id("11", surface="_M130_DIFERENCIA_TOTAL_CASILLA")
_M130_RESULTADO_POSITIVO_CASILLA: CasillaId = validated_casilla_id("12", surface="_M130_RESULTADO_POSITIVO_CASILLA")
_M130_MINORACION_CASILLA: CasillaId = validated_casilla_id("13", surface="_M130_MINORACION_CASILLA")
_M130_RESULTADO_PREVIO_CASILLA: CasillaId = validated_casilla_id("14", surface="_M130_RESULTADO_PREVIO_CASILLA")
_M130_HOME_DEDUCTION_CASILLA: CasillaId = validated_casilla_id("16", surface="_M130_HOME_DEDUCTION_CASILLA")
_M130_DIFERENCIA_CASILLA: CasillaId = validated_casilla_id("17", surface="_M130_DIFERENCIA_CASILLA")
_M130_PRIOR_RETURN_CASILLA: CasillaId = validated_casilla_id("18", surface="_M130_PRIOR_RETURN_CASILLA")
_M130_RESULTADO_FINAL_CASILLA: CasillaId = validated_casilla_id("19", surface="_M130_RESULTADO_FINAL_CASILLA")
_MODELO_130_COMPUTED_CASILLA_IDS: tuple[CasillaId, ...] = (
    _M130_RENDIMIENTO_NETO_CASILLA,
    _M130_PAGO_FRACCIONADO_CASILLA,
    _M130_RESULTADO_PARCIAL_CASILLA,
    _M130_DIFERENCIA_AGRARIA_CASILLA,
    _M130_DIFERENCIA_TOTAL_CASILLA,
    _M130_RESULTADO_POSITIVO_CASILLA,
    _M130_MINORACION_CASILLA,
    _M130_RESULTADO_PREVIO_CASILLA,
    _M130_DIFERENCIA_CASILLA,
    _M130_RESULTADO_FINAL_CASILLA,
)


def _modelo_130_snapshot() -> RegistrySnapshot:
    modelo, catalogues = _committed_modelo("130")
    return build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2026,
        period="1T",
    )


def _modelo_130_calculation() -> RegistryCalculationResult:
    return calculate_registry_snapshot(
        _modelo_130_snapshot(),
        inputs={
            _M130_INGRESOS_CASILLA: Decimal("10000"),
            _M130_GASTOS_CASILLA: Decimal("4000"),
            _M130_RETENCIONES_CASILLA: Decimal("100"),
            _M130_AGRARIAN_VOLUME_CASILLA: Decimal("2000"),
            _M130_AGRARIAN_WITHHELD_CASILLA: Decimal("10"),
            _M130_HOME_DEDUCTION_CASILLA: Decimal("0"),
            _M130_PRIOR_RETURN_CASILLA: Decimal("0"),
        },
        date_context={"filing_period": date(2026, 3, 31)},
        binding_values={
            _PREVIOUS_YEAR_NET_INCOME_BINDING: Decimal("13000"),
            _PREVIOUS_PERIOD_NEGATIVE_RESULT_BINDING: Decimal("0"),
        },
    )


def _filed_observation(calculation: RegistryCalculationResult) -> RegistryModeloObservation:
    observations_by_id = {observation.casilla_id: observation for observation in calculation.observations}
    return RegistryModeloObservation(
        modelo="130",
        filing_year=2026,
        period="1T",
        observations=tuple(
            observations_by_id[cid].model_copy(update={"value": calculation.values[cid]})
            for cid in _MODELO_130_COMPUTED_CASILLA_IDS
        ),
    )


def _observation_with_one_cent_delta(observation: CasillaObservation) -> CasillaObservation:
    assert isinstance(observation.value, Decimal)
    return observation.model_copy(update={"value": observation.value + Decimal("0.01")})


def test_filed_state_comparison_satisfies_matching_computed_casilla_ids() -> None:
    calculation = _modelo_130_calculation()

    comparison = compare_calculation_to_filed_observation(
        calculation,
        _filed_observation(calculation),
        required_casilla_ids=_MODELO_130_COMPUTED_CASILLA_IDS,
    )

    assert comparison.status == "satisfied"
    assert comparison.compared_casilla_ids == _MODELO_130_COMPUTED_CASILLA_IDS
    assert comparison.drifts == ()
    assert comparison.missing_filed_casilla_ids == ()


def test_filed_state_comparison_rejects_legacy_casilla_list_keys() -> None:
    with pytest.raises(ValidationError) as raised:
        RegistryFiledStateComparison.model_validate(
            {
                "modelo": "130",
                "revision": "2019-y-siguientes",
                "filing_year": 2026,
                "period": "1T",
                "status": "satisfied",
                "compared_casillas": _MODELO_130_COMPUTED_CASILLA_IDS,
                "missing_local_casillas": (),
                "missing_filed_casillas": (),
            },
        )

    message = str(raised.value)
    assert "compared_casillas" in message
    assert "missing_local_casillas" in message
    assert "missing_filed_casillas" in message


def test_filed_state_drift_rejects_blank_registry_provenance_refs() -> None:
    """Drift rows are operator-facing provenance carriers, not free-text bags."""
    for field_name in ("formula_id", "legal_refs", "source_refs"):
        payload: dict[str, object] = {
            "casilla_id": _M130_RESULTADO_FINAL_CASILLA,
            "local_value": Decimal("1.00"),
            "filed_value": Decimal("2.00"),
            "delta": Decimal("-1.00"),
            "formula_id": "resultado-final",
            "legal_refs": ("ley-35-2006:art-110",),
            "source_refs": ("aeat-dr-130-2026",),
        }
        payload[field_name] = (" ",) if field_name.endswith("_refs") else " "

        with pytest.raises(ValidationError, match=field_name):
            RegistryFiledStateDrift.model_validate(payload)


def test_filed_state_comparison_reports_value_drift() -> None:
    calculation = _modelo_130_calculation()
    # casilla_values is a derived @property; mutate the typed
    # `observations` tuple — the canonical storage — to drift one entry.
    observation = _filed_observation(calculation)
    drifted_observations = tuple(
        _observation_with_one_cent_delta(obs) if obs.casilla_id == _M130_RESULTADO_FINAL_CASILLA else obs
        for obs in observation.observations
    )
    observation = observation.model_copy(update={"observations": drifted_observations})

    comparison = compare_calculation_to_filed_observation(
        calculation,
        observation,
        required_casilla_ids=_MODELO_130_COMPUTED_CASILLA_IDS,
    )

    assert comparison.status == "failed"
    assert len(comparison.drifts) == 1
    assert comparison.drifts[0].casilla_id == _M130_RESULTADO_FINAL_CASILLA
    assert comparison.drifts[0].delta == Decimal("-0.01")


def test_filed_state_comparison_reports_missing_filed_casilla() -> None:
    calculation = _modelo_130_calculation()
    # casilla_values is a derived @property; drop the underlying typed
    # `observations` entry to simulate a missing filed casilla.
    observation = _filed_observation(calculation)
    pruned_observations = tuple(
        obs for obs in observation.observations if obs.casilla_id != _M130_RESULTADO_FINAL_CASILLA
    )
    observation = observation.model_copy(update={"observations": pruned_observations})

    comparison = compare_calculation_to_filed_observation(
        calculation,
        observation,
        required_casilla_ids=_MODELO_130_COMPUTED_CASILLA_IDS,
    )

    assert comparison.status == "failed"
    assert comparison.missing_filed_casilla_ids == (_M130_RESULTADO_FINAL_CASILLA,)
    assert _M130_RESULTADO_FINAL_CASILLA not in comparison.compared_casilla_ids


def test_filed_state_comparison_rejects_modelo_mismatch() -> None:
    calculation = _modelo_130_calculation()
    observation = _filed_observation(calculation).model_copy(update={"modelo": "131"})

    with pytest.raises(RegistryValidationError, match="cannot compare calculation modelo"):
        compare_calculation_to_filed_observation(
            calculation,
            observation,
            required_casilla_ids=_MODELO_130_COMPUTED_CASILLA_IDS,
        )


def test_filed_state_comparison_rejects_empty_required_casilla_ids() -> None:
    """Passing an empty ``required_casilla_ids`` set is meaningless and the
    helper must refuse to silently produce a vacuous-satisfied result."""
    calculation = _modelo_130_calculation()

    with pytest.raises(RegistryValidationError, match="requires at least one casilla"):
        compare_calculation_to_filed_observation(
            calculation,
            _filed_observation(calculation),
            required_casilla_ids=(),
        )


def test_filed_state_comparison_reports_missing_local_casilla() -> None:
    """When a required casilla is absent from ``calculation.values`` but
    present in the observation, it lands in ``missing_local_casilla_ids`` —
    a separate failure axis from ``missing_filed_casilla_ids`` and drift."""
    calculation = _modelo_130_calculation()
    observation = _filed_observation(calculation)
    # `values` is a derived @property over the typed observations envelope;
    # drop casilla "19" by filtering the canonical observations tuple instead.
    pruned_observations = tuple(
        obs for obs in calculation.observations if obs.casilla_id != _M130_RESULTADO_FINAL_CASILLA
    )
    calculation = calculation.model_copy(update={"observations": pruned_observations})

    comparison = compare_calculation_to_filed_observation(
        calculation,
        observation,
        required_casilla_ids=_MODELO_130_COMPUTED_CASILLA_IDS,
    )

    assert comparison.status == "failed"
    assert comparison.missing_local_casilla_ids == (_M130_RESULTADO_FINAL_CASILLA,)
    assert comparison.missing_filed_casilla_ids == ()
    assert _M130_RESULTADO_FINAL_CASILLA not in comparison.compared_casilla_ids
    assert comparison.drifts == ()


def test_filed_state_drift_carries_formula_provenance() -> None:
    """A drifted computed casilla carries ``formula_id``, ``legal_refs``, and
    ``source_refs`` pulled from the typed calculation observation so the
    regulatory grounding for the drift is preserved through the comparison
    boundary and available to CLI / audit surfaces.

    Casilla "19" (resultado final M130) is formula-computed; its
    ``CasillaObservation`` must have non-empty ``legal_refs`` and a
    ``formula_id``. Drifting it by 0.01 forces it into the ``drifts``
    tuple; the test asserts provenance is carried.
    """
    calculation = _modelo_130_calculation()
    observation = _filed_observation(calculation)
    drifted_observations = tuple(
        _observation_with_one_cent_delta(obs) if obs.casilla_id == _M130_RESULTADO_FINAL_CASILLA else obs
        for obs in observation.observations
    )
    observation = observation.model_copy(update={"observations": drifted_observations})

    comparison = compare_calculation_to_filed_observation(
        calculation,
        observation,
        required_casilla_ids=_MODELO_130_COMPUTED_CASILLA_IDS,
    )

    assert comparison.status == "failed"
    assert len(comparison.drifts) == 1
    drift = comparison.drifts[0]
    assert drift.casilla_id == _M130_RESULTADO_FINAL_CASILLA
    assert drift.formula_id is not None, "computed casilla drift must carry formula_id"
    assert len(drift.legal_refs) > 0, "computed casilla drift must carry legal_refs"
    assert len(drift.source_refs) > 0, "computed casilla drift must carry source_refs"


def test_filed_state_drift_carries_input_casilla_provenance() -> None:
    """Input casilla drifts must use the typed observation envelope, not formula entries."""
    calculation = _modelo_130_calculation()
    expected_observation = next(obs for obs in calculation.observations if obs.casilla_id == _M130_INGRESOS_CASILLA)
    assert expected_observation.formula_id is None
    assert expected_observation.legal_refs
    assert expected_observation.source_refs
    observation = RegistryModeloObservation(
        modelo="130",
        filing_year=2026,
        period="1T",
        observations=(
            expected_observation.model_copy(
                update={"value": calculation.values[_M130_INGRESOS_CASILLA] + Decimal("0.01")},
            ),
        ),
    )

    comparison = compare_calculation_to_filed_observation(
        calculation,
        observation,
        required_casilla_ids=(_M130_INGRESOS_CASILLA,),
    )

    assert comparison.status == "failed"
    assert len(comparison.drifts) == 1
    drift = comparison.drifts[0]
    assert drift.casilla_id == _M130_INGRESOS_CASILLA
    assert drift.formula_id is None
    assert drift.legal_refs == expected_observation.legal_refs
    assert drift.source_refs == expected_observation.source_refs


def test_filed_state_comparison_default_tolerance_is_exact() -> None:
    """A caller that omits ``tolerance`` gets the strictest reading, never a looser one.

    The default cannot consult the registry, so the only safe value is the one
    that absorbs nothing — matching :func:`application.modelo.detect_casilla_divergences`'s
    same default. Modelo 130 publishes ``0.01``, so this is the behavioural
    proof that the parameter's absence does NOT fall back to that published
    value; it falls back to exact equality.
    """
    calculation = _modelo_130_calculation()
    observation = _filed_observation(calculation)
    drifted_observations = tuple(
        _observation_with_one_cent_delta(obs) if obs.casilla_id == _M130_RESULTADO_FINAL_CASILLA else obs
        for obs in observation.observations
    )
    observation = observation.model_copy(update={"observations": drifted_observations})

    comparison = compare_calculation_to_filed_observation(
        calculation,
        observation,
        required_casilla_ids=_MODELO_130_COMPUTED_CASILLA_IDS,
    )

    assert comparison.status == "failed"
    assert len(comparison.drifts) == 1
    assert comparison.drifts[0].casilla_id == _M130_RESULTADO_FINAL_CASILLA


def test_filed_state_comparison_absorbs_a_drift_within_an_explicit_tolerance() -> None:
    """The SAME one-cent delta stays silent once the caller passes a tolerance covering it.

    Companion to the default-is-exact test above: without this the suite could
    not distinguish "the tolerance parameter is honoured" from "it is silently
    ignored and every delta is reported regardless of what is passed".
    """
    calculation = _modelo_130_calculation()
    observation = _filed_observation(calculation)
    drifted_observations = tuple(
        _observation_with_one_cent_delta(obs) if obs.casilla_id == _M130_RESULTADO_FINAL_CASILLA else obs
        for obs in observation.observations
    )
    observation = observation.model_copy(update={"observations": drifted_observations})

    comparison = compare_calculation_to_filed_observation(
        calculation,
        observation,
        required_casilla_ids=_MODELO_130_COMPUTED_CASILLA_IDS,
        tolerance=Decimal("0.01"),
    )

    assert comparison.status == "satisfied"
    assert comparison.drifts == ()


def test_filed_state_comparison_tolerance_is_registry_published_and_differs_by_modelo() -> None:
    """The threshold tracks the registry rather than being a constant this module owns.

    Modelo 130 publishes ``0.01``; modelo 303 publishes ``0.00`` (the
    strictest-wins fold across expectations declaring both ``0.00`` and
    ``0.01``). A hardcoded constant cannot be correct for both, so resolving
    two DIFFERENT real bundled snapshots to two different values is the
    property that proves the threshold is read from the registry rather than
    carried in code — mirroring
    ``application/modelo/tests/test_reconcile_tolerance_is_registry_published.py``,
    which pins the same contract for the sibling comparator.
    """
    m130_tolerance = _modelo_130_snapshot().verification_policy().tolerance
    m303_tolerance = _committed_modelo_snapshot("303").verification_policy().tolerance

    assert m130_tolerance == Decimal("0.01")
    assert m303_tolerance == Decimal("0.00")
    assert m130_tolerance != m303_tolerance


def _committed_modelo_snapshot(modelo_id: str) -> RegistrySnapshot:
    modelo, catalogues = _committed_modelo(modelo_id)
    return build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2026,
        period="1T",
    )


def test_filed_state_comparison_reports_composite_missing_and_drift() -> None:
    """Each failure axis must populate independently — one casilla missing
    locally, another missing in the filed observation, and a third with a
    numeric drift, all in the same comparison."""
    calculation = _modelo_130_calculation()
    observation = _filed_observation(calculation)
    pruned_local_observations = tuple(
        obs for obs in calculation.observations if obs.casilla_id != _M130_RENDIMIENTO_NETO_CASILLA
    )
    calculation = calculation.model_copy(update={"observations": pruned_local_observations})
    # casilla_values is a derived @property; mutate the typed
    # `observations` tuple to drop "04" and drift "19".
    mutated_observations = tuple(
        _observation_with_one_cent_delta(obs) if obs.casilla_id == _M130_RESULTADO_FINAL_CASILLA else obs
        for obs in observation.observations
        if obs.casilla_id != _M130_PAGO_FRACCIONADO_CASILLA
    )
    observation = observation.model_copy(update={"observations": mutated_observations})

    comparison = compare_calculation_to_filed_observation(
        calculation,
        observation,
        required_casilla_ids=_MODELO_130_COMPUTED_CASILLA_IDS,
    )

    assert comparison.status == "failed"
    assert comparison.missing_local_casilla_ids == (_M130_RENDIMIENTO_NETO_CASILLA,)
    assert comparison.missing_filed_casilla_ids == (_M130_PAGO_FRACCIONADO_CASILLA,)
    assert len(comparison.drifts) == 1
    assert comparison.drifts[0].casilla_id == _M130_RESULTADO_FINAL_CASILLA
    assert comparison.drifts[0].delta == Decimal("-0.01")
    assert _M130_RENDIMIENTO_NETO_CASILLA not in comparison.compared_casilla_ids
    assert _M130_PAGO_FRACCIONADO_CASILLA not in comparison.compared_casilla_ids
