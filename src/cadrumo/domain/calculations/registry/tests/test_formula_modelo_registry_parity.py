"""Registry parity checks for formula-backed modelo definitions."""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.validate import RegistryValidator

from .....core.resources import bundled_path
from ._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_formula_revisions_are_owned_by_constructs_with_snapshot_workflow_surfaces() -> None:
    modelos, catalogues = _committed_registry_tree()
    validator = RegistryValidator(catalogues, source_root=bundled_path())
    required_surfaces = {"calculation", "review", "approval", "reconciliation", "workflow"}

    for modelo in modelos:
        validator.validate_modelo(modelo)
        for revision in modelo.revisions.values():
            if not revision.formulas:
                continue

            owned_formulas = set().union(*(set(construct.formulas) for construct in revision.constructs))
            assert {formula.id for formula in revision.formulas} <= owned_formulas, (modelo.id, revision.id)

            linked_ids = set().union(*(set(construct.application_links) for construct in revision.constructs))
            linked_by_surface = {link.surface: link for link in revision.application_links if link.id in linked_ids}
            assert required_surfaces <= set(linked_by_surface), (modelo.id, revision.id)
            assert all(link.requires_snapshot for link in linked_by_surface.values()), (modelo.id, revision.id)
