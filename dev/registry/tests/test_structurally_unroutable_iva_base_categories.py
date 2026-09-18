"""Compiler mutation proof for the structural IVA base-category screen."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.ledger_iva_bindings import (
    structurally_unroutable_iva_base_categories,
)
from cadrumo.domain.iva.schema import IvaCategory
from dev.registry.compiler.authority import compiled_bundled_authority

from ..compiler.loader import load_registry_tree
from ._gate_support import declaring_fragment, scratch_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("governed_fact_scope")]

_INTRA_COMMUNITY_SUPPLY_BASE_BINDING = "modelo-303-casilla-59-entregas-intracomunitarias-base"


def test_mutation_stripping_the_intra_community_supply_binding_reds_the_negative_control(tmp_path: Path) -> None:
    """A source mutation must change the compiler-derived structural result."""
    scratch_root = scratch_registry_tree(tmp_path, "303")
    revision_id = compiled_bundled_authority().snapshot("303", filing_year=2025, period="1T").revision.id
    # The binding is addressed by its declared id, never by a fragment
    # filename: the edition under test carries no bindings directory of its
    # own, and the baseline holding it states every binding in one fragment.
    fragment = declaring_fragment(
        scratch_root / "modelos" / "303",
        revision_id=revision_id,
        section="bindings",
        anchor=f'id = "{_INTRA_COMMUNITY_SUPPLY_BASE_BINDING}"',
    )
    fragment.mutate(
        'categories = ["intra_community_supply"]',
        'categories = ["domestic_general"]',
        after=f'id = "{_INTRA_COMMUNITY_SUPPLY_BASE_BINDING}"',
    )

    modelos, _catalogues = load_registry_tree(scratch_root)
    mutated_revision = next(modelo for modelo in modelos if modelo.id == "303").revisions[revision_id]

    unroutable = structurally_unroutable_iva_base_categories(mutated_revision)
    assert IvaCategory("intra_community_supply") in unroutable, (
        "stripping the only binding drawing intra_community_supply's base must red the negative control"
    )
