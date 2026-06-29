"""IVA compensation relation-prefill binding tests."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....domain.calculations.registry import (
    RegistryModeloObservation,
    RegistryValidationError,
    materialize_relation_binding_values,
)
from ....tests.registry_observations import registry_grounded_modelo_observation, registry_grounded_observations
from ....tests.secure_sql import isolated_runtime_profile
from .._observations_repository import CalculationObservationRepository
from .._relation_prefill import resolve_relations_from_local_store
from ._iva_compensation_history_support import (
    _BOX_97_BINDING,
    _BOX_662_BINDING,
    _M303_COMPENSACION_APLICADA_CASILLA,
    _M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA,
    _M303_CUOTA_DEVENGADA_TOTAL_CASILLA,
    _M303_DISPONIBLE_CASILLA,
    _M303_GENERADA_CASILLA,
    _M303_PRINTED_COMPENSATION_REFERENCE_CASILLA,
    _M303_RESULTADO_REGIMEN_GENERAL_CASILLA,
    _modelo_390_2026_snapshot,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_modelo_390_carry_boxes_resolve_through_fifo_partition_with_carried_pending(tmp_path: Path) -> None:
    """End-to-end: the M390 box-97 / box-662 BINDING values come from the FIFO partition.

    Files four 303 quarters with a real carried-pending chain (1T credit carried,
    2T applies part of it, 4T generates more) as observations, then resolves the
    M390 relations through the production relation resolver and materialises the
    binding slots. The two carry-box bindings must carry the FIFO partition
    (box 97 = 120, box 662 = 0), NOT the per-period relation sums (50 / 100),
    proving the wiring overrides the double-counting per-period path.
    """
    quarter_chain = [
        ("1T", Decimal("100.00"), Decimal("0.00"), Decimal("100.00")),
        ("2T", Decimal("0.00"), Decimal("30.00"), Decimal("70.00")),
        ("3T", Decimal("0.00"), Decimal("0.00"), Decimal("70.00")),
        ("4T", Decimal("50.00"), Decimal("0.00"), Decimal("120.00")),
    ]
    from .._relation_prefill import _fifo_compensation_carry_binding_values, _gather_observations_for_snapshot

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="m390-fifo-carry"):
        observation_repo = CalculationObservationRepository()
        for period, generada, aplicada, disponible in quarter_chain:
            observation_repo.save_observation(
                registry_grounded_modelo_observation(
                    modelo="303",
                    filing_year=2026,
                    period=period,
                    casilla_values={
                        _M303_GENERADA_CASILLA: generada,
                        _M303_COMPENSACION_APLICADA_CASILLA: aplicada,
                        _M303_DISPONIBLE_CASILLA: disponible,
                    },
                ),
                source_kind="app_filing",
                captured_at=datetime(2027, 1, 30, 12, 0, tzinfo=UTC),
            )

        snapshot = _modelo_390_2026_snapshot()
        relation_vals = resolve_relations_from_local_store(
            snapshot,
            repository=observation_repo,
            captured_at=datetime(2027, 1, 30, 12, 0, tzinfo=UTC),
        )
        relation_values_map = {rv.relation: rv.value for rv in relation_vals.values if rv.value is not None}
        resolved = materialize_relation_binding_values(snapshot.revision, relation_values_map, period="0A")
        for binding_id, value in _fifo_compensation_carry_binding_values(
            snapshot,
            _gather_observations_for_snapshot(snapshot, repository=observation_repo),
        ).items():
            if binding_id in resolved:
                resolved[binding_id] = value

    _4t_disponible = quarter_chain[-1][3]
    assert resolved[_BOX_97_BINDING] == _4t_disponible
    assert resolved[_BOX_662_BINDING] == Decimal("0.00")
    assert relation_values_map["modelo-390-rel-303-compensacion-ultimo-periodo"] == quarter_chain[-1][1]
    assert relation_values_map["modelo-390-rel-303-compensacion-generada-ejercicio-no-97"] == quarter_chain[0][1]
    assert resolved[_BOX_97_BINDING] + resolved[_BOX_662_BINDING] == _4t_disponible


def test_modelo_390_compensation_bindings_resolve_from_secure_iva_history(tmp_path: Path) -> None:
    """M390←M303 bindings are now ``relation_prefill``; resolve via the relation path.

    The five M390←M303 fold bindings migrated from ``previous_filing`` to
    ``relation_prefill`` backed by ``cross_model_output`` relations.
    The compensación bindings (ultimo-periodo + generada-ejercicio-no-97) read
    ``iva.compensacion-generada-periodo`` from M303 casilla observations — not
    from the IVA compensation history repository. This verifies the relation
    resolver resolves all five bindings from real M303 observations.
    """
    quarter_data = [
        ("1T", Decimal("100.00"), Decimal("40.00"), Decimal("60.00"), Decimal("20.00")),
        ("2T", Decimal("80.00"), Decimal("30.00"), Decimal("50.00"), Decimal("10.00")),
        ("3T", Decimal("120.00"), Decimal("50.00"), Decimal("70.00"), Decimal("20.00")),
        ("4T", Decimal("90.00"), Decimal("60.00"), Decimal("30.00"), Decimal("100.00")),
    ]
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="m390-compensation-history"):
        observation_repo = CalculationObservationRepository()
        for period, devengada, deducible, regimen_general, compensacion in quarter_data:
            observation_repo.save_observation(
                registry_grounded_modelo_observation(
                    modelo="303",
                    filing_year=2026,
                    period=period,
                    casilla_values={
                        _M303_CUOTA_DEVENGADA_TOTAL_CASILLA: devengada,
                        _M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA: deducible,
                        _M303_RESULTADO_REGIMEN_GENERAL_CASILLA: regimen_general,
                        _M303_GENERADA_CASILLA: compensacion,
                    },
                ),
                source_kind="app_filing",
                captured_at=datetime(2027, 1, 30, 12, 0, tzinfo=UTC),
            )

        snapshot = _modelo_390_2026_snapshot()
        relation_vals = resolve_relations_from_local_store(
            snapshot,
            repository=observation_repo,
            captured_at=datetime(2027, 1, 30, 12, 0, tzinfo=UTC),
        )

    relation_values_map = {rv.relation: rv.value for rv in relation_vals.values if rv.value is not None}
    resolved = materialize_relation_binding_values(snapshot.revision, relation_values_map, period="0A")

    assert resolved["modelo-390-prev-303-cuota-devengada-total"] == Decimal("390.00")
    assert resolved["modelo-390-prev-303-cuota-deducible-total"] == Decimal("180.00")
    assert resolved["modelo-390-prev-303-resultado-regimen-general"] == Decimal("210.00")
    assert resolved["modelo-390-prev-303-compensacion-generada-ejercicio-no-97"] == Decimal("50.00")
    assert resolved["modelo-390-prev-303-compensacion-ultimo-periodo"] == Decimal("100.00")
    resolved_rels = {rv.relation for rv in relation_vals.values if rv.value is not None}
    assert resolved_rels >= {
        "modelo-390-rel-303-cuota-devengada-total",
        "modelo-390-rel-303-cuota-deducible-total",
        "modelo-390-rel-303-resultado-regimen-general",
        "modelo-390-rel-303-compensacion-ultimo-periodo",
        "modelo-390-rel-303-compensacion-generada-ejercicio-no-97",
    }
    assert all(rv.provenance == "local_filing" for rv in relation_vals.values if rv.value is not None)


def test_relation_prefill_fifo_state_refuses_printed_number_compensation_references() -> None:
    from .._relation_prefill import _fifo_compensation_carry_binding_values

    snapshot = _modelo_390_2026_snapshot()
    generated_observation = registry_grounded_observations(
        modelo="303",
        filing_year=2026,
        period="4T",
        casilla_values={_M303_GENERADA_CASILLA: Decimal("50.00")},
    )[0]
    observation = RegistryModeloObservation(
        modelo="303",
        filing_year=2026,
        period="4T",
        observations=(
            generated_observation,
            generated_observation.model_copy(update={"casilla_id": _M303_PRINTED_COMPENSATION_REFERENCE_CASILLA}),
        ),
    )

    with pytest.raises(RegistryValidationError, match=r"canonical casilla\.id"):
        _fifo_compensation_carry_binding_values(snapshot, (observation,))
