"""Withholding row-total scenario inputs follow the selected edition's declarations."""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.temporal import select_revision

from ..conformance.registry_schema_support import committed_modelo
from ..edition_export_scenarios import edition_export_scenarios

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# The withholding grouped-row-sum bindings an edition's declarante totals add
# over when it sums its own type-2 records.
_ROW_TOTAL_BINDINGS = {
    "190": frozenset(
        {
            "modelo-190-perceptor-rows-percepcion-dineraria-total",
            "modelo-190-perceptor-rows-percepcion-especie-total",
            "modelo-190-perceptor-rows-incapacidad-dineraria-total",
            "modelo-190-perceptor-rows-incapacidad-especie-total",
            "modelo-190-perceptor-rows-retencion-practicada-total",
            "modelo-190-perceptor-rows-ingreso-a-cuenta-total",
            "modelo-190-perceptor-rows-incapacidad-retencion-total",
            "modelo-190-perceptor-rows-incapacidad-ingreso-a-cuenta-total",
        }
    ),
    "193": frozenset({"modelo-193-perceptor-rows-base-total", "modelo-193-perceptor-rows-retenciones-total"}),
}


@pytest.mark.parametrize("modelo_id", sorted(_ROW_TOTAL_BINDINGS))
def test_row_total_inputs_are_exactly_the_ones_the_selected_edition_declares(modelo_id: str) -> None:
    """A scenario supplies a row total only where its edition sums the type-2 records.

    A missing input leaves the declarante totals unresolved and an undeclared one
    is refused, so a filing-year bound that drifts from the editions fails here.
    """
    modelo, catalogues = committed_modelo(modelo_id)
    row_totals = _ROW_TOTAL_BINDINGS[modelo_id]
    supplying: list[str] = []
    for revision_id, scenario in edition_export_scenarios(modelo_id).items():
        revision = select_revision(
            modelo,
            filing_year=scenario.period.filing_year,
            period=scenario.period.registry_token,
            support=catalogues.supported_filing_years,
        )
        assert str(revision.id) == revision_id
        declared = {str(binding.id) for binding in revision.bindings} & row_totals
        assert set(scenario.inputs) & row_totals == declared, revision_id
        if declared:
            supplying.append(revision_id)
    assert supplying, f"no Modelo {modelo_id} edition sums its type-2 records"
