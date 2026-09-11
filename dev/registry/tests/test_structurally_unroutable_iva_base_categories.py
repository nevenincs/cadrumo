"""Compiler mutation proof for the structural IVA base-category screen."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import bundled_authority
from cadrumo.domain.calculations.registry.ledger_iva_bindings import (
    structurally_unroutable_iva_base_categories,
)
from cadrumo.domain.iva.schema import IvaCategory

from ..compiler.loader import load_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_mutation_stripping_the_intra_community_supply_binding_reds_the_negative_control(tmp_path: Path) -> None:
    """A source mutation must change the compiler-derived structural result."""
    bundled_root = bundled_path("registry", "aeat")
    scratch_root = tmp_path / "registry-mutant" / "aeat"
    (scratch_root / "modelos").mkdir(parents=True)
    shutil.copytree(bundled_root / "modelos" / "303", scratch_root / "modelos" / "303")
    for catalogue_dir in ("apoderamientos", "iva", "legal", "topics"):
        source = bundled_root / catalogue_dir
        if source.is_dir():
            shutil.copytree(source, scratch_root / catalogue_dir)
        elif source.exists():
            shutil.copy2(source, scratch_root / catalogue_dir)

    revision_id = bundled_authority().snapshot("303", filing_year=2025, period="1T").revision.id
    bindings_dir = scratch_root / "modelos" / "303" / "revisions" / revision_id / "bindings"
    candidates = sorted(bindings_dir.glob("*intracom-export-base*.toml"))
    assert len(candidates) == 1, f"expected exactly one intracom-export-base fragment, found {candidates}"
    bindings_path = candidates[0]
    original = bindings_path.read_text(encoding="utf-8")
    mutated = original.replace('categories = ["intra_community_supply"]', 'categories = ["domestic_general"]', 1)
    assert mutated != original, "the mutation target string was not found -- test is stale"
    bindings_path.write_text(mutated, encoding="utf-8")

    modelos, _catalogues = load_registry_tree(scratch_root)
    mutated_revision = next(modelo for modelo in modelos if modelo.id == "303").revisions[revision_id]

    unroutable = structurally_unroutable_iva_base_categories(mutated_revision)
    assert IvaCategory.INTRA_COMMUNITY_SUPPLY in unroutable, (
        "stripping the only binding drawing intra_community_supply's base must red the negative control"
    )
