"""Committed registry legal/source grounding through the real validator."""

from __future__ import annotations

import pytest

from .....core.resources import bundled_path
from .. import RegistryValidator, load_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_committed_registry_legal_and_construct_references_validate_through_loader() -> None:
    """The loaded registry must satisfy legal refs and construct closure checks."""
    registry_root = bundled_path("registry", "aeat")
    modelos, catalogues = load_registry_tree(registry_root)

    assert modelos, "committed registry load produced no modelos"

    validator = RegistryValidator(
        catalogues,
        source_root=bundled_path(),
        catalogue_corpus_strict=False,
    )
    validator.validate_registry(modelos)
