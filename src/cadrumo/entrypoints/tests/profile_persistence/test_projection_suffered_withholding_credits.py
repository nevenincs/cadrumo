"""The Modelo 100 projection reads the suffered-withholding credits from their payer evidence.

Each credit box takes the sum of the recorded payer certificates of its class, a
proven zero when the profile's income categories exclude the class, and no
value when the class is declared but nothing was recorded. A credit with no
value is reported unresolved, and so are the totals computed from it: total
pagos a cuenta (0609) and cuota diferencial (0610) are never shown as numbers.

The expected figures follow the registry formulas independently: 0609 is the
sum of the pagos a cuenta boxes, here the trabajo credit plus the Modelo 130
instalment carried to 0604, and 0610 is the resulting tax 0595 minus 0609.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.application.modelo.projection import ModeloProjectServiceResult
from cadrumo.application.modelo.projection_unresolved import UNRESOLVED_OPERAND_REASON
from cadrumo.core.retencion_soportada import RetencionSoportadaClase
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.modelos.calculation_revision_sources import CalculationNoteSentence
from cadrumo.domain.user_profile.values import UserProfileFact

from .projection_m130_seeding_support import ACTIVITY_ONLY, M130_Q1_RESULTADO, PayerRecord, run_projection

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_ACTIVITY_AND_WORK = "actividad_economica,trabajo"
# Advertising services (IAE group 844) is an activity and not an urban rental, so no rental-activity
# withholding is asked for beside the activity credit.
_NOT_A_RENTAL = (UserProfileFact(path="activities.iae_epigraph", value="844"),)
_TRABAJO_BINDING = "renta-retencion-soportada-trabajo"


def _values(result: ModeloProjectServiceResult) -> dict[str, Decimal]:
    return {row.casilla_id: row.value for row in result.casilla_observations}


def test_a_declared_work_class_without_payer_records_is_unresolved_and_so_are_its_totals(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    result = run_projection(tmp_path, operation, income_categories=_ACTIVITY_AND_WORK, profile_facts=_NOT_A_RENTAL)

    (unresolved,) = result.unresolved_bindings
    assert unresolved.binding_id == _TRABAJO_BINDING
    assert unresolved.casilla_id == "0596"
    assert unresolved.reason == "unresolved_binding"
    assert unresolved.note is CalculationNoteSentence.RETENCION_SOPORTADA_EVIDENCE_REQUIRED
    unresolved_boxes = {row.casilla_id: row for row in result.unresolved_casillas}
    assert {"0609", "0610"} <= set(unresolved_boxes)
    assert unresolved_boxes["0609"].reason == UNRESOLVED_OPERAND_REASON
    values = _values(result)
    assert not {"0596", "0609", "0610"} & set(values)
    # The headline result stops before any credit, so it is still computed.
    assert values["0595"] == result.m100_projection.cuota_resultante
    assert result.is_extrapolated


def test_two_payer_records_sum_into_the_work_credit_and_total_pagos_a_cuenta(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    result = run_projection(
        tmp_path,
        operation,
        profile_facts=_NOT_A_RENTAL,
        income_categories=_ACTIVITY_AND_WORK,
        payer_records=(
            PayerRecord("B00010165", RetencionSoportadaClase.TRABAJO, Decimal("1200.00")),
            PayerRecord("B00010090", RetencionSoportadaClase.TRABAJO, Decimal("750.00")),
        ),
    )

    values = _values(result)
    assert result.unresolved_bindings == ()
    assert not {"0609", "0610"} & {row.casilla_id for row in result.unresolved_casillas}
    assert values["0596"] == Decimal("1950.00")
    assert values["0597"] == Decimal("0.00")
    assert values["0603"] == Decimal("0.00")
    assert values["0604"] == M130_Q1_RESULTADO
    assert values["0609"] == Decimal("1950.00") + M130_Q1_RESULTADO
    assert values["0610"] == values["0595"] - values["0609"]
    # A resolved credit does not make the planning estimate a filing figure.
    assert result.is_extrapolated


def test_a_work_class_the_profile_excludes_is_a_proven_zero(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    result = run_projection(tmp_path, operation, income_categories=ACTIVITY_ONLY, profile_facts=_NOT_A_RENTAL)

    values = _values(result)
    assert result.unresolved_bindings == ()
    assert values["0596"] == Decimal("0.00")
    assert values["0609"] == M130_Q1_RESULTADO
    assert values["0610"] == values["0595"] - M130_Q1_RESULTADO
