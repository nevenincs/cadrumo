"""Round-trip tests for the small annual-summary receivers 190 and 193.

Modelos 190 and 193 are pure receivers: their casilla schemas declare
only output totals (no taxpayer-input casillas), and every formula
expression sources directly from cross-modelo relations resolved
upstream. The contract under test is "given concrete relation values,
produce concrete output casilla values" — the receiver's formula
composition is the unit under test, separate from the chain resolver
which produces the relation values.

Modelo 190 (annual summary of 111 worker / professional withholdings)
declares three output casillas. The monetary outputs source from Modelo 111
relations; the percepciones count is bound to the withholding detail source:

- ``decl.total-percepciones`` = bound distinct (perceptor, clave, subclave)
  withholding count
- ``decl.percepciones-total`` = sum of the nine importe relations
- ``decl.retenciones-total`` = copy of the single retenciones relation

Modelo 193 (annual summary of 123 capital-mobiliario withholdings)
declares two monetary output casillas as single-relation copies, while
``decl.total-perceptores`` is bound to the dedicated retenciones aggregation
source:

- ``decl.total-perceptores`` = bound distinct perceptor-NIF count
- ``decl.base-total`` = copy of base-anual
- ``decl.retenciones-total`` = copy of retenciones-anual
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.bindings import resolve_available_bound_inputs_by_casilla_id
from cadrumo.domain.calculations.registry.schema_input_kind import InputKind

from .....core.resources import bundled_path
from ..formula_runtime import calculate_registry_snapshot
from ..snapshot import build_snapshot
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_modelo_193_copies_monetary_relations_and_binds_perceptor_count() -> None:
    """M193 relation formulas cover money only; perceptor count is a bound distinct-NIF fact."""

    modelo, catalogues = _committed_modelo("193")
    revision = next(iter(modelo.revisions.values()))

    # Graph-wiring assertions — each monetary output casilla must declare an
    # op=copy formula sourcing the matching 123 relation. The perceptor count
    # must stay off the relation graph.
    formulas_by_target = {f.target_casilla_id: f for f in revision.formulas}
    expected_relation_wiring = {
        "decl.base-total": "modelo-193-rel-123-base-anual",
        "decl.retenciones-total": "modelo-193-rel-123-retenciones-anual",
    }
    assert "decl.total-perceptores" not in formulas_by_target
    perceptor_casilla = next(c for c in revision.casillas if c.id == "decl.total-perceptores")
    assert perceptor_casilla.input_kind is InputKind.BOUND
    assert perceptor_casilla.binding == "modelo-193-123-perceptores-anual"
    perceptor_binding = next(b for b in revision.bindings if b.id == "modelo-193-123-perceptores-anual")
    assert perceptor_binding.source == "retenciones_aggregation"

    for target, expected_source in expected_relation_wiring.items():
        formula = formulas_by_target[target]
        expression = formula.expression.model_dump(exclude_none=True)
        assert expression.get("op") == "copy", f"{target} formula must be op=copy"
        args = expression.get("args") or []
        assert len(args) == 1, f"{target} op=copy must take exactly one argument"
        assert args[0].get("relation") == expected_source, (
            f"{target} op=copy must source from {expected_source}, got {args[0]!r}"
        )

    # Runtime threading — two distinct relation values must land in the
    # relation-backed casillas without cross-contamination; the count arrives
    # through the binding channel.
    snapshot = build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2026, period="0A")
    relation_values = {
        "modelo-193-rel-123-base-anual": Decimal("7000.50"),
        "modelo-193-rel-123-retenciones-anual": Decimal("1330.10"),
    }
    binding_values = {"modelo-193-123-perceptores-anual": Decimal("2")}
    result = calculate_registry_snapshot(
        snapshot,
        inputs=resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values),
        date_context={"filing_period": date(2026, 1, 31)},
        binding_values=binding_values,
        relation_values=relation_values,
    )

    assert result.values["decl.total-perceptores"] == binding_values["modelo-193-123-perceptores-anual"]
    for target, source in expected_relation_wiring.items():
        assert result.values[target] == relation_values[source], (
            f"op=copy thread broke: {target} should equal {source}={relation_values[source]}"
        )
