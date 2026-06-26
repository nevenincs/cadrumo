"""Round-trip tests for the small annual-summary receivers 190 and 193.

Modelos 190 and 193 are pure receivers: their casilla schemas declare
only output totals (no taxpayer-input casillas), and every formula
expression sources directly from cross-modelo relations resolved
upstream. The contract under test is "given concrete relation values,
produce concrete output casilla values" — the receiver's formula
composition is the unit under test, separate from the chain resolver
which produces the relation values.

Modelo 190 (annual summary of 111 worker / professional withholdings)
declares three output casillas:

- ``decl.total-percepciones`` = sum of the nine perception-count
  relations (trabajo dinerario, trabajo especie, ..., derechos
  imagen)
- ``decl.percepciones-total`` = sum of the nine importe relations
- ``decl.retenciones-total`` = copy of the single retenciones relation

Modelo 193 (annual summary of 123 capital-mobiliario withholdings)
declares three output casillas, each a single-relation copy:

- ``decl.total-perceptores`` = copy of perceptores-anual
- ``decl.base-total`` = copy of base-anual
- ``decl.retenciones-total`` = copy of retenciones-anual
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.resources import bundled_path
from .._formula_runtime import calculate_registry_snapshot
from .._loader import load_registry_tree
from .._snapshot import build_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REGISTRY_ROOT = bundled_path("registry", "aeat")


def test_modelo_193_copies_three_relations_into_three_output_casillas() -> None:
    """Each of 193's three output casillas is a 1-to-1 copy of the matching 123 relation."""

    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    modelo = next(m for m in modelos if m.id == "193")
    revision = next(iter(modelo.revisions.values()))

    # Graph-wiring assertions — each output casilla must declare an
    # op=copy formula sourcing the matching 123 relation. A swapped
    # source or flipped operator fails here before threading.
    formulas_by_target = {f.target_casilla_id: f for f in revision.formulas}
    expected_wiring = {
        "decl.total-perceptores": "modelo-193-rel-123-perceptores-anual",
        "decl.base-total": "modelo-193-rel-123-base-anual",
        "decl.retenciones-total": "modelo-193-rel-123-retenciones-anual",
    }
    for target, expected_source in expected_wiring.items():
        formula = formulas_by_target[target]
        expression = formula.expression.model_dump(exclude_none=True)
        assert expression.get("op") == "copy", f"{target} formula must be op=copy"
        args = expression.get("args") or []
        assert len(args) == 1, f"{target} op=copy must take exactly one argument"
        assert args[0].get("relation") == expected_source, (
            f"{target} op=copy must source from {expected_source}, got {args[0]!r}"
        )

    # Runtime threading — three distinct relation values must land in
    # three distinct casillas without cross-contamination.
    snapshot = build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2026, period="0A")
    relation_values = {
        "modelo-193-rel-123-perceptores-anual": Decimal("12"),
        "modelo-193-rel-123-base-anual": Decimal("7000.50"),
        "modelo-193-rel-123-retenciones-anual": Decimal("1330.10"),
    }
    result = calculate_registry_snapshot(
        snapshot,
        inputs={},
        date_context={"filing_period": date(2026, 1, 31)},
        relation_values=relation_values,
    )

    for target, source in expected_wiring.items():
        assert result.values[target] == relation_values[source], (
            f"op=copy thread broke: {target} should equal {source}={relation_values[source]}"
        )
