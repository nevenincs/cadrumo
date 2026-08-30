"""Generated, fail-closed public-schema denominator for Modelo Workspace V1."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence, Set
from dataclasses import dataclass
from functools import cache
from secrets import token_bytes
from threading import RLock
from types import NoneType, UnionType
from typing import Annotated, Literal, TypeAliasType, TypeGuard, Union, cast, get_args, get_origin, get_type_hints

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic.fields import FieldInfo

from ...core.models import STRICT_FROZEN_CONFIG
from ...core.aggregation import BindingSourceKind
from ...core.hashing import content_hash_hex
from ...core.errors.hierarchy import CadrumoError
from ...core.identity import ContentDigest
from ...domain.calculations.registry.bindings import selector_model_for_source
from ...domain.calculations.registry.export import derive_export_layouts_from_bindings
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.calculations.registry.static_inspection import RegistryRevisionInspection
from .workspace_models import ModeloWorkspaceSchemaClassification

_MANIFEST_VERSION = 1
_manifest_capture_process_pid = os.getpid()
_manifest_capture_process_nonce = token_bytes(32)
_manifest_capture_domains: set[str] = set()
_manifest_capture_lock = RLock()
_manifest_capture_generations: dict[str, tuple[tuple[str, ...], int]] = {}
_manifest_capture_generation = 0
_REGISTRY_ROOT_FIELDS = frozenset(
    {
        "modelo",
        "revision",
        "filing_period",
        "filing_year",
        "period",
        "legal",
        "sources",
        "extraction_profiles",
        "live_cross_references",
        "workbook_parity_refs",
        "verification_expectations",
        "application_links",
        "deadline_windows",
        "filing_schedules",
        "constructs",
        "dependency_classifications",
        "convenio",
        "supplementary_ordenes",
    }
)

# RegistryRevisionInspection deliberately excludes filing-grade content
# (calculation, materialization, verification, filing state) -- it "cannot
# calculate, render, or file anything" (static_inspection.py). Its top-level
# fields are therefore a much smaller, structurally distinct denominator from
# RegistrySnapshot's, not a subset reachable by reusing _REGISTRY_ROOT_FIELDS.
_INSPECTION_ROOT_FIELDS = frozenset(
    {
        "modelo_id",
        "revision_id",
        "review_status",
        "family_dispositions",
        "source_root",
        "revision_source_refs",
        "sources",
        "source_ref_ids",
        "legal_ref_ids",
        "casilla_ids",
        "casilla_sections",
        "binding_ids",
        "projection_endpoints",
        "formulas",
        "parameters",
        "bindings",
        "relations",
        "workbook_parity_refs",
        "live_cross_references",
    }
)

type _Path = Annotated[
    str,
    Field(min_length=1, max_length=512, pattern=r"^[A-Za-z][A-Za-z0-9_.=<>,|-]*$"),
]
type _SchemaType = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z][A-Za-z0-9_]*$")]
type _Owner = Literal[
    "application.modelo.workspace",
    "application.modelo.work_review",
    "domain.calculations.registry",
]
type _Reason = Literal[
    "generated_export_layout",
    "registry_declaration",
    "review_projection",
    "selector_configuration",
]
type _Destination = Literal[
    "ModeloWorkspaceApplicabilityReferenceV1",
    "ModeloWorkspaceBindingReferenceV1",
    "ModeloWorkspaceCasillaReferenceV1",
    "ModeloWorkspaceConstraintReferenceV1",
    "ModeloWorkspaceContinuityReferenceV1",
    "ModeloWorkspaceExportExposureReferenceV1",
    "ModeloWorkspaceExportFieldReferenceV1",
    "ModeloWorkspaceFormulaOperandReferenceV1",
    "ModeloWorkspaceFormulaReferenceV1",
    "ModeloWorkspaceParameterReferenceV1",
    "ModeloWorkspaceRelationEndpointReferenceV1",
    "ModeloWorkspaceRelationReferenceV1",
]
type _NodeKind = Literal["leaf", "union_branch"]


class _ManifestModel(BaseModel):
    """Common strict and immutable posture for manifest records."""

    model_config = STRICT_FROZEN_CONFIG


class ModeloWorkspaceFieldManifestEntryV1(_ManifestModel):
    """One reachable public-schema leaf or discriminated branch disposition."""

    path: _Path
    schema_type: _SchemaType
    node_kind: _NodeKind
    classification: ModeloWorkspaceSchemaClassification
    destination: _Destination | None = None
    owner: _Owner | None = None
    reason: _Reason | None = None

    @model_validator(mode="after")
    def _require_classification_metadata(self) -> ModeloWorkspaceFieldManifestEntryV1:
        projected = self.classification is ModeloWorkspaceSchemaClassification.PROJECTED
        if projected != (self.destination is not None):
            raise ValueError("projected Workspace fields require exactly one typed destination")
        if projected != (self.owner is None and self.reason is None):
            raise ValueError("only derived or backend Workspace fields may name owner and reason")
        if not projected and (self.owner is None or self.reason is None):
            raise ValueError("derived or backend Workspace fields require a bounded owner and reason")
        return self


class ModeloWorkspaceFieldManifestV1(_ManifestModel):
    """Deterministic complete classification over the public registry type denominator."""

    manifest_version: Literal[1] = _MANIFEST_VERSION
    traversal_roots: Annotated[tuple[_Path, ...], Field(min_length=1, max_length=128)]
    entries: Annotated[tuple[ModeloWorkspaceFieldManifestEntryV1, ...], Field(min_length=1, max_length=10000)]
    manifest_digest: ContentDigest

    @field_validator("traversal_roots")
    @classmethod
    def _require_sorted_unique_roots(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if value != tuple(sorted(value)) or len(set(value)) != len(value):
            raise ValueError("workspace field manifest roots must be sorted and unique")
        return value

    @field_validator("entries")
    @classmethod
    def _require_sorted_unique_entries(
        cls,
        value: tuple[ModeloWorkspaceFieldManifestEntryV1, ...],
    ) -> tuple[ModeloWorkspaceFieldManifestEntryV1, ...]:
        paths = tuple(entry.path for entry in value)
        if paths != tuple(sorted(paths)) or len(set(paths)) != len(paths):
            raise ValueError("workspace field manifest paths must be sorted and unique")
        return value

    @model_validator(mode="after")
    def _require_reproducible_digest(self) -> ModeloWorkspaceFieldManifestV1:
        if self.manifest_digest != _manifest_digest(self.traversal_roots, self.entries):
            raise ValueError("workspace field manifest digest does not reproduce")
        return self


type _Node = tuple[_SchemaType, _NodeKind]
type _Root = tuple[_Path, type[BaseModel]]


def generate_modelo_workspace_field_manifest(snapshot: RegistrySnapshot) -> ModeloWorkspaceFieldManifestV1:
    """Classify every reachable validated-registry type leaf and tagged branch.

    The snapshot provides the selected revision for the sole export-layout authority;
    selector roots come exclusively from the public registry selector accessor.
    Neither raw authoring data nor Pydantic JSON Schema participates in this walk.
    """
    return _generate_manifest_from_roots(_manifest_roots(snapshot))


def generate_modelo_workspace_field_manifest_for_inspection(
    inspection: RegistryRevisionInspection,
) -> ModeloWorkspaceFieldManifestV1:
    """Classify every reachable STATIC_INSPECTION type leaf and tagged branch.

    A static inspection makes a structurally distinct authority claim
    from a graded snapshot (it "cannot calculate, render, or file anything"),
    so it gets its own complete manifest over its own type universe rather
    than a partial view filtered out of the snapshot-rooted manifest -- the
    same "cannot be represented as one degraded result" principle already
    governing the REGISTRY admission envelope applies identically here.
    ``RegistryRevisionInspection`` carries no full ``ModeloRevision``, so it
    has no export-layout root; selector roots are unchanged, since selector
    models are picked purely by :class:`BindingSourceKind`, independent of
    which admission is reading.
    """
    del inspection  # unused: the walk is over the TYPE, exactly like the snapshot walk
    roots: list[_Root] = [("registry_revision_inspection", RegistryRevisionInspection)]
    roots.extend(_selector_roots())
    return _generate_manifest_from_roots(_sorted_unique_roots(roots))


def _generate_manifest_from_roots(roots: tuple[_Root, ...]) -> ModeloWorkspaceFieldManifestV1:
    nodes: dict[str, _Node] = {}
    for root_path, root_model in roots:
        _walk_annotation(
            annotation=root_model,
            path=root_path,
            nodes=nodes,
            visited=set(),
            active=(),
            discriminator=None,
        )
    entries = tuple(
        _classify_node(path, schema_type, node_kind) for path, (schema_type, node_kind) in sorted(nodes.items())
    )
    root_paths = tuple(path for path, _ in roots)
    return ModeloWorkspaceFieldManifestV1(
        traversal_roots=root_paths,
        entries=entries,
        manifest_digest=_manifest_digest(root_paths, entries),
    )


def validate_modelo_workspace_field_manifest(
    manifest: ModeloWorkspaceFieldManifestV1,
    snapshot: RegistrySnapshot,
) -> ModeloWorkspaceFieldManifestV1:
    """Refuse a manifest that is missing, duplicated, stale, or no longer classified."""
    current = generate_modelo_workspace_field_manifest(snapshot)
    if manifest != current:
        raise ValueError("workspace field manifest is not the current public-schema fixed point")
    return manifest


def validate_modelo_workspace_field_manifest_for_inspection(
    manifest: ModeloWorkspaceFieldManifestV1,
    inspection: RegistryRevisionInspection,
) -> ModeloWorkspaceFieldManifestV1:
    """Refuse a STATIC_INSPECTION manifest that is stale or no longer classified."""
    current = generate_modelo_workspace_field_manifest_for_inspection(inspection)
    if manifest != current:
        raise ValueError("workspace field manifest is not the current static-inspection fixed point")
    return manifest


def _selector_roots() -> tuple[_Root, ...]:
    """Return the admission-agnostic selector roots.

    Purely a function of :class:`BindingSourceKind`, never of a specific
    snapshot or inspection instance, so both admissions share the identical
    set.
    """
    roots: list[_Root] = []
    for source in BindingSourceKind:
        selector_model = selector_model_for_source(source)
        if selector_model is not None:
            roots.append((f"selector.{source.value}", selector_model))
    return tuple(roots)


def _sorted_unique_roots(roots: list[_Root]) -> tuple[_Root, ...]:
    root_paths = tuple(path for path, _ in roots)
    if len(root_paths) != len(set(root_paths)):
        raise ValueError("workspace field manifest has duplicate traversal roots")
    return tuple(sorted(roots, key=lambda root: root[0]))


def _manifest_roots(snapshot: RegistrySnapshot) -> tuple[_Root, ...]:
    roots: list[_Root] = [("registry_snapshot", RegistrySnapshot)]
    roots.extend(_selector_roots())

    generated_layouts = derive_export_layouts_from_bindings(snapshot.revision)
    for layout_type in sorted({type(layout) for layout in generated_layouts}, key=_schema_type_label):
        roots.append((f"derived.export_layout.{_root_type_coordinate(layout_type)}", layout_type))

    root_paths = tuple(path for path, _ in roots)
    if len(root_paths) != len(set(root_paths)):
        raise ValueError("workspace field manifest has duplicate traversal roots")
    return tuple(sorted(roots, key=lambda root: root[0]))


def _walk_annotation(
    *,
    annotation: object,
    path: _Path,
    nodes: dict[str, _Node],
    visited: set[tuple[type[BaseModel], str]],
    active: tuple[type[BaseModel], ...],
    discriminator: str | None,
    record_terminal: bool = True,
) -> None:
    if isinstance(annotation, TypeAliasType) and _is_traversable_type_alias(annotation):
        _walk_annotation(
            annotation=annotation.__value__,
            path=path,
            nodes=nodes,
            visited=visited,
            active=active,
            discriminator=discriminator,
            record_terminal=record_terminal,
        )
        return
    effective_discriminator = discriminator or _annotation_discriminator(annotation)
    unwrapped = _unwrap_annotated(annotation)
    origin = get_origin(unwrapped)
    if origin in (Union, UnionType):
        _walk_union(
            annotation=unwrapped,
            path=path,
            nodes=nodes,
            visited=visited,
            active=active,
            discriminator=effective_discriminator,
        )
        return
    if _is_model_type(unwrapped):
        model_type = unwrapped
        pair = (model_type, path)
        if pair in visited or model_type in active:
            return
        visited.add(pair)
        annotations = _model_annotations(model_type)
        raw_fields = model_type.model_fields
        assert isinstance(raw_fields, dict)
        fields: dict[str, FieldInfo] = {}
        for field_name_raw, field_info_raw in raw_fields.items():
            assert isinstance(field_name_raw, str)
            assert isinstance(field_info_raw, FieldInfo)
            fields[field_name_raw] = field_info_raw
        for field_name, field in fields.items():
            field_annotation = annotations.get(field_name, field.annotation)
            _walk_annotation(
                annotation=field_annotation,
                path=f"{path}.{field_name}",
                nodes=nodes,
                visited=visited,
                active=(*active, model_type),
                discriminator=_field_discriminator(field.discriminator) or _annotation_discriminator(field_annotation),
            )
        return
    if origin is Literal:
        if record_terminal:
            _record_node(nodes, path, _schema_type_label(unwrapped), "leaf")
        return
    if _is_mapping_origin(origin):
        arguments = get_args(unwrapped)
        if len(arguments) != 2:
            raise ValueError(f"workspace field manifest cannot classify mapping at {path}")
        _walk_annotation(
            annotation=arguments[1],
            path=f"{path}.mapping_value",
            nodes=nodes,
            visited=visited,
            active=active,
            discriminator=None,
        )
        return
    if _is_collection_origin(origin):
        _walk_collection(
            arguments=get_args(unwrapped),
            path=path,
            nodes=nodes,
            visited=visited,
            active=active,
        )
        return
    if record_terminal:
        _record_node(nodes, path, _schema_type_label(unwrapped), "leaf")


def _walk_union(
    *,
    annotation: object,
    path: _Path,
    nodes: dict[str, _Node],
    visited: set[tuple[type[BaseModel], str]],
    active: tuple[type[BaseModel], ...],
    discriminator: str | None,
) -> None:
    coordinates: set[str] = set()
    for arm in get_args(annotation):
        coordinate = _union_coordinate(arm, discriminator)
        if coordinate in coordinates:
            raise ValueError(f"workspace field manifest has duplicate union coordinate at {path}")
        coordinates.add(coordinate)
        arm_path = f"{path}.variant={coordinate}"
        _record_node(nodes, arm_path, _schema_type_label(arm), "union_branch")
        if _unwrap_annotated(arm) is not NoneType:
            _walk_annotation(
                annotation=arm,
                path=arm_path,
                nodes=nodes,
                visited=visited,
                active=active,
                discriminator=None,
                record_terminal=False,
            )


def _walk_collection(
    *,
    arguments: tuple[object, ...],
    path: _Path,
    nodes: dict[str, _Node],
    visited: set[tuple[type[BaseModel], str]],
    active: tuple[type[BaseModel], ...],
) -> None:
    element_types = tuple(argument for argument in arguments if argument is not Ellipsis)
    if not element_types:
        raise ValueError(f"workspace field manifest cannot classify collection at {path}")
    if len(element_types) == 1:
        _walk_annotation(
            annotation=element_types[0],
            path=f"{path}.collection_item",
            nodes=nodes,
            visited=visited,
            active=active,
            discriminator=None,
        )
        return
    for index, element_type in enumerate(element_types):
        _walk_annotation(
            annotation=element_type,
            path=f"{path}.collection_item{index}",
            nodes=nodes,
            visited=visited,
            active=active,
            discriminator=None,
        )


def _record_node(nodes: dict[str, _Node], path: _Path, schema_type: _SchemaType, node_kind: _NodeKind) -> None:
    current = nodes.get(path)
    node = (schema_type, node_kind)
    if current is not None:
        raise ValueError(f"workspace field manifest has duplicate canonical path {path}")
    nodes[path] = node


def _classify_node(
    path: _Path,
    schema_type: _SchemaType,
    node_kind: _NodeKind,
) -> ModeloWorkspaceFieldManifestEntryV1:
    destination = _projected_destination(path, schema_type, node_kind)
    if destination is not None:
        return ModeloWorkspaceFieldManifestEntryV1(
            path=path,
            schema_type=schema_type,
            node_kind=node_kind,
            classification=ModeloWorkspaceSchemaClassification.PROJECTED,
            destination=destination,
        )
    if path.startswith("derived.export_layout.") or ".export_layouts." in path:
        return _owned_entry(
            path=path,
            schema_type=schema_type,
            node_kind=node_kind,
            classification=ModeloWorkspaceSchemaClassification.DERIVED,
            owner="domain.calculations.registry",
            reason="generated_export_layout",
        )
    if path in ("registry_snapshot.revision.review_status", "registry_revision_inspection.review_status"):
        return _owned_entry(
            path=path,
            schema_type=schema_type,
            node_kind=node_kind,
            classification=ModeloWorkspaceSchemaClassification.DERIVED,
            owner="application.modelo.work_review",
            reason="review_projection",
        )
    if path.startswith("selector."):
        return _owned_entry(
            path=path,
            schema_type=schema_type,
            node_kind=node_kind,
            classification=ModeloWorkspaceSchemaClassification.BACKEND_ONLY,
            owner="domain.calculations.registry",
            reason="selector_configuration",
        )
    if path.startswith("registry_snapshot."):
        top_level = path.removeprefix("registry_snapshot.").split(".", maxsplit=1)[0]
        if top_level not in _REGISTRY_ROOT_FIELDS:
            raise ValueError(f"workspace field manifest cannot classify registry root {top_level!r}")
        return _owned_entry(
            path=path,
            schema_type=schema_type,
            node_kind=node_kind,
            classification=ModeloWorkspaceSchemaClassification.BACKEND_ONLY,
            owner="domain.calculations.registry",
            reason="registry_declaration",
        )
    if path.startswith("registry_revision_inspection."):
        top_level = path.removeprefix("registry_revision_inspection.").split(".", maxsplit=1)[0]
        if top_level not in _INSPECTION_ROOT_FIELDS:
            raise ValueError(f"workspace field manifest cannot classify inspection root {top_level!r}")
        return _owned_entry(
            path=path,
            schema_type=schema_type,
            node_kind=node_kind,
            classification=ModeloWorkspaceSchemaClassification.BACKEND_ONLY,
            owner="domain.calculations.registry",
            reason="registry_declaration",
        )
    raise ValueError(f"workspace field manifest cannot classify path {path!r}")


def _projected_destination(
    path: _Path,
    schema_type: _SchemaType,
    node_kind: _NodeKind,
) -> _Destination | None:
    if path.startswith(("selector.", "derived.export_layout.")):
        return None
    if node_kind == "union_branch" and _is_workspace_formula_operand(path, schema_type):
        return "ModeloWorkspaceFormulaOperandReferenceV1"
    if schema_type == "ApplicabilityRuleId":
        return "ModeloWorkspaceApplicabilityReferenceV1"
    if ".constraint" in path and schema_type == "CasillaId":
        return "ModeloWorkspaceConstraintReferenceV1"
    if schema_type == "ContinuidadId":
        return "ModeloWorkspaceContinuityReferenceV1"
    if ".export" in path and schema_type in {"CasillaId", "ExportFieldId"}:
        return "ModeloWorkspaceExportExposureReferenceV1"
    if ".relation" in path and schema_type in {"BindingId", "CasillaId"}:
        return "ModeloWorkspaceRelationEndpointReferenceV1"
    destinations: dict[_SchemaType, _Destination] = {
        "ApplicabilityRuleId": "ModeloWorkspaceApplicabilityReferenceV1",
        "BindingId": "ModeloWorkspaceBindingReferenceV1",
        "CasillaId": "ModeloWorkspaceCasillaReferenceV1",
        "ContinuidadId": "ModeloWorkspaceContinuityReferenceV1",
        "ExportFieldId": "ModeloWorkspaceExportFieldReferenceV1",
        "FormulaId": "ModeloWorkspaceFormulaReferenceV1",
        "ParameterId": "ModeloWorkspaceParameterReferenceV1",
        "RelationId": "ModeloWorkspaceRelationReferenceV1",
    }
    return destinations.get(schema_type)


def _is_workspace_formula_operand(path: _Path, schema_type: _SchemaType) -> bool:
    """Return whether one formula-expression branch has a Workspace operand DTO.

    Formula expressions are permissive compiler nodes.  Only their canonical
    identity leaves and literal leaf become Workspace operand references;
    optional absence, operators, and dispatch containers remain registry-owned
    implementation grammar rather than being mislabelled as a DTO projection.
    """
    if ".expression." not in path:
        return False
    operand_fields: dict[str, frozenset[_SchemaType]] = {
        "casilla_id": frozenset({"CasillaId"}),
        "binding": frozenset({"BindingId"}),
        "date_binding": frozenset({"BindingId"}),
        "parameter": frozenset({"ParameterId"}),
        "relation": frozenset({"RelationId"}),
        "literal": frozenset({"Decimal"}),
    }
    return any(
        f".expression.{field_name}." in path and schema_type in schema_types
        for field_name, schema_types in operand_fields.items()
    )


def _owned_entry(
    *,
    path: _Path,
    schema_type: _SchemaType,
    node_kind: _NodeKind,
    classification: ModeloWorkspaceSchemaClassification,
    owner: _Owner,
    reason: _Reason,
) -> ModeloWorkspaceFieldManifestEntryV1:
    return ModeloWorkspaceFieldManifestEntryV1(
        path=path,
        schema_type=schema_type,
        node_kind=node_kind,
        classification=classification,
        owner=owner,
        reason=reason,
    )


@cache
def _model_annotations(model_type: type[BaseModel]) -> dict[str, object]:
    return cast(dict[str, object], get_type_hints(model_type, include_extras=True))


def _unwrap_annotated(annotation: object) -> object:
    while get_origin(annotation) is Annotated:
        annotation = get_args(annotation)[0]
    return annotation


def _field_discriminator(discriminator: object) -> str | None:
    if discriminator is None:
        return None
    if isinstance(discriminator, str):
        return discriminator
    raise ValueError("workspace field manifest supports only string discriminators")


def _annotation_discriminator(annotation: object) -> str | None:
    if get_origin(annotation) is not Annotated:
        return None
    for metadata in get_args(annotation)[1:]:
        discriminator = getattr(metadata, "discriminator", None)
        if discriminator is not None:
            return _field_discriminator(discriminator)
    return None


def _union_coordinate(annotation: object, discriminator: str | None) -> str:
    if discriminator is None:
        return f"union={_schema_type_label(annotation)}"
    unwrapped = _unwrap_annotated(annotation)
    if not _is_model_type(unwrapped):
        raise ValueError("workspace discriminated union arm must be a Pydantic model")
    discriminator_annotation = _model_annotations(unwrapped).get(discriminator)
    if discriminator_annotation is None or get_origin(_unwrap_annotated(discriminator_annotation)) is not Literal:
        raise ValueError("workspace discriminated union arm must declare a Literal discriminator")
    values = get_args(_unwrap_annotated(discriminator_annotation))
    if len(values) != 1 or not isinstance(values[0], (str, int)):
        raise ValueError("workspace discriminated union arm must declare one stable scalar discriminator")
    return f"{discriminator}={values[0]}"


def _is_mapping_origin(origin: object) -> bool:
    return origin is not None and isinstance(origin, type) and issubclass(origin, Mapping)


def _is_collection_origin(origin: object) -> bool:
    return origin is not None and isinstance(origin, type) and issubclass(origin, (Sequence, Set))


def _is_model_type(annotation: object) -> TypeGuard[type[BaseModel]]:
    return isinstance(annotation, type) and issubclass(annotation, BaseModel)


def _is_traversable_type_alias(annotation: TypeAliasType) -> bool:
    value = _unwrap_annotated(annotation.__value__)
    origin = get_origin(value)
    return (
        origin in (Union, UnionType)
        or _is_model_type(value)
        or _is_mapping_origin(origin)
        or _is_collection_origin(origin)
    )


def _schema_type_label(annotation: object) -> _SchemaType:
    unwrapped = _unwrap_annotated(annotation)
    if isinstance(unwrapped, TypeAliasType):
        return unwrapped.__name__
    if unwrapped is NoneType:
        return "NoneType"
    if isinstance(unwrapped, type):
        label = unwrapped.__name__.lstrip("_")
        if label and label[0].isalpha() and label.replace("_", "").isalnum():
            return label
    origin = get_origin(unwrapped)
    if origin is Literal:
        return "Literal"
    if origin is not None:
        return _schema_type_label(origin)
    raise ValueError(f"workspace field manifest cannot name public schema type {unwrapped!r}")


def _root_type_coordinate(model_type: type[BaseModel]) -> str:
    coordinate = _schema_type_label(model_type)
    return coordinate[0].lower() + coordinate[1:]


def _manifest_digest(
    roots: tuple[_Path, ...],
    entries: tuple[ModeloWorkspaceFieldManifestEntryV1, ...],
) -> ContentDigest:
    return content_hash_hex(
        {
            "manifest_version": _MANIFEST_VERSION,
            "traversal_roots": roots,
            "entries": [entry.model_dump(mode="json") for entry in entries],
        }
    )


class ModeloWorkspaceManifestCaptureError(CadrumoError, RuntimeError):
    """Raised when a field manifest cannot be captured over one stable window."""


@dataclass(frozen=True, slots=True)
class ModeloWorkspaceManifestCapture:
    """One generated field manifest and its currentness coordinate.

    ``manifest`` is exactly what the sole walker produced; the capture never
    re-walks the schema to describe what it already holds. The snapshot
    coordinate and process incarnation are folded into the opaque comparison
    domain and never exposed.
    """

    manifest: ModeloWorkspaceFieldManifestV1
    comparison_domain: str
    generation: int

    def require_current(self, current: ModeloWorkspaceManifestCurrentCoordinate) -> ModeloWorkspaceManifestCapture:
        """Refuse a currentness comparison outside this owner process domain."""
        _require_manifest_process_domain(self.comparison_domain)
        current.require_current(self)
        return self


@dataclass(frozen=True, slots=True)
class ModeloWorkspaceManifestCurrentCoordinate:
    """Opaque same-process coordinate for one manifest owner scope."""

    comparison_domain: str
    generation: int

    def require_current(self, captured: ModeloWorkspaceManifestCapture) -> ModeloWorkspaceManifestCurrentCoordinate:
        """Require a capture from this exact owner scope and process incarnation."""
        _require_manifest_process_domain(self.comparison_domain)
        _require_manifest_process_domain(captured.comparison_domain)
        if self.comparison_domain != captured.comparison_domain:
            raise ModeloWorkspaceManifestCaptureError(
                translated_message="errors.refused.modelo_workspace_manifest_capture_not_current",
                context={"reason": "distinct_owner_scope"},
            )
        if self.generation != captured.generation:
            raise ModeloWorkspaceManifestCaptureError(
                translated_message="errors.refused.modelo_workspace_manifest_capture_not_current",
                context={"reason": "capture_superseded"},
            )
        return self


def _require_manifest_process_domain(domain: str) -> None:
    """Refuse a coordinate domain not minted in this process incarnation."""
    if _manifest_capture_process_pid != os.getpid():
        raise ModeloWorkspaceManifestCaptureError(
            translated_message="errors.refused.modelo_workspace_manifest_capture_not_current",
            context={"reason": "forked_process"},
        )
    with _manifest_capture_lock:
        known = domain in _manifest_capture_domains
    if not known:
        raise ModeloWorkspaceManifestCaptureError(
            translated_message="errors.refused.modelo_workspace_manifest_capture_not_current",
            context={"reason": "foreign_process_incarnation"},
        )


def _manifest_comparison_domain(snapshot: RegistrySnapshot) -> str:
    """Mint the non-persisted coordinate domain for one manifest owner scope."""
    domain = content_hash_hex(
        {
            "owner": "application.modelo.workspace_manifest",
            "namespace": "modelo.workspace_field_manifest",
            "modelo": str(snapshot.modelo.id),
            "revision": str(snapshot.revision.id),
            "filing_year": snapshot.filing_year,
            "period": str(snapshot.period),
            "process_incarnation": _manifest_capture_process_nonce.hex(),
        }
    )
    with _manifest_capture_lock:
        _manifest_capture_domains.add(domain)
    return domain


def _inspection_manifest_comparison_domain(inspection: RegistryRevisionInspection) -> str:
    """Mint the non-persisted coordinate domain for one STATIC_INSPECTION manifest scope.

    ``RegistryRevisionInspection`` "intentionally carries neither a filing
    year nor a period" (static_inspection.py), so this domain is keyed by
    modelo and revision alone -- there is no filing_year/period to fold in.
    """
    domain = content_hash_hex(
        {
            "owner": "application.modelo.workspace_manifest",
            "namespace": "modelo.workspace_field_manifest.static_inspection",
            "modelo": str(inspection.modelo_id),
            "revision": str(inspection.revision_id),
            "process_incarnation": _manifest_capture_process_nonce.hex(),
        }
    )
    with _manifest_capture_lock:
        _manifest_capture_domains.add(domain)
    return domain


def _manifest_generation_for(domain: str, observation: tuple[str, ...]) -> int:
    """Assign one injective, order-preserving generation per distinct observation."""
    global _manifest_capture_generation
    with _manifest_capture_lock:
        recorded = _manifest_capture_generations.get(domain)
        if recorded is not None and recorded[0] == observation:
            return recorded[1]
        _manifest_capture_generation += 1
        _manifest_capture_generations[domain] = (observation, _manifest_capture_generation)
        return _manifest_capture_generation


def read_modelo_workspace_manifest_current_coordinate(
    snapshot: RegistrySnapshot,
) -> ModeloWorkspaceManifestCurrentCoordinate:
    """Return the typed current coordinate for same-domain capture validation."""
    manifest = generate_modelo_workspace_field_manifest(snapshot)
    domain = _manifest_comparison_domain(snapshot)
    return ModeloWorkspaceManifestCurrentCoordinate(
        comparison_domain=domain,
        generation=_manifest_generation_for(domain, (str(manifest.manifest_digest),)),
    )


def capture_modelo_workspace_manifest(snapshot: RegistrySnapshot) -> ModeloWorkspaceManifestCapture:
    """Generate one manifest and pair it with the coordinate of that same walk.

    The walk is atomic by construction: the sole generating authority runs once
    and its own digest becomes the observation, so no second walk can pair a
    manifest with a coordinate derived from different schema state.
    """
    manifest = generate_modelo_workspace_field_manifest(snapshot)
    domain = _manifest_comparison_domain(snapshot)
    return ModeloWorkspaceManifestCapture(
        manifest=manifest,
        comparison_domain=domain,
        generation=_manifest_generation_for(domain, (str(manifest.manifest_digest),)),
    )


def read_modelo_workspace_manifest_current_coordinate_for_inspection(
    inspection: RegistryRevisionInspection,
) -> ModeloWorkspaceManifestCurrentCoordinate:
    """Return the typed current coordinate for same-domain STATIC_INSPECTION capture validation."""
    manifest = generate_modelo_workspace_field_manifest_for_inspection(inspection)
    domain = _inspection_manifest_comparison_domain(inspection)
    return ModeloWorkspaceManifestCurrentCoordinate(
        comparison_domain=domain,
        generation=_manifest_generation_for(domain, (str(manifest.manifest_digest),)),
    )


def capture_modelo_workspace_manifest_for_inspection(
    inspection: RegistryRevisionInspection,
) -> ModeloWorkspaceManifestCapture:
    """Generate one STATIC_INSPECTION manifest and pair it with the coordinate of that same walk."""
    manifest = generate_modelo_workspace_field_manifest_for_inspection(inspection)
    domain = _inspection_manifest_comparison_domain(inspection)
    return ModeloWorkspaceManifestCapture(
        manifest=manifest,
        comparison_domain=domain,
        generation=_manifest_generation_for(domain, (str(manifest.manifest_digest),)),
    )


__all__ = [
    "ModeloWorkspaceFieldManifestEntryV1",
    "ModeloWorkspaceFieldManifestV1",
    "ModeloWorkspaceManifestCapture",
    "ModeloWorkspaceManifestCaptureError",
    "ModeloWorkspaceManifestCurrentCoordinate",
    "capture_modelo_workspace_manifest",
    "capture_modelo_workspace_manifest_for_inspection",
    "generate_modelo_workspace_field_manifest",
    "generate_modelo_workspace_field_manifest_for_inspection",
    "read_modelo_workspace_manifest_current_coordinate",
    "read_modelo_workspace_manifest_current_coordinate_for_inspection",
    "validate_modelo_workspace_field_manifest",
    "validate_modelo_workspace_field_manifest_for_inspection",
]
