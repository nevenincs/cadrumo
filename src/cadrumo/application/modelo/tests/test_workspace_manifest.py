"""Integration contracts for the generated Modelo Workspace field manifest."""

from __future__ import annotations

from collections.abc import Mapping
from functools import cache
from typing import Literal

import pytest
from pydantic import BaseModel, ValidationError

from ....core import BindingSourceKind
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.bindings import selector_model_for_source
from ..workspace_manifest import (
    ModeloWorkspaceFieldManifestEntryV1,
    ModeloWorkspaceFieldManifestV1,
    ModeloWorkspaceManifestCapture,
    ModeloWorkspaceManifestCaptureError,
    ModeloWorkspaceManifestCurrentCoordinate,
    _manifest_digest,
    _Node,
    _walk_annotation,
    capture_modelo_workspace_manifest,
    capture_modelo_workspace_manifest_for_inspection,
    generate_modelo_workspace_field_manifest,
    generate_modelo_workspace_field_manifest_for_inspection,
    read_modelo_workspace_manifest_current_coordinate,
    read_modelo_workspace_manifest_current_coordinate_for_inspection,
    validate_modelo_workspace_field_manifest,
    validate_modelo_workspace_field_manifest_for_inspection,
)
from ..workspace_models import ModeloWorkspaceSchemaClassification, ModeloWorkspaceSchemaReferenceV1
from ..workspace_producers import (
    MODELO_WORKSPACE_FIELD_MANIFEST_PRODUCER_CONTRACT_V1,
    ModeloWorkspaceContributorKindV1,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]


type _NestedTraversalAlias = Mapping[str, tuple[int, ...]]


class _NestedTraversalModel(BaseModel):
    value: str


@cache
def _snapshot():
    """Use one real, exported authority snapshot with generated export layouts."""
    return bundled_authority().snapshot("303", filing_year=2025, period="4T")


@cache
def _manifest() -> ModeloWorkspaceFieldManifestV1:
    return generate_modelo_workspace_field_manifest(_snapshot())


@cache
def _inspection():
    """Use one real, exported static-inspection projection for the same coordinate."""
    return bundled_authority().capture_law_selected_projection("303", filing_year=2025, period="4T").projection


@cache
def _inspection_manifest() -> ModeloWorkspaceFieldManifestV1:
    return generate_modelo_workspace_field_manifest_for_inspection(_inspection())


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
            f"selector.{source.value}" for source in BindingSourceKind if selector_model_for_source(source) is not None
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


def test_workspace_manifest_projects_only_representable_live_formula_operands() -> None:
    """M303 proves compiler grammar cannot masquerade as a Workspace operand DTO."""
    entries_by_suffix = {
        entry.path.removeprefix("registry_snapshot.revision.formulas.collection_item.expression."): entry
        for entry in _manifest().entries
        if entry.path.startswith("registry_snapshot.revision.formulas.collection_item.expression.")
    }

    projected = entries_by_suffix["binding.variant=union=BindingId"]
    assert projected.classification is ModeloWorkspaceSchemaClassification.PROJECTED
    assert projected.destination == "ModeloWorkspaceFormulaOperandReferenceV1"

    literal = entries_by_suffix["literal.variant=union=Decimal"]
    assert literal.classification is ModeloWorkspaceSchemaClassification.PROJECTED
    assert literal.destination == "ModeloWorkspaceFormulaOperandReferenceV1"

    for suffix in (
        "binding.variant=union=NoneType",
        "op.variant=union=Literal",
        "dispatch_table.variant=union=Mapping",
    ):
        entry = entries_by_suffix[suffix]
        assert entry.classification is ModeloWorkspaceSchemaClassification.BACKEND_ONLY
        assert entry.destination is None
        assert entry.owner == "domain.calculations.registry"
        assert entry.reason == "registry_declaration"


def test_workspace_manifest_walks_nested_union_containers_and_aliases() -> None:
    nodes: dict[str, _Node] = {}
    _walk_annotation(
        annotation=_NestedTraversalAlias | tuple[_NestedTraversalModel, ...] | Literal["literal"] | int | None,
        path="synthetic",
        nodes=nodes,
        visited=set(),
        active=(),
        discriminator=None,
    )

    assert any(path.endswith(".mapping_value.collection_item") for path in nodes)
    assert any(path.endswith(".collection_item.value") for path in nodes)
    assert any(path.endswith("variant=union=Literal") for path in nodes)
    assert any(path.endswith("variant=union=int") for path in nodes)
    assert any(path.endswith("variant=union=NoneType") for path in nodes)


def test_workspace_manifest_walks_live_dispatch_parameter_identity() -> None:
    entries = {
        entry.path: entry
        for entry in _manifest().entries
        if entry.path.startswith("registry_snapshot.revision.formulas.collection_item.expression.dispatch_table")
    }
    dispatch = entries[
        "registry_snapshot.revision.formulas.collection_item.expression.dispatch_table.variant=union=Mapping"
    ]
    parameter = entries[
        "registry_snapshot.revision.formulas.collection_item.expression.dispatch_table.variant=union=Mapping.mapping_value"
    ]

    assert dispatch.classification is ModeloWorkspaceSchemaClassification.BACKEND_ONLY
    assert dispatch.destination is None
    assert parameter.schema_type == "ParameterId"
    assert parameter.classification is ModeloWorkspaceSchemaClassification.PROJECTED
    assert parameter.destination == "ModeloWorkspaceParameterReferenceV1"


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
    assert contract.contributor.owner == "application.modelo.workspace_manifest"
    assert contract.projection_discriminator == "workspace_field_manifest"


def test_capture_republishes_the_sole_walker_manifest_without_rewalking() -> None:
    """The capture carries exactly what the one generating authority produced."""
    snapshot = _snapshot()

    captured = capture_modelo_workspace_manifest(snapshot)

    assert captured.manifest == generate_modelo_workspace_field_manifest(snapshot)
    assert validate_modelo_workspace_field_manifest(captured.manifest, snapshot) is captured.manifest


def test_capture_is_singleflight_and_current_against_its_own_coordinate() -> None:
    """An unchanged schema denominator shares one generation and stays current."""
    snapshot = _snapshot()

    first = capture_modelo_workspace_manifest(snapshot)
    second = capture_modelo_workspace_manifest(snapshot)

    assert first.generation == second.generation
    assert first.comparison_domain == second.comparison_domain

    current = read_modelo_workspace_manifest_current_coordinate(snapshot)
    assert first.require_current(current) is first


def test_a_distinct_snapshot_coordinate_is_a_distinct_owner_scope() -> None:
    """Two filing coordinates never validate each other's capture."""
    snapshot = _snapshot()
    other = bundled_authority().snapshot("303", filing_year=2025, period="3T")

    captured = capture_modelo_workspace_manifest(snapshot)
    other_coordinate = read_modelo_workspace_manifest_current_coordinate(other)

    assert captured.comparison_domain != other_coordinate.comparison_domain
    with pytest.raises(ModeloWorkspaceManifestCaptureError):
        captured.require_current(other_coordinate)


def test_a_superseded_generation_is_refused_within_one_owner_scope() -> None:
    """A coordinate from a different manifest digest refuses the earlier capture."""
    snapshot = _snapshot()
    captured = capture_modelo_workspace_manifest(snapshot)

    superseded = ModeloWorkspaceManifestCurrentCoordinate(
        comparison_domain=captured.comparison_domain,
        generation=captured.generation + 1,
    )

    with pytest.raises(ModeloWorkspaceManifestCaptureError):
        captured.require_current(superseded)


def test_capture_exposes_no_snapshot_internals_and_no_second_manifest_shape() -> None:
    """The capture adds a coordinate only; it derives no parallel manifest."""
    from dataclasses import fields

    snapshot = _snapshot()
    captured = capture_modelo_workspace_manifest(snapshot)

    assert {field.name for field in fields(ModeloWorkspaceManifestCapture)} == {
        "manifest",
        "comparison_domain",
        "generation",
    }
    assert {field.name for field in fields(ModeloWorkspaceManifestCurrentCoordinate)} == {
        "comparison_domain",
        "generation",
    }
    assert str(snapshot.revision.id) not in captured.comparison_domain


def test_manifest_authority_is_owned_by_its_public_defining_module() -> None:
    """Every manifest symbol is defined here and bound nowhere in the package namespace."""
    from ... import modelo as modelo_namespace

    for owned in (
        ModeloWorkspaceFieldManifestEntryV1,
        ModeloWorkspaceFieldManifestV1,
        ModeloWorkspaceManifestCapture,
        ModeloWorkspaceManifestCurrentCoordinate,
        ModeloWorkspaceManifestCaptureError,
        capture_modelo_workspace_manifest,
        generate_modelo_workspace_field_manifest,
        read_modelo_workspace_manifest_current_coordinate,
        validate_modelo_workspace_field_manifest,
    ):
        assert owned.__module__ == "cadrumo.application.modelo.workspace_manifest"
        assert not hasattr(modelo_namespace, owned.__name__)


def test_the_retired_private_manifest_module_is_gone() -> None:
    """No private path, alias, or re-export survives the hard move."""
    import importlib
    from pathlib import Path

    package = Path(importlib.import_module("cadrumo.application.modelo").__file__).parent

    assert not (package / "_workspace_manifest.py").exists()
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("cadrumo.application.modelo._workspace_manifest")


# STATIC_INSPECTION gets its own complete manifest, over its own
# type universe, never a filtered view into the snapshot-rooted manifest ---


def test_inspection_manifest_is_a_real_authority_fixed_point_with_safe_classifications() -> None:
    inspection = _inspection()
    manifest = _inspection_manifest()

    assert validate_modelo_workspace_field_manifest_for_inspection(manifest, inspection) is manifest
    assert manifest.entries == tuple(sorted(manifest.entries, key=lambda entry: entry.path))
    assert len({entry.path for entry in manifest.entries}) == len(manifest.entries)
    assert any(entry.destination is not None for entry in manifest.entries)
    assert any(entry.reason == "selector_configuration" for entry in manifest.entries)
    assert all(path.startswith(("registry_revision_inspection", "selector.")) for path in manifest.traversal_roots)


def test_inspection_manifest_has_no_export_layout_root() -> None:
    """RegistryRevisionInspection carries no full ModeloRevision, so it derives no export layout."""
    manifest = _inspection_manifest()

    assert not any(path.startswith("derived.export_layout.") for path in manifest.traversal_roots)
    assert not any(entry.path.startswith("derived.export_layout.") for entry in manifest.entries)


def test_inspection_manifest_never_reaches_filing_grade_content() -> None:
    """Admission-honesty: no entry can name a materialization, verification, or filing-state field.

    RegistryRevisionInspection structurally has no such fields at all, so this
    is a property of the walked type rather than a filter -- the manifest
    cannot accidentally claim availability the inspection has no data for.
    """
    manifest = _inspection_manifest()

    for entry in manifest.entries:
        assert "materializ" not in entry.path
        assert "verification" not in entry.path
        assert "filed_at" not in entry.path
        assert "calculation" not in entry.path


def test_inspection_manifest_is_stable_across_regeneration() -> None:
    inspection = _inspection()

    first = generate_modelo_workspace_field_manifest_for_inspection(inspection)
    second = generate_modelo_workspace_field_manifest_for_inspection(inspection)

    assert first == second
    assert first.manifest_digest == second.manifest_digest


def test_inspection_manifest_digest_differs_from_the_snapshot_manifest_for_the_same_coordinate() -> None:
    """Two distinct authority claims over the identical (modelo, revision) never collide."""
    snapshot_manifest = _manifest()
    inspection_manifest = _inspection_manifest()

    assert snapshot_manifest.manifest_digest != inspection_manifest.manifest_digest
    assert snapshot_manifest.traversal_roots != inspection_manifest.traversal_roots


def test_inspection_capture_is_singleflight_and_current_against_its_own_coordinate() -> None:
    inspection = _inspection()

    first = capture_modelo_workspace_manifest_for_inspection(inspection)
    second = capture_modelo_workspace_manifest_for_inspection(inspection)

    assert first.generation == second.generation
    assert first.comparison_domain == second.comparison_domain

    current = read_modelo_workspace_manifest_current_coordinate_for_inspection(inspection)
    assert first.require_current(current) is first


def test_inspection_and_snapshot_manifest_captures_never_share_a_comparison_domain() -> None:
    """The two admissions' captures must never validate against each other's coordinate."""
    inspection_captured = capture_modelo_workspace_manifest_for_inspection(_inspection())
    snapshot_coordinate = read_modelo_workspace_manifest_current_coordinate(_snapshot())

    assert inspection_captured.comparison_domain != snapshot_coordinate.comparison_domain
    with pytest.raises(ModeloWorkspaceManifestCaptureError):
        inspection_captured.require_current(snapshot_coordinate)
