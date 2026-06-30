"""Committed registry legal/source grounding through the real validator."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from .....core.resources import bundled_path
from .. import RegistryValidator, load_registry_tree, verify_legal_catalogue

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_committed_registry_legal_and_construct_references_validate_through_loader() -> None:
    """The loaded registry must satisfy legal refs and construct closure checks."""
    registry_root = bundled_path("registry", "aeat")
    modelos, catalogues = load_registry_tree(registry_root)

    assert modelos, "committed registry load produced no modelos"

    validator = RegistryValidator(catalogues, source_root=bundled_path())
    validator.validate_registry(modelos)


def _collect_legal_refs_from_toml(path: Path) -> tuple[str, ...]:
    found: list[str] = []

    def walk(value: object) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key == "legal_refs":
                    if isinstance(item, list):
                        found.extend(ref for ref in item if isinstance(ref, str))
                    elif isinstance(item, str):
                        found.append(item)
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(tomllib.loads(path.read_text(encoding="utf-8")))
    return tuple(found)


def test_every_bundled_registry_toml_legal_ref_resolves_to_catalogue_and_corpus() -> None:
    registry_root = bundled_path("registry", "aeat")
    _modelos, catalogues = load_registry_tree(registry_root)
    refs_by_file = {
        path.relative_to(registry_root).as_posix(): refs
        for path in registry_root.rglob("*.toml")
        if (refs := _collect_legal_refs_from_toml(path))
    }
    refs = sorted({ref for file_refs in refs_by_file.values() for ref in file_refs})

    assert refs_by_file, "bundled registry TOML contains no legal_refs keys"
    missing = sorted(ref for ref in refs if ref not in catalogues.legal)
    assert not missing, f"bundled registry TOML legal_refs absent from legal catalogue: {missing}"
    verify_legal_catalogue({ref: catalogues.legal[ref] for ref in refs}, source_root=bundled_path())
