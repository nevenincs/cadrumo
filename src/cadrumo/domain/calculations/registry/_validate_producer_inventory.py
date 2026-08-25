"""Producer-inventory closure validation for one registry revision.

This is intentionally a list-returning validator: the registry validator
accumulates these structural producer failures beside the revision-section
diagnostics before issuing its one refusal.
"""

from __future__ import annotations

from .schema import ModeloRevision
from .schema_input_kind import InputKind


def validate_producer_inventory(prefix: str, revision: ModeloRevision) -> list[str]:
    """Return producer-closure failures for one revision.

    The section validators own formula/casilla reference identity, duplicate
    targets, and dangling directions. This pass consumes the revision's
    lossless producer inventory to close the two model-copy paths that can
    otherwise bypass schema-time input-kind checks: a computed casilla without
    a formula and a non-computed casilla carrying a formula declaration.
    """
    inventory = revision.producer_inventory()
    casilla_by_id = {casilla.id: casilla for casilla in revision.casillas}
    failures: list[str] = []
    for casilla_id, formula_ids in sorted(inventory.formula_ids_by_casilla.items()):
        casilla = casilla_by_id.get(casilla_id)
        if casilla is None or casilla.input_kind == InputKind.COMPUTED:
            continue
        for formula_id in formula_ids:
            failures.append(
                f"{prefix}: casilla {casilla_id!r} declares formula {formula_id!r} "
                f"but input_kind is {casilla.input_kind.value!r}; formula declarations must be computed",
            )

    for casilla_id in sorted(inventory.computed_casilla_ids):
        if casilla_id not in inventory.formula_ids_by_casilla:
            failures.append(
                f"{prefix}: computed casilla {casilla_id!r} has no formula producer declaration",
            )

    return list(dict.fromkeys(failures))
