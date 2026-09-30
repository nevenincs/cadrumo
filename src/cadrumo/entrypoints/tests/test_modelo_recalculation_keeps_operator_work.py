"""The workspace Calculate action recalculates without discarding the operator's work.

Driven over real encrypted storage through the production calculate executor.
Before the caller context was replayed, pressing Calculate re-derived the
declaration from its sources alone and silently dropped every manual value,
clear and override, and a Modelo 303 recalculation refused for want of filing
evidence the head already recorded.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ...application.modelo.calculation_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ...application.modelo.edit_models import (
    ModeloEditScalarAddressV1,
    ModeloEditScalarIntentKind,
    ModeloScalarEditIntentV1,
)
from ...core.casilla_id import CasillaId, validated_casilla_id
from ...domain.filing.schema import ModeloScalar
from ...domain.modelos.calculation_revision_operator_layer import CalculationOperatorLayer
from .modelo_operator_work_storage import SEEDED_AT, seeded_operator_work

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_C06 = validated_casilla_id("06")
_C08 = validated_casilla_id("08")


def _intent(
    casilla_id: CasillaId, kind: ModeloEditScalarIntentKind, value: ModeloScalar = None
) -> ModeloScalarEditIntentV1:
    return ModeloScalarEditIntentV1(address=ModeloEditScalarAddressV1(casilla_id=casilla_id), kind=kind, value=value)


@pytest.mark.timeout(180)
def test_recalculating_keeps_manual_values_and_clears(tmp_path: Path) -> None:
    with seeded_operator_work(tmp_path) as work:
        applied = work.apply(
            scalar=(
                _intent(_C06, ModeloEditScalarIntentKind.SET_TYPED_VALUE, "100"),
                _intent(_C08, ModeloEditScalarIntentKind.CLEAR_DECLARED_VALUE),
            )
        )
        assert applied.refusal is None
        edited = work.require_head()

        recalculated = work.recalculate()

    assert recalculated.operator_layer == CalculationOperatorLayer(decimal_casilla_inputs={_C06: "100"})
    assert recalculated.cleared_casilla_ids == (_C08,)
    assert recalculated.casilla_values[_C06] == Decimal("100")
    assert recalculated.calculation_revision_id == edited.calculation_revision_id


@pytest.mark.timeout(180)
def test_recalculating_a_head_with_an_unknown_layer_keeps_it_unknown(tmp_path: Path) -> None:
    """A head stored before operator layers replays no values and does not claim a known-empty layer."""
    with seeded_operator_work(tmp_path) as work:
        legacy = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work.work_unit_id, ports=work.ports, clock=SEEDED_AT
        ).revision
        assert legacy.operator_layer is None

        recalculated = work.recalculate()

    assert recalculated.operator_layer is None


@pytest.mark.timeout(240)
def test_recalculating_modelo_303_replays_its_recorded_filing_evidence(tmp_path: Path) -> None:
    with seeded_operator_work(tmp_path, modelo="303") as work:
        first = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work.work_unit_id,
            ports=work.ports,
            filing_instance_evidence=work.m303_filing_evidence(),
            record_operator_layer=True,
            clock=SEEDED_AT,
        ).revision

        recalculated = work.recalculate()

    assert recalculated.filing_instance_evidence == first.filing_instance_evidence
    assert recalculated.operator_layer == CalculationOperatorLayer()
