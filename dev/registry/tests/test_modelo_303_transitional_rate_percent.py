"""Compiler mutation proof for M303 transitional-rate source declarations."""

from __future__ import annotations

import shutil
from pathlib import Path

from ..compiler.loader import load_registry_tree


def test_mutation_reverting_154_to_manual_reds_the_gate(tmp_path: Path) -> None:
    """A scratch source-tree mutation must parse casilla 154 as manual."""
    bundled_root = _bundled_registry_root()
    scratch_root = tmp_path / "registry-mutant" / "aeat"
    (scratch_root / "modelos").mkdir(parents=True)
    shutil.copytree(bundled_root / "modelos" / "303", scratch_root / "modelos" / "303")
    for catalogue_dir in ("apoderamientos", "categories", "iva", "legal", "topics"):
        source = bundled_root / catalogue_dir
        if source.is_dir():
            shutil.copytree(source, scratch_root / catalogue_dir)
        elif source.exists():
            shutil.copy2(source, scratch_root / catalogue_dir)
    casillas_path = (
        scratch_root
        / "modelos"
        / "303"
        / "revisions"
        / "2024-desde-09-y-3t"
        / "casillas"
        / "civa.repercutido.general__c21.toml"
    )
    original = casillas_path.read_text(encoding="utf-8")
    mutated = original.replace(
        'input_kind = "computed"\nformula = "modelo-303-dr303-154-rate"', 'input_kind = "manual"', 1
    )
    assert mutated != original, "the mutation target string was not found -- test is stale"
    casillas_path.write_text(mutated, encoding="utf-8")
    modelos, _catalogues = load_registry_tree(scratch_root)
    revision = next(modelo for modelo in modelos if modelo.id == "303").revisions["2024-desde-09-y-3t"]
    casillas = {casilla.id: casilla for casilla in revision.casillas}
    assert casillas["154"].input_kind == "manual"
    assert casillas["154"].formula is None


def _bundled_registry_root() -> Path:
    return Path(__file__).resolve().parents[4] / "_data" / "registry" / "aeat"
