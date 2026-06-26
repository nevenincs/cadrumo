"""Round-trip test for modelo 180 (rental withholdings annual receiver).

Modelo 180 is the annual summary of 115 rental withholdings. Like 193,
it is a pure receiver: three output casillas, each a copy-from-relation
formula. The schema declares the same three-formula shape across both
revisions (2019-2022 and 2023-y-siguientes).

The contract under test: given concrete relation values for the three
115 sources, the snapshot calculator must thread each value into its
matching output casilla via the declared op=copy formula.
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


def test_modelo_180_copies_three_relations_into_three_output_casillas() -> None:
    """Each of 180's three output casillas is a 1-to-1 copy of the matching 115 relation."""

    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    modelo = next(m for m in modelos if m.id == "180")
    revision = next(rev for rev in modelo.revisions.values() if rev.id == "2023-y-siguientes")

    # Graph-wiring assertions — each output casilla must declare an
    # op=copy formula sourcing the matching 115 relation. A declaration
    # regression that flipped the operator or renamed the source
    # relation fails here before the runtime threading assertions run.
    formulas_by_target = {f.target_casilla_id: f for f in revision.formulas}
    expected_wiring = {
        "decl.total-perceptores": "modelo-180-rel-115-perceptores-anual",
        "decl.base-total": "modelo-180-rel-115-base-anual",
        "decl.retenciones-total": "modelo-180-rel-115-retenciones-anual",
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
    # three distinct output casillas. The fixture values are chosen
    # distinct so a swapped-wiring regression (e.g., base-total threaded
    # with the perceptores value) fails loudly.
    snapshot = build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2026, period="0A")
    relation_values = {
        "modelo-180-rel-115-perceptores-anual": Decimal("5"),
        "modelo-180-rel-115-base-anual": Decimal("2149.75"),
        "modelo-180-rel-115-retenciones-anual": Decimal("418.00"),
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
