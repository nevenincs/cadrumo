"""The Modelo 100 projection refuses caller figures for suffered-withholding credits.

The credits on 0596, 0597 and 0603 are owned by the taxpayer's payer records and
absence attestations. The calculation refuses a caller value for them, so the
projection, a planning estimate, refuses one the same way and under its own
command leaf. These run the real projection service over a seeded encrypted
profile, so the refusal comes from the service rather than a helper.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.application.modelo.action_errors import ModeloAggregationBindingError
from cadrumo.application.modelo.projection import ModeloProjectServiceResult
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.retencion_soportada_bindings import retencion_soportada_bindings

from .projection_m130_seeding_support import PROJECTION_YEAR, run_projection

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_CREDIT_CASILLAS = ("0596", "0597", "0603")
# A manual money box no source resolver owns (the employer's contribution to a pension plan, which no
# payer certificate states), and the computed employment-income total it is the only supplied addend of.
_UNRELATED_CASILLA = "0008"
_EMPLOYMENT_INCOME_TOTAL = "0012"


def _family_binding_ids(operation: PinnedAuthorityOperation) -> tuple[str, ...]:
    revision = operation.snapshot("100", filing_year=PROJECTION_YEAR, period="0A").revision
    return tuple(sorted(binding.id for binding, _provider in retencion_soportada_bindings(revision)))


def test_the_family_binding_ids_are_the_revisions_own_declarations(*, operation: PinnedAuthorityOperation) -> None:
    """Anchor the ids so a renamed binding fails here instead of passing vacuously below."""
    assert _family_binding_ids(operation) == (
        "renta-retencion-soportada-arrendamiento-actividad",
        "renta-retencion-soportada-capital-mobiliario",
        "renta-retencion-soportada-ganancia-patrimonial",
        "renta-retencion-soportada-trabajo",
        "renta-retencion-soportada-trabajo-gastos-deducibles",
        "renta-retencion-soportada-trabajo-importe-integro-dinerario",
        "renta-retencion-soportada-trabajo-ingreso-a-cuenta",
        "renta-retencion-soportada-trabajo-ingreso-a-cuenta-repercutido",
        "renta-retencion-soportada-trabajo-reducciones-aplicables",
        "renta-retencion-soportada-trabajo-valoracion-especie",
    )


@pytest.mark.parametrize("casilla", _CREDIT_CASILLAS)
def test_a_caller_figure_on_a_credit_casilla_is_refused_under_the_projection_leaf(
    tmp_path: Path, casilla: str, *, operation: PinnedAuthorityOperation
) -> None:
    with pytest.raises(ModeloAggregationBindingError) as refused:
        run_projection(tmp_path, operation, casilla_overrides={casilla: "1950.00"})

    assert refused.value.translated_message == "application.modelo.errors.caller_casilla_source_binding_conflict"
    assert refused.value.context == {"casillas": [casilla]}
    failure = refused.value.precondition_failure
    assert failure is not None
    assert failure.identity == (
        "modelo.project",
        "modelo.project.source_inputs.unowned",
        "modelo.project.source_inputs.casilla_override_rejected",
    )


@pytest.mark.parametrize(
    "binding_id",
    [
        "renta-retencion-soportada-trabajo",
        "renta-retencion-soportada-capital-mobiliario",
        "renta-retencion-soportada-ganancia-patrimonial",
    ],
)
def test_a_caller_figure_on_a_credit_binding_is_refused_under_the_projection_leaf(
    tmp_path: Path, binding_id: str, *, operation: PinnedAuthorityOperation
) -> None:
    with pytest.raises(ModeloAggregationBindingError) as refused:
        run_projection(tmp_path, operation, binding_overrides={binding_id: "750.00"})

    assert refused.value.context == {"rejected_binding_ids": [binding_id]}
    failure = refused.value.precondition_failure
    assert failure is not None
    assert failure.identity == (
        "modelo.project",
        "modelo.project.source_inputs.unowned",
        "modelo.project.source_inputs.binding_override_rejected",
    )


def test_a_casilla_no_source_owns_is_still_accepted(tmp_path: Path, *, operation: PinnedAuthorityOperation) -> None:
    """The guard is scoped to the credit family: an ordinary manual box still reaches the engine."""
    baseline = run_projection(tmp_path / "baseline", operation)
    overridden = run_projection(tmp_path / "overridden", operation, casilla_overrides={_UNRELATED_CASILLA: "1000.00"})

    def employment_income_total(result: ModeloProjectServiceResult) -> Decimal:
        return next(row.value for row in result.casilla_observations if row.casilla_id == _EMPLOYMENT_INCOME_TOTAL)

    assert employment_income_total(baseline) == Decimal("0.00")
    assert employment_income_total(overridden) == Decimal("1000.00")
