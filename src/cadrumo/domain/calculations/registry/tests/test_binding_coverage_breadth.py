"""Breadth gate for bound-casilla referential integrity."""

from __future__ import annotations

import pytest

from ..schema_input_kind import InputKind
from .registry_tree import bundled_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_every_bound_casilla_references_bindings_in_its_revision() -> None:
    dangling: list[str] = []
    scanned = 0
    for modelo in bundled_registry_tree()[0]:
        for revision in modelo.revisions.values():
            binding_ids = {binding.id for binding in revision.bindings}
            for casilla in revision.casillas:
                if casilla.input_kind is not InputKind.BOUND:
                    continue
                scanned += 1
                for binding_id in (casilla.binding, *casilla.alternate_bindings):
                    if binding_id not in binding_ids:
                        dangling.append(f"{modelo.id}/{revision.id}/{casilla.id} -> {binding_id}")

    assert scanned > 0
    assert not dangling, "bound casillas with no binding declaration:\n" + "\n".join(f"  + {row}" for row in dangling)
