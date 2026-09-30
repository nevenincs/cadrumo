"""A calculation records exactly the operator's caller tier, never a source value.

Driven over real encrypted storage through the production calculation boundary.
The revision's merged input map carries values the sources produced; the
operator layer must carry only what the caller supplied, so a later replay can
never promote a ledger or profile value into an operator override.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ...application.modelo.calculation_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ...application.modelo.caller_context import caller_context_calculation_inputs, caller_context_of
from ...core.authority_grade import RegistryAuthorityGrade
from ...core.casilla_id import validated_casilla_id
from ...domain.modelos.calculation_revision_operator_layer import CalculationOperatorLayer
from .modelo_operator_work_storage import SEEDED_AT, seeded_operator_work

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_C06 = validated_casilla_id("06")


@pytest.mark.timeout(120)
def test_an_operator_calculation_records_only_its_caller_tier(tmp_path: Path) -> None:
    with seeded_operator_work(tmp_path) as work:
        empty = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work.work_unit_id, ports=work.ports, record_operator_layer=True, clock=SEEDED_AT
        ).revision
        typed = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work.work_unit_id,
            ports=work.ports,
            casilla_inputs={_C06: Decimal("100.00")},
            record_operator_layer=True,
            clock=SEEDED_AT,
        ).revision

    # The merged replay map holds source-produced entries the operator never typed.
    assert empty.input_values_by_casilla_id
    assert empty.operator_layer == CalculationOperatorLayer()
    assert typed.operator_layer == CalculationOperatorLayer(decimal_casilla_inputs={_C06: "100"})
    assert caller_context_of(typed).operator_layer == typed.operator_layer


@pytest.mark.timeout(120)
def test_a_calculation_that_does_not_record_the_layer_keeps_its_historical_id(tmp_path: Path) -> None:
    with seeded_operator_work(tmp_path) as work:
        unrecorded = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work.work_unit_id, ports=work.ports, clock=SEEDED_AT
        ).revision
        recorded = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work.work_unit_id, ports=work.ports, record_operator_layer=True, clock=SEEDED_AT
        ).revision

    assert unrecorded.operator_layer is None
    assert not caller_context_of(unrecorded).operator_layer_known
    assert recorded.operator_layer is not None
    assert recorded.calculation_revision_id != unrecorded.calculation_revision_id
    assert recorded.casilla_values == unrecorded.casilla_values


@pytest.mark.timeout(120)
def test_replaying_a_caller_context_reproduces_the_same_revision(tmp_path: Path) -> None:
    """The projected channels feed the engine exactly what the operator entered, binding overrides included."""
    carry = "modelo-130-pagos-fraccionados-anteriores"
    with seeded_operator_work(tmp_path) as work:
        first = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work.work_unit_id,
            ports=work.ports,
            casilla_inputs={_C06: Decimal("100.00")},
            binding_values={carry: Decimal("12.50")},
            record_operator_layer=True,
            clock=SEEDED_AT,
        ).revision
        snapshot = work.operation.snapshot(
            "130",
            filing_year=work.work_unit.filing_year,
            period=work.work_unit.period.registry_token,
            grade=RegistryAuthorityGrade.CALCULATION,
        )
        replay = caller_context_calculation_inputs(caller_context_of(first), revision=snapshot.revision)
        second = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work.work_unit_id,
            ports=work.ports,
            casilla_inputs=replay.casilla_inputs,
            text_casilla_inputs=replay.text_casilla_inputs,
            cleared_casilla_ids=replay.cleared_casilla_ids,
            binding_values=replay.binding_values,
            enum_binding_values=replay.enum_binding_values,
            detail_rows=replay.detail_rows,
            filing_instance_evidence=replay.filing_instance_evidence,
            m210_official_tipo_renta_code=replay.m210_official_tipo_renta_code,
            m210_gross_income_source_mode=replay.m210_gross_income_source_mode,
            borrador_snapshot_id=replay.borrador_snapshot_id,
            record_operator_layer=True,
            clock=SEEDED_AT,
        ).revision

    assert first.operator_layer == CalculationOperatorLayer(
        decimal_casilla_inputs={_C06: "100"}, binding_overrides={carry: "12.5"}
    )
    assert second.calculation_revision_id == first.calculation_revision_id
