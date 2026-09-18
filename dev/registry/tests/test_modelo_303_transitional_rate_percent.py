"""Compiler mutation proof for M303 transitional-rate source declarations."""

from __future__ import annotations

from pathlib import Path

import pytest

from ..compiler.loader import load_registry_tree
from ._gate_support import declaring_fragment, scratch_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("governed_fact_scope")]

_REVISION_ID = "2024-desde-09-y-3t"


def test_mutation_reverting_154_to_manual_reds_the_gate(tmp_path: Path) -> None:
    """A scratch source-tree mutation must parse casilla 154 as manual."""
    scratch_root = scratch_registry_tree(tmp_path, "303")
    fragment = declaring_fragment(
        scratch_root / "modelos" / "303",
        revision_id=_REVISION_ID,
        section="casillas",
        anchor='formula = "modelo-303-dr303-154-rate"',
    )
    fragment.mutate('input_kind = "computed"\nformula = "modelo-303-dr303-154-rate"', 'input_kind = "manual"')

    modelos, _catalogues = load_registry_tree(scratch_root)
    revision = next(modelo for modelo in modelos if modelo.id == "303").revisions[_REVISION_ID]
    casillas = {casilla.id: casilla for casilla in revision.casillas}
    assert casillas["154"].input_kind == "manual"
    assert casillas["154"].formula is None
