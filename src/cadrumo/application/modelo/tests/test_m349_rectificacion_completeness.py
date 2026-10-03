"""Modelo 349 rectificación casillas are answered only by stated zero totals.

Without rectificación rows, the per-row rectificación casillas are owed nothing
only when the declarant states zero rectificaciones in both summary totals. An
unstated total cannot prove that, so the casillas stay demanded.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....core.casilla_id import CasillaId
from ....core.modelo import Modelo
from ....core.period import Period
from ....domain.calculations.registry.bindings import resolve_available_bound_inputs_by_casilla_id
from ....domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.schema_surfaces import CasillaDefinition
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from .._calculation_helpers import build_typed_observations
from .._calculation_modelo_adjustments import drop_row_field_template_outputs
from ..verification_actions import (
    M349_IMPORTE_RECTIFICACIONES_CASILLA,
    M349_NUMERO_RECTIFICACIONES_CASILLA,
    _detail_row_template_casilla_is_satisfied,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CLOCK = datetime(2026, 6, 29, 12, 0, tzinfo=UTC)
_BUCKET_ID = "5f0e7a52-2a3c-4f4e-9d1e-6a2b9c0f8e11"
_TOTALS = (M349_NUMERO_RECTIFICACIONES_CASILLA, M349_IMPORTE_RECTIFICACIONES_CASILLA)


def _snapshot_and_work_unit() -> tuple[RegistrySnapshot, WorkUnit]:
    snapshot = published_snapshot(Modelo("349").value, filing_year=2026, period="1T")
    period = Period.from_year_and_code(2026, "1T")
    work_unit = WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo="349",
            filing_year=2026,
            period=period,
            revision_id=snapshot.revision.id,
        ),
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode("349"),
        filing_year=2026,
        period=period,
        revision_id=snapshot.revision.id,
        name="349-2026-1T",
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )
    return snapshot, work_unit


def _revision_without_rows(
    snapshot: RegistrySnapshot,
    work_unit: WorkUnit,
    *,
    omitted: tuple[CasillaId, ...],
) -> CalculationRevision:
    binding_values = {
        "iva-349-declarante-numero-operadores": Decimal("0"),
        "iva-349-declarante-importe-operaciones": Decimal("0"),
        "iva-349-declarante-numero-rectificaciones": Decimal("0"),
        "iva-349-declarante-importe-rectificaciones": Decimal("0"),
    }
    inputs = resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values)
    engine_result = calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        date_context={"filing_period": work_unit.period.end_date},
        binding_values=binding_values,
    )
    casilla_values, observations = drop_row_field_template_outputs(
        revision=snapshot.revision,
        casilla_values=dict(engine_result.values),
        observations=build_typed_observations(engine_result=engine_result, snapshot=snapshot),
    )
    casilla_values = {casilla_id: value for casilla_id, value in casilla_values.items() if casilla_id not in omitted}
    observations = tuple(observation for observation in observations if observation.casilla_id not in omitted)
    input_values = {casilla_id: str(value) for casilla_id, value in inputs.items()}
    binding_overrides = {binding_id: str(value) for binding_id, value in binding_values.items()}
    return CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id=work_unit.work_unit_id,
            input_values_by_casilla_id=input_values,
            binding_overrides=binding_overrides,
            casilla_values=casilla_values,
            filing_instance_evidence=None,
            source_provenance=(),
        ),
        work_unit_id=work_unit.work_unit_id,
        registry_snapshot_ref=snapshot.snapshot_ref,
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id=input_values,
        binding_overrides=binding_overrides,
        casilla_values=casilla_values,
        observations=observations,
        created_at=_CLOCK,
        updated_at=_CLOCK,
        filing_instance_evidence=None,
        source_provenance=(),
    )


def _rectificacion_casilla(snapshot: RegistrySnapshot) -> CasillaDefinition:
    candidates = [casilla for casilla in snapshot.revision.casillas if casilla.section[:1] == ("rectificacion",)]
    assert candidates, "the published Modelo 349 revision declares no rectificacion-section casilla"
    return candidates[0]


def test_stated_zero_totals_answer_the_rectificacion_casilla() -> None:
    snapshot, work_unit = _snapshot_and_work_unit()
    target = _revision_without_rows(snapshot, work_unit, omitted=())
    assert all(target.casilla_values[total] == Decimal("0") for total in _TOTALS)

    assert _detail_row_template_casilla_is_satisfied(
        work_unit=work_unit,
        target=target,
        casilla=_rectificacion_casilla(snapshot),
        revision=snapshot.revision,
    )


@pytest.mark.parametrize("omitted", [(total,) for total in _TOTALS] + [_TOTALS])
def test_an_unstated_total_leaves_the_rectificacion_casilla_demanded(omitted: tuple[CasillaId, ...]) -> None:
    snapshot, work_unit = _snapshot_and_work_unit()
    target = _revision_without_rows(snapshot, work_unit, omitted=omitted)
    assert all(total not in target.casilla_values for total in omitted)

    assert not _detail_row_template_casilla_is_satisfied(
        work_unit=work_unit,
        target=target,
        casilla=_rectificacion_casilla(snapshot),
        revision=snapshot.revision,
    )
