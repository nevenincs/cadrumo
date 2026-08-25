"""Integration contracts for the generated Modelo Workspace field manifest."""

from __future__ import annotations

from functools import cache

import pytest
from pydantic import ValidationError

from ....core import BindingSourceKind
from ....core.resources import resources
from ....domain.calculations.registry import selector_model_for_source
from .._workspace_manifest import (
    MODELO_WORKSPACE_FIELD_MANIFEST_PRODUCER_CONTRACT_V1,
    ModeloWorkspaceFieldManifestEntryV1,
    ModeloWorkspaceFieldManifestV1,
    _manifest_digest,
    _Node,
    _walk_annotation,
    generate_modelo_workspace_field_manifest,
    validate_modelo_workspace_field_manifest,
)
from .._workspace_models import ModeloWorkspaceSchemaClassification, ModeloWorkspaceSchemaReferenceV1
from .._workspace_producers import ModeloWorkspaceContributorKindV1

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]


@cache
def _snapshot():
    """Use one real, exported authority snapshot with generated export layouts."""
    return resources().modelos.authority.snapshot("303", filing_year=2025, period="4T")


@cache
def _manifest() -> ModeloWorkspaceFieldManifestV1:
    return generate_modelo_workspace_field_manifest(_snapshot())


def _rebuild_manifest(
    manifest: ModeloWorkspaceFieldManifestV1,
    *,
    traversal_roots: tuple[str, ...] | None = None,
    entries: tuple[ModeloWorkspaceFieldManifestEntryV1, ...] | None = None,
) -> ModeloWorkspaceFieldManifestV1:
    roots = manifest.traversal_roots if traversal_roots is None else traversal_roots
    manifest_entries = manifest.entries if entries is None else entries
    return ModeloWorkspaceFieldManifestV1(
        traversal_roots=roots,
        entries=manifest_entries,
        manifest_digest=_manifest_digest(roots, manifest_entries),
    )


def test_workspace_manifest_is_a_real_authority_fixed_point_with_safe_classifications() -> None:
    snapshot = _snapshot()
    manifest = _manifest()

    assert validate_modelo_workspace_field_manifest(manifest, snapshot) is manifest
    assert manifest.entries == tuple(sorted(manifest.entries, key=lambda entry: entry.path))
    assert len({entry.path for entry in manifest.entries}) == len(manifest.entries)
    assert {entry.classification for entry in manifest.entries} == {
        ModeloWorkspaceSchemaClassification.PROJECTED,
        ModeloWorkspaceSchemaClassification.DERIVED,
        ModeloWorkspaceSchemaClassification.BACKEND_ONLY,
    }
    assert any(entry.path.startswith("derived.export_layout.") for entry in manifest.entries)
    assert all(
        entry.classification is ModeloWorkspaceSchemaClassification.DERIVED
        for entry in manifest.entries
        if entry.path.startswith("derived.export_layout.")
    )
    assert any(entry.destination is not None for entry in manifest.entries)
    assert any(entry.reason == "selector_configuration" for entry in manifest.entries)


def test_workspace_manifest_includes_every_public_selector_root_and_its_extra_universe() -> None:
    manifest = _manifest()
    selector_roots = tuple(root for root in manifest.traversal_roots if root.startswith("selector."))
    selector_entries = tuple(entry for entry in manifest.entries if entry.path.startswith("selector."))

    expected_roots = tuple(
        sorted(
            f"selector.{source.value}"
            for source in BindingSourceKind
            if selector_model_for_source(source) is not None
        )
    )
    assert selector_roots == expected_roots
    assert selector_entries
    assert len(selector_entries) < len(manifest.entries)
    for root in selector_roots:
        assert any(entry.path.startswith(f"{root}.") for entry in selector_entries)

    without_selectors = _rebuild_manifest(
        manifest,
        traversal_roots=tuple(root for root in manifest.traversal_roots if not root.startswith("selector.")),
        entries=tuple(entry for entry in manifest.entries if not entry.path.startswith("selector.")),
    )
    with pytest.raises(ValueError, match="fixed point"):
        validate_modelo_workspace_field_manifest(without_selectors, _snapshot())


def test_workspace_manifest_walks_existing_tagged_union_and_collection_coordinates() -> None:
    nodes: dict[str, _Node] = {}
    _walk_annotation(
        annotation=ModeloWorkspaceSchemaReferenceV1,
        path="workspace_schema_reference",
        nodes=nodes,
        visited=set(),
        active=(),
        discriminator=None,
    )

    assert any(".variant=kind=casilla" in path for path in nodes)
    assert any(".variant=kind=formula_operand_casilla" in path for path in nodes)
    assert any("collection_item" in entry.path for entry in _manifest().entries)
    assert len(nodes) == len(set(nodes))


def test_workspace_manifest_refuses_duplicate_stale_and_unclassified_fixed_points() -> None:
    manifest = _manifest()
    payload = manifest.model_dump()
    payload["traversal_roots"] = tuple(payload["traversal_roots"])
    payload["entries"] = tuple([payload["entries"][0], *payload["entries"]])
    with pytest.raises(ValidationError, match="sorted and unique"):
        ModeloWorkspaceFieldManifestV1.model_validate(payload)

    stale_payload = manifest.model_dump()
    stale_payload["traversal_roots"] = tuple(stale_payload["traversal_roots"])
    stale_payload["entries"] = tuple(stale_payload["entries"][1:])
    with pytest.raises(ValidationError, match="digest does not reproduce"):
        ModeloWorkspaceFieldManifestV1.model_validate(stale_payload)

    changed_entry = manifest.entries[0].model_copy(update={"path": "registry_snapshot.unknown_field"})
    unclassified = _rebuild_manifest(
        manifest,
        entries=tuple(sorted((changed_entry, *manifest.entries[1:]), key=lambda entry: entry.path)),
    )
    with pytest.raises(ValueError, match="fixed point"):
        validate_modelo_workspace_field_manifest(unclassified, _snapshot())


def test_workspace_field_manifest_declares_the_single_s126_contributor_contract() -> None:
    contract = MODELO_WORKSPACE_FIELD_MANIFEST_PRODUCER_CONTRACT_V1

    assert contract.contributor_kind is ModeloWorkspaceContributorKindV1.FIELD_MANIFEST
    assert contract.contributor.owner == "domain.calculations.registry"
    assert contract.projection_discriminator == "workspace_field_manifest"
