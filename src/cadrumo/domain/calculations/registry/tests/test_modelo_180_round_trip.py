"""Round-trip test for modelo 180 (rental withholdings annual receiver).

Modelo 180 is the annual summary of 115 rental withholdings. Its monetary
outputs are copy-from-relation formulas. Its perceptor-count output is a bound
``retenciones_aggregation`` value, because summing quarterly perceptor counts
double-counts a landlord paid in more than one quarter.

The contract under test: given concrete relation values for the two monetary
115 sources, the snapshot calculator must thread each value into its matching
output casilla via the declared op=copy formula, while the count casilla stays
bound to the dedicated distinct-perceptor source.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.resources import bundled_path
from .. import InputKind, resolve_available_bound_inputs_by_casilla_id
from ..formula_runtime import calculate_registry_snapshot
from ..snapshot import build_snapshot
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_modelo_180_copies_monetary_relations_and_binds_perceptor_count() -> None:
    """M180 relation formulas cover money only; perceptor count is a bound distinct-NIF fact."""

    modelo, catalogues = _committed_modelo("180")
    revision = next(rev for rev in modelo.revisions.values() if rev.id == "2023-y-siguientes")

    # Graph-wiring assertions — each output casilla must declare an
    # op=copy formula sourcing the matching 115 relation. A declaration
    # regression that flipped the operator or renamed the source
    # relation fails here before the runtime threading assertions run.
    formulas_by_target = {f.target_casilla_id: f for f in revision.formulas}
    expected_relation_wiring = {
        "decl.base-total": "modelo-180-rel-115-base-anual",
        "decl.retenciones-total": "modelo-180-rel-115-retenciones-anual",
    }
    assert "decl.total-perceptores" not in formulas_by_target
    perceptor_casilla = next(c for c in revision.casillas if c.id == "decl.total-perceptores")
    assert perceptor_casilla.input_kind is InputKind.BOUND
    assert perceptor_casilla.binding == "modelo-180-115-perceptores-anual"
    perceptor_binding = next(b for b in revision.bindings if b.id == "modelo-180-115-perceptores-anual")
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

    # Runtime threading — two distinct relation values must land in
    # the two relation-backed output casillas. The fixture values are chosen
    # distinct so a swapped-wiring regression (e.g., base-total threaded
    # with the retenciones value) fails loudly. The bound perceptor fixture is
    # separate so the test also proves the count is not relation-fed.
    snapshot = build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2026, period="0A")
    relation_values = {
        "modelo-180-rel-115-base-anual": Decimal("2149.75"),
        "modelo-180-rel-115-retenciones-anual": Decimal("418.00"),
    }
    binding_values = {"modelo-180-115-perceptores-anual": Decimal("3")}
    result = calculate_registry_snapshot(
        snapshot,
        inputs=resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values),
        date_context={"filing_period": date(2026, 1, 31)},
        binding_values=binding_values,
        relation_values=relation_values,
    )

    assert result.values["decl.total-perceptores"] == binding_values["modelo-180-115-perceptores-anual"]
    for target, source in expected_relation_wiring.items():
        assert result.values[target] == relation_values[source], (
            f"op=copy thread broke: {target} should equal {source}={relation_values[source]}"
        )
