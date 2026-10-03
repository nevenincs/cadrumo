"""Evidence-backed split/merge boundaries, never identity or value conversions."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from datetime import date
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, Protocol

from pydantic import BeforeValidator, Field, model_validator

from cadrumo.core.identity.continuidad import ContinuidadId

from ....core.errors.hierarchy import pydantic_validation_boundary
from .errors import RegistryValidationError
from .ids import RevisionId
from .period_selector_overlap import period_selectors_overlap
from .schema_base import LegalRefs, RegistryModel, SourceRefs, coerce_enum_member
from .schema_references import PeriodSelector, SourceReference

if TYPE_CHECKING:
    from .schema import ModeloDefinition, ModeloRevision


class EndpointSourceContext(Protocol):
    """Minimum typed endpoint surface required by source-context validation."""

    id: RevisionId
    valid_from: date
    valid_to: date | None
    period_selector: PeriodSelector


class CasillaStructuralKind(StrEnum):
    """The two approved shapes between distinct identities."""

    SPLIT = "split"
    MERGE = "merge"


class CasillaStructuralSuccession(RegistryModel):
    """One target-owned relationship with separately cited official endpoints."""

    id: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
    kind: Annotated[CasillaStructuralKind, BeforeValidator(coerce_enum_member(CasillaStructuralKind))]
    from_revision: RevisionId
    to_revision: RevisionId
    source_lineages: tuple[ContinuidadId, ...] = Field(min_length=1)
    target_lineages: tuple[ContinuidadId, ...] = Field(min_length=1)
    legal_refs: LegalRefs
    from_source_refs: SourceRefs
    to_source_refs: SourceRefs
    evidence: str = Field(min_length=1)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _shape(self) -> CasillaStructuralSuccession:
        return _validate_structural_succession_shape(self)


def _validate_structural_succession_shape(
    relation: CasillaStructuralSuccession,
) -> CasillaStructuralSuccession:
    sources, targets = _structural_endpoint_sets(relation)
    _validate_distinct_structural_endpoints(sources, targets)
    _validate_split_or_merge_cardinality(relation.kind, sources, targets)
    _validate_structural_revision_boundary(relation)
    _validate_structural_evidence(relation)
    return relation


def _structural_endpoint_sets(
    relation: CasillaStructuralSuccession,
) -> tuple[set[ContinuidadId], set[ContinuidadId]]:
    sources, targets = set(relation.source_lineages), set(relation.target_lineages)
    if len(sources) != len(relation.source_lineages) or len(targets) != len(relation.target_lineages):
        raise RegistryValidationError("structural succession endpoint sets must be duplicate-free")
    return sources, targets


def _validate_distinct_structural_endpoints(
    sources: set[ContinuidadId],
    targets: set[ContinuidadId],
) -> None:
    if sources & targets:
        raise RegistryValidationError("structural succession requires distinct source and target identities")


def _validate_split_or_merge_cardinality(
    kind: CasillaStructuralKind,
    sources: set[ContinuidadId],
    targets: set[ContinuidadId],
) -> None:
    valid = (
        (len(sources) == 1 and len(targets) >= 2)
        if kind is CasillaStructuralKind.SPLIT
        else (len(sources) >= 2 and len(targets) == 1)
    )
    if not valid:
        raise RegistryValidationError("structural succession must be one-to-many split or many-to-one merge")


def _validate_structural_revision_boundary(relation: CasillaStructuralSuccession) -> None:
    if relation.from_revision == relation.to_revision:
        raise RegistryValidationError("structural succession must span different revisions")


def _validate_structural_evidence(relation: CasillaStructuralSuccession) -> None:
    if (
        not relation.legal_refs
        or not relation.from_source_refs
        or not relation.to_source_refs
        or not relation.evidence.strip()
    ):
        raise RegistryValidationError("structural succession requires legal and official evidence for both endpoints")


def endpoint_source_context_failures(
    prefix: str,
    *,
    endpoint: EndpointSourceContext,
    enrolled_source_ids: tuple[str, ...],
    source_ids: SourceRefs,
    sources: Mapping[str, SourceReference],
) -> tuple[str, ...]:
    """Validate exact source membership and temporal scope for one endpoint."""
    enrolled = set(enrolled_source_ids)
    failures: list[str] = []
    for source_id in source_ids:
        source = sources.get(source_id)
        if source is None:
            continue
        scope = f"{prefix} endpoint {endpoint.id!r} source {source_id!r}"
        if source_id not in enrolled:
            failures.append(f"{scope} is not enrolled for this modelo or endpoint edition")
        if not source.applies_across(endpoint.valid_from, endpoint.valid_to):
            failures.append(f"{scope} does not apply within the endpoint edition's validity window")
        if source.period_selector is not None and not period_selectors_overlap(
            source.period_selector, endpoint.period_selector
        ):
            failures.append(f"{scope} does not apply to the endpoint edition's filing periods")
    return tuple(failures)


def structural_succession_failures(modelo: ModeloDefinition) -> tuple[str, ...]:
    """Validate ownership, exact endpoints, lifecycle and the independently declared edge.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.schema.ModeloDefinition`.
    """
    if not any(revision.casilla_structural_successions for revision in modelo.revisions.values()):
        return ()
    # Local imports keep the schema's own after-validator free of import cycles.
    from .casilla_lineage_totality import judging_predecessor
    from .revision_order import ordered_revisions

    ordered = ordered_revisions(modelo)
    positions = {revision.id: index for index, revision in enumerate(ordered)}
    counts = {
        revision.id: Counter(row.continuidad_id for row in revision.casillas if row.continuidad_id is not None)
        for revision in ordered
    }
    owned: set[tuple[str, str, str]] = set()
    identifiers: set[str] = set()
    failures: list[str] = []
    for index, revision in enumerate(ordered):
        predecessor = judging_predecessor(modelo, ordered, index)
        for relation in revision.casilla_structural_successions:
            prefix, source = _structural_relationship_header(
                modelo,
                revision,
                relation,
                predecessor=predecessor,
                index=index,
                positions=positions,
                identifiers=identifiers,
                failures=failures,
            )
            if source is None:
                continue
            _append_structural_relationship_lineage_failures(
                relation,
                revision,
                source,
                prefix=prefix,
                index=index,
                ordered=ordered,
                positions=positions,
                counts=counts,
                owned=owned,
                failures=failures,
            )
            _append_structural_relationship_lifecycle_failures(
                relation,
                revision,
                source,
                ordered=ordered,
                prefix=prefix,
                failures=failures,
            )
    return tuple(failures)


def _structural_relationship_header(
    modelo: ModeloDefinition,
    revision: ModeloRevision,
    relation: CasillaStructuralSuccession,
    *,
    predecessor: ModeloRevision | None,
    index: int,
    positions: Mapping[RevisionId, int],
    identifiers: set[str],
    failures: list[str],
) -> tuple[str, ModeloRevision | None]:
    from .revision_order import revisions_coexist

    prefix = f"structural succession {modelo.id}/{revision.id}/{relation.id}: "
    if relation.id in identifiers:
        failures.append(prefix + "duplicate relationship identifier")
    identifiers.add(relation.id)
    source = modelo.revisions.get(relation.from_revision)
    if relation.to_revision != revision.id:
        failures.append(prefix + "relationship must be authored only in its target revision")
    if source is None or relation.to_revision not in modelo.revisions:
        failures.append(prefix + "unknown endpoint revision")
        return prefix, None
    if predecessor is None or predecessor.id != source.id or revisions_coexist(source, revision):
        failures.append(prefix + "boundary must match the non-coexisting predecessor succession")
    if positions[source.id] >= index:
        failures.append(prefix + "source revision must precede target revision")
    return prefix, source


def _append_structural_relationship_lineage_failures(
    relation: CasillaStructuralSuccession,
    revision: ModeloRevision,
    source: ModeloRevision,
    *,
    prefix: str,
    index: int,
    ordered: tuple[ModeloRevision, ...],
    positions: Mapping[RevisionId, int],
    counts: Mapping[RevisionId, Counter[ContinuidadId]],
    owned: set[tuple[str, str, str]],
    failures: list[str],
) -> None:
    _append_structural_endpoint_lineage_failures(
        "source",
        source,
        relation.source_lineages,
        other_revisions=ordered[positions[source.id] + 1 :],
        prefix=prefix,
        counts=counts,
        owned=owned,
        failures=failures,
    )
    _append_structural_endpoint_lineage_failures(
        "target",
        revision,
        relation.target_lineages,
        other_revisions=ordered[:index],
        prefix=prefix,
        counts=counts,
        owned=owned,
        failures=failures,
    )


def _append_structural_endpoint_lineage_failures(
    side: str,
    endpoint: ModeloRevision,
    lineages: tuple[ContinuidadId, ...],
    *,
    other_revisions: tuple[ModeloRevision, ...],
    prefix: str,
    counts: Mapping[RevisionId, Counter[ContinuidadId]],
    owned: set[tuple[str, str, str]],
    failures: list[str],
) -> None:
    boundary = "end" if side == "source" else "begin"
    for lineage in lineages:
        key = (side, str(endpoint.id), str(lineage))
        if key in owned:
            failures.append(prefix + f"overlapping {side} ownership for {lineage!r}")
        owned.add(key)
        if counts[endpoint.id][lineage] != 1:
            failures.append(prefix + f"{side} endpoint {lineage!r} must resolve to exactly one casilla")
        if any(counts[other.id][lineage] for other in other_revisions):
            failures.append(prefix + f"{side} identity {lineage!r} must {boundary} at boundary")


def _append_structural_relationship_lifecycle_failures(
    relation: CasillaStructuralSuccession,
    revision: ModeloRevision,
    source: ModeloRevision,
    *,
    ordered: tuple[ModeloRevision, ...],
    prefix: str,
    failures: list[str],
) -> None:
    endpoints = set(relation.source_lineages) | set(relation.target_lineages)
    if _has_conflicting_single_chain_lifecycle(ordered, source, revision, endpoints):
        failures.append(prefix + "conflicting single-chain lifecycle declaration")
    if _has_target_classification(relation, revision):
        failures.append(prefix + "structural targets must not duplicate classification in row origin or evidence")
    if _has_conflicting_lineage_attestation(relation, revision, endpoints, source):
        failures.append(prefix + "conflicting lineage attestation")


def _has_conflicting_single_chain_lifecycle(
    ordered: tuple[ModeloRevision, ...],
    source: ModeloRevision,
    revision: ModeloRevision,
    endpoints: set[ContinuidadId],
) -> bool:
    return any(
        evolution.from_revision == source.id
        and evolution.to_revision == revision.id
        and evolution.continuidad_id in endpoints
        for owner in ordered
        for evolution in owner.casilla_continuidad_evolutions
    )


def _has_target_classification(relation: CasillaStructuralSuccession, revision: ModeloRevision) -> bool:
    return any(
        row.continuidad_id in relation.target_lineages
        and (row.continuidad_origin is not None or row.continuidad_evidence is not None)
        for row in revision.casillas
    )


def _has_conflicting_lineage_attestation(
    relation: CasillaStructuralSuccession,
    revision: ModeloRevision,
    endpoints: set[ContinuidadId],
    source: ModeloRevision,
) -> bool:
    return any(
        attestation.continuidad_id in endpoints
        and attestation.from_revision == source.id
        and attestation.to_revision == revision.id
        for attestation in revision.lineage_attestations
    )


def validated_structural_targets(modelo: ModeloDefinition, revision_id: str) -> frozenset[str]:
    """Only valid relationship membership resolves a successor's origin totality.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.schema.ModeloDefinition`.
    """
    if not modelo.revisions[revision_id].casilla_structural_successions:
        return frozenset[str]()
    if structural_succession_failures(modelo):
        return frozenset[str]()
    return frozenset(
        lineage
        for relation in modelo.revisions[revision_id].casilla_structural_successions
        for lineage in relation.target_lineages
    )
