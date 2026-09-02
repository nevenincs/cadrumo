"""Fail-closed validation for authored semantic maps and parser output.

This development-only boundary verifies the two authorities before a later
generator step joins them.  It deliberately validates the structural join but
does not render, derive, or publish export fragments.
"""

from __future__ import annotations

from collections import Counter
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from cadrumo.core.casilla_id import CasillaId
from cadrumo.core.filing_projection_ref import FilingProjectionRef
from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.ids import SourceRefId
from cadrumo.domain.calculations.registry.schema_exports import ProjectionEndpointDeclaration
from cadrumo.domain.calculations.registry.static_inspection import GeneratedArtifactInspection

from ._record_design_ir import (
    AnchorKey,
    RecordDesignIntermediate,
    RecordKey,
    intermediate_anchor_key,
    intermediate_record_key,
)
from ._semantic_map import (
    SemanticMap,
    SemanticMapEntry,
    semantic_anchor_key,
    semantic_record_key,
)
from ._variable_envelope import validate_variable_envelope

__all__ = [
    "SemanticMapAnomalyException",
    "resolve_semantic_map_casilla_tokens",
    "validate_inspection_source_authority",
    "validate_semantic_map",
]


class _StrictModel(BaseModel):
    """Frozen development-tool boundary model with no untyped extras."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class SemanticMapAnomalyException(_StrictModel):
    """A hash-pinned parser or source anomaly noted without changing mapping.

    Exceptions document the limited parser/source anomalies that future
    maintenance may need to explain.  They intentionally contain no anchor,
    coordinate, or semantic fields, and :func:`validate_semantic_map` never
    consults them to waive source, reference, or bijection validation.
    """

    source_ref: SourceRefId
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    category: Literal["parser_anomaly", "source_anomaly"]
    reason: str = Field(min_length=1)


def validate_semantic_map(
    semantic_map: SemanticMap,
    intermediate: RecordDesignIntermediate,
    inspection: GeneratedArtifactInspection,
    *,
    anomaly_exceptions: tuple[SemanticMapAnomalyException, ...] = (),
) -> SemanticMap:
    """Validate a static map through a non-filing revision inspection.

    Static source compilation has no filing context.  The inspection presents
    the selected revision's immutable admission facts without constructing a
    snapshot or crossing the filing/legal-review gate.
    """
    _validate_scope(semantic_map, intermediate, modelo_id=inspection.modelo_id)
    validate_inspection_source_authority(intermediate, inspection)
    _validate_anomaly_exceptions(anomaly_exceptions, intermediate)
    _validate_exact_bijection(semantic_map, intermediate)
    _validate_exact_record_bijection(semantic_map, intermediate)
    _validate_variable_envelope_boundary(semantic_map, intermediate)
    resolved_map = resolve_semantic_map_casilla_tokens(
        semantic_map,
        casilla_ids=inspection.casilla_ids,
    )
    _validate_entry_references(
        resolved_map,
        casilla_ids=inspection.casilla_ids,
        binding_ids=inspection.binding_ids,
        projection_endpoints=inspection.projection_endpoints,
        legal_ref_ids=inspection.legal_ref_ids,
        source_refs=frozenset(inspection.sources),
    )
    return resolved_map


def resolve_semantic_map_casilla_tokens(
    semantic_map: SemanticMap,
    *,
    casilla_ids: frozenset[CasillaId],
) -> SemanticMap:
    """Compile official numeric box tokens to exact revision-owned identifiers.

    An authored semantic map may carry the numeric token printed by an official
    record design without the registry's leading zeroes.  The selected revision
    remains the sole identity authority: an exact identifier is preserved, and
    a numeric token is left-padded only when exactly one unqualified declared
    identifier can be obtained by adding zeroes to its left.  Qualified or
    otherwise non-numeric identities are never rewritten, so segment ownership
    cannot be inferred from a nearby-looking token.
    """
    resolved_entries: list[SemanticMapEntry] = []
    for entry in semantic_map.entries:
        token = entry.casilla_id
        if token is None or token in casilla_ids:
            resolved_entries.append(entry)
            continue

        candidates = _left_padded_casilla_candidates(token, casilla_ids=casilla_ids)
        if len(candidates) == 1:
            resolved_entries.append(entry.model_copy(update={"casilla_id": candidates[0]}))
            continue
        if candidates:
            raise RegistryValidationError(
                f"semantic map export field {entry.export_field_id!r} has ambiguous numeric casilla token "
                f"{token!r}; target revision left-padding candidates are {tuple(candidates)!r}",
            )
        raise RegistryValidationError(
            f"semantic map export field {entry.export_field_id!r} references unknown target-revision "
            f"casilla {token!r}; no unique left-padding resolution exists",
        )

    return semantic_map.model_copy(update={"entries": tuple(resolved_entries)})


def _left_padded_casilla_candidates(
    token: CasillaId,
    *,
    casilla_ids: frozenset[CasillaId],
) -> tuple[CasillaId, ...]:
    """Return declared unqualified ids produced solely by left-zero padding."""
    if not token.isdecimal():
        return ()
    return tuple(
        sorted(
            candidate
            for candidate in casilla_ids
            if candidate.isdecimal()
            and len(candidate) > len(token)
            and candidate.endswith(token)
            and set(candidate[: -len(token)]) == {"0"}
        ),
    )


def _validate_scope(
    semantic_map: SemanticMap,
    intermediate: RecordDesignIntermediate,
    *,
    modelo_id: str,
) -> None:
    if semantic_map.modelo != modelo_id:
        raise RegistryValidationError(
            f"semantic map modelo {semantic_map.modelo!r} does not match target revision modelo {modelo_id!r}",
        )
    if semantic_map.design_epoch != intermediate.source.design_epoch:
        raise RegistryValidationError(
            f"semantic map design epoch {semantic_map.design_epoch!r} does not match parser "
            f"design epoch {intermediate.source.design_epoch!r}",
        )
    if semantic_map.source_ref != intermediate.source.source_ref:
        raise RegistryValidationError(
            f"semantic map source {semantic_map.source_ref!r} does not match parser intermediate source "
            f"{intermediate.source.source_ref!r}",
        )
    if semantic_map.source_sha256 != intermediate.source.source_sha256:
        raise RegistryValidationError(
            "semantic map SHA-256 does not match parser intermediate source",
        )


def validate_inspection_source_authority(
    intermediate: RecordDesignIntermediate,
    inspection: GeneratedArtifactInspection,
) -> None:
    """Require parser evidence to belong to the selected static revision."""
    source = inspection.sources.get(intermediate.source.source_ref)
    if source is None:
        raise RegistryValidationError(
            f"parser intermediate source {intermediate.source.source_ref!r} is absent from the target "
            "registry source catalogue",
        )
    if source.kind != "record_design":
        raise RegistryValidationError(
            f"parser intermediate source {source.id!r} must resolve to a record-design source",
        )
    if source.sha256 != intermediate.source.source_sha256:
        raise RegistryValidationError(
            f"parser intermediate source {source.id!r} SHA-256 does not match the target registry catalogue",
        )
    if source.record_design_epoch != intermediate.source.design_epoch:
        raise RegistryValidationError(
            f"parser intermediate source {source.id!r} design epoch {intermediate.source.design_epoch!r} "
            "does not match the target registry catalogue",
        )
    if intermediate.source.source_ref not in inspection.revision_source_refs:
        raise RegistryValidationError(
            f"parser intermediate source {intermediate.source.source_ref!r} is not an authority of selected "
            f"revision {inspection.revision_id!r}",
        )


def _validate_anomaly_exceptions(
    anomaly_exceptions: tuple[SemanticMapAnomalyException, ...],
    intermediate: RecordDesignIntermediate,
) -> None:
    seen: set[SemanticMapAnomalyException] = set()
    for exception in anomaly_exceptions:
        if exception in seen:
            raise RegistryValidationError(
                f"duplicate semantic-map anomaly exception for source {exception.source_ref!r}: "
                f"{exception.category} {exception.reason!r}",
            )
        seen.add(exception)
        if exception.source_ref != intermediate.source.source_ref:
            raise RegistryValidationError(
                f"semantic-map anomaly exception source {exception.source_ref!r} does not match parser "
                f"intermediate source {intermediate.source.source_ref!r}",
            )
        if exception.source_sha256 != intermediate.source.source_sha256:
            raise RegistryValidationError(
                f"semantic-map anomaly exception for source {exception.source_ref!r} is not pinned to the "
                "parser intermediate SHA-256",
            )


def _validate_variable_envelope_boundary(
    semantic_map: SemanticMap,
    intermediate: RecordDesignIntermediate,
) -> None:
    """Retain envelopes as distinct, source-pinned composition authorities."""
    fixed_keys = {(sheet.sheet, sheet.record_identity) for sheet in intermediate.sheets}
    envelope_keys = tuple((envelope.sheet, envelope.record_identity) for envelope in intermediate.variable_envelopes)
    duplicate_envelopes = _duplicate_record_keys(envelope_keys)
    if duplicate_envelopes:
        raise RegistryValidationError(
            "parser intermediate contains duplicate variable-envelope identities: "
            f"{_format_record_keys(duplicate_envelopes)}",
        )
    collisions = tuple(sorted(fixed_keys.intersection(envelope_keys)))
    if collisions:
        raise RegistryValidationError(
            "parser intermediate cannot classify one identity as both fixed record and variable envelope: "
            f"{_format_record_keys(collisions)}",
        )
    if not envelope_keys:
        if semantic_map.variable_envelopes:
            raise RegistryValidationError(
                "semantic map declares a variable-envelope contract but parser output contains no variable envelope",
            )
        return
    if len(envelope_keys) != 1:
        raise RegistryValidationError(
            "variable-envelope composition authority admits exactly one parser envelope per design; "
            f"parser output declares {_format_record_keys(envelope_keys)}",
        )
    if len(semantic_map.variable_envelopes) != 1:
        raise RegistryValidationError(
            f"parser envelope {envelope_keys[0][1]!r} requires exactly one reviewed variable-envelope "
            f"semantic contract, found {len(semantic_map.variable_envelopes)}",
        )
    semantic = semantic_map.variable_envelopes[0]
    parser_envelope = intermediate.variable_envelopes[0]
    if semantic.record_identity != parser_envelope.record_identity:
        raise RegistryValidationError(
            f"reviewed variable-envelope contract names {semantic.record_identity!r} but the parser owns "
            f"{parser_envelope.record_identity!r}",
        )
    records_by_anchor = {semantic_record_key(record): record for record in semantic_map.records}
    body_record_ids = tuple(
        records_by_anchor[intermediate_record_key(sheet)].export_record_id for sheet in intermediate.sheets
    )
    validate_variable_envelope(
        semantic,
        parser_envelope,
        modelo=str(semantic_map.modelo),
        source=intermediate.source,
        body_record_ids=body_record_ids,
    )


def _validate_exact_bijection(
    semantic_map: SemanticMap,
    intermediate: RecordDesignIntermediate,
) -> None:
    intermediate_keys = tuple(intermediate_anchor_key(field) for sheet in intermediate.sheets for field in sheet.fields)
    semantic_keys = tuple(semantic_anchor_key(entry.anchor) for entry in semantic_map.entries)
    duplicate_intermediate = _duplicate_anchor_keys(intermediate_keys)
    if duplicate_intermediate:
        raise RegistryValidationError(
            "parser intermediate contains duplicate exact anchors; refusing ambiguous semantic-map join: "
            f"{_format_anchor_keys(duplicate_intermediate)}",
        )
    duplicate_semantic = _duplicate_anchor_keys(semantic_keys)
    if duplicate_semantic:
        raise RegistryValidationError(
            "semantic map contains duplicate exact anchors; refusing ambiguous parser join: "
            f"{_format_anchor_keys(duplicate_semantic)}",
        )

    intermediate_set = set(intermediate_keys)
    semantic_set = set(semantic_keys)
    missing = tuple(sorted(intermediate_set - semantic_set))
    extra = tuple(sorted(semantic_set - intermediate_set))
    if missing or extra:
        details: list[str] = []
        if missing:
            details.append(f"missing semantic entries {_format_anchor_keys(missing)}")
        if extra:
            details.append(f"extra semantic entries {_format_anchor_keys(extra)}")
        raise RegistryValidationError(
            "semantic map must form a complete exact bijection with parser output; " + "; ".join(details),
        )


def _validate_entry_references(
    semantic_map: SemanticMap,
    *,
    casilla_ids: frozenset[str],
    binding_ids: frozenset[str],
    projection_endpoints: tuple[ProjectionEndpointDeclaration, ...],
    legal_ref_ids: frozenset[str],
    source_refs: frozenset[str],
) -> None:
    duplicate_export_ids = _duplicate_string_keys(tuple(str(entry.export_field_id) for entry in semantic_map.entries))
    if duplicate_export_ids:
        raise RegistryValidationError(
            "semantic map contains duplicate canonical export field ids in one generated layout: "
            f"{', '.join(duplicate_export_ids)}",
        )

    _validate_projection_ref_admission(semantic_map, projection_endpoints=projection_endpoints)
    for entry in semantic_map.entries:
        if entry.casilla_id is not None and entry.casilla_id not in casilla_ids:
            raise RegistryValidationError(
                f"semantic map export field {entry.export_field_id!r} references unknown target-revision "
                f"casilla {entry.casilla_id!r}",
            )
        if entry.binding is not None and entry.binding not in binding_ids:
            raise RegistryValidationError(
                f"semantic map export field {entry.export_field_id!r} references unknown target-revision "
                f"binding {entry.binding!r}",
            )
        _validate_catalogue_refs(entry, legal_ref_ids=legal_ref_ids, source_refs=source_refs)


def _validate_projection_ref_admission(
    semantic_map: SemanticMap,
    *,
    projection_endpoints: tuple[ProjectionEndpointDeclaration, ...],
) -> None:
    """Require an exact semantic-map/declaration projection bijection.

    The selected immutable revision owns this declaration index. Map anchors
    remain source evidence, so neither their geometry nor field labels can
    select, repair, or omit a projection identity.
    """
    projection_refs = tuple(
        entry.projection_ref for entry in semantic_map.entries if entry.kind is CasillaFieldKind.PROJECTION
    )
    if any(projection_ref is None for projection_ref in projection_refs):
        raise RegistryValidationError("projection semantic-map entries must carry a typed projection_ref")
    typed_refs = tuple(projection_ref for projection_ref in projection_refs if projection_ref is not None)
    _validate_projection_ref_bijection(typed_refs, projection_endpoints=projection_endpoints)


def _validate_projection_ref_bijection(
    projection_refs: tuple[FilingProjectionRef, ...],
    *,
    projection_endpoints: tuple[ProjectionEndpointDeclaration, ...],
) -> None:
    """Require typed map refs to be the exact selected-revision declaration set."""
    typed_refs = projection_refs
    duplicate_refs = tuple(projection_ref for projection_ref, count in Counter(typed_refs).items() if count > 1)
    if duplicate_refs:
        raise RegistryValidationError(
            "semantic map contains duplicate projection references: "
            f"{tuple(sorted(repr(projection_ref) for projection_ref in duplicate_refs))}",
        )
    admitted = _projection_endpoint_index(projection_endpoints)
    for projection_ref in typed_refs:
        declarations = admitted.get(projection_ref)
        if declarations is None:
            raise RegistryValidationError(
                f"semantic-map projection reference is not admitted by the target revision: {projection_ref!r}",
            )
        if len(declarations) != 1:
            raise RegistryValidationError(
                "semantic-map projection reference is not admitted exactly once by the target revision: "
                f"{projection_ref!r} resolves to {len(declarations)} declarations",
            )
    missing = tuple(sorted(repr(reference) for reference in set(admitted) - set(typed_refs)))
    if missing:
        raise RegistryValidationError(
            "semantic map omits target-revision projection declarations: " + ", ".join(missing),
        )


def _validate_exact_record_bijection(
    semantic_map: SemanticMap,
    intermediate: RecordDesignIntermediate,
) -> None:
    intermediate_keys = tuple(intermediate_record_key(sheet) for sheet in intermediate.sheets)
    semantic_keys = tuple(semantic_record_key(record) for record in semantic_map.records)
    duplicate_intermediate = _duplicate_record_keys(intermediate_keys)
    if duplicate_intermediate:
        raise RegistryValidationError(
            "parser intermediate contains duplicate exact record anchors; refusing ambiguous semantic-map join: "
            f"{_format_record_keys(duplicate_intermediate)}",
        )
    duplicate_semantic = _duplicate_record_keys(semantic_keys)
    if duplicate_semantic:
        raise RegistryValidationError(
            "semantic map contains duplicate exact record anchors; refusing ambiguous parser join: "
            f"{_format_record_keys(duplicate_semantic)}",
        )
    missing = tuple(sorted(set(intermediate_keys) - set(semantic_keys)))
    extra = tuple(sorted(set(semantic_keys) - set(intermediate_keys)))
    if missing or extra:
        details: list[str] = []
        if missing:
            details.append(f"missing semantic record entries {_format_record_keys(missing)}")
        if extra:
            details.append(f"extra semantic record entries {_format_record_keys(extra)}")
        raise RegistryValidationError(
            "semantic map must form a complete exact record bijection with parser output; " + "; ".join(details),
        )


def _validate_catalogue_refs(
    entry: SemanticMapEntry,
    *,
    legal_ref_ids: frozenset[str],
    source_refs: frozenset[str],
) -> None:
    unknown_legal = tuple(sorted(set(entry.legal_refs) - legal_ref_ids))
    if unknown_legal:
        raise RegistryValidationError(
            f"semantic map export field {entry.export_field_id!r} has unresolved legal refs: {unknown_legal!r}",
        )
    unknown_sources = tuple(sorted(set(entry.source_refs) - source_refs))
    if unknown_sources:
        raise RegistryValidationError(
            f"semantic map export field {entry.export_field_id!r} has unresolved source refs: {unknown_sources!r}",
        )


def _projection_endpoint_index(
    projection_endpoints: tuple[ProjectionEndpointDeclaration, ...],
) -> dict[FilingProjectionRef, tuple[ProjectionEndpointDeclaration, ...]]:
    """Index static declarations without giving the map an inferred owner."""
    index: dict[FilingProjectionRef, list[ProjectionEndpointDeclaration]] = {}
    for declaration in projection_endpoints:
        index.setdefault(declaration.projection_ref, []).append(declaration)
    return {projection_ref: tuple(declarations) for projection_ref, declarations in index.items()}


def _duplicate_anchor_keys(keys: tuple[AnchorKey, ...]) -> tuple[AnchorKey, ...]:
    counts = Counter(keys)
    return tuple(sorted(key for key, count in counts.items() if count > 1))


def _duplicate_string_keys(keys: tuple[str, ...]) -> tuple[str, ...]:
    counts = Counter(keys)
    return tuple(sorted(key for key, count in counts.items() if count > 1))


def _duplicate_record_keys(keys: tuple[RecordKey, ...]) -> tuple[RecordKey, ...]:
    counts = Counter(keys)
    return tuple(sorted(key for key, count in counts.items() if count > 1))


def _format_anchor_keys(keys: tuple[AnchorKey, ...]) -> str:
    return ", ".join(
        f"(sheet={sheet!r}, source_row={source_row}, source_cell={source_cell!r}, ordinal={ordinal}, "
        f"record_identity={record_identity!r})"
        for sheet, source_row, source_cell, ordinal, record_identity in keys
    )


def _format_record_keys(keys: tuple[RecordKey, ...]) -> str:
    return ", ".join(f"(sheet={sheet!r}, record_identity={record_identity!r})" for sheet, record_identity in keys)
