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
    from .schema import ModeloDefinition


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
        sources, targets = set(self.source_lineages), set(self.target_lineages)
        if len(sources) != len(self.source_lineages) or len(targets) != len(self.target_lineages):
            raise RegistryValidationError("structural succession endpoint sets must be duplicate-free")
        if sources & targets:
            raise RegistryValidationError("structural succession requires distinct source and target identities")
        valid = (
            (len(sources) == 1 and len(targets) >= 2)
            if self.kind is CasillaStructuralKind.SPLIT
            else (len(sources) >= 2 and len(targets) == 1)
        )
        if not valid:
            raise RegistryValidationError("structural succession must be one-to-many split or many-to-one merge")
        if self.from_revision == self.to_revision:
            raise RegistryValidationError("structural succession must span different revisions")
        if not self.legal_refs or not self.from_source_refs or not self.to_source_refs or not self.evidence.strip():
            raise RegistryValidationError(
                "structural succession requires legal and official evidence for both endpoints"
            )
        return self


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
    """Validate ownership, exact endpoints, lifecycle and the independently declared edge."""
    if not any(revision.casilla_structural_successions for revision in modelo.revisions.values()):
        return ()
    # Local imports keep the schema's own after-validator free of import cycles.
    from .casilla_lineage_totality import judging_predecessor
    from .revision_order import ordered_revisions, revisions_coexist

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
            prefix = f"structural succession {modelo.id}/{revision.id}/{relation.id}: "
            if relation.id in identifiers:
                failures.append(prefix + "duplicate relationship identifier")
            identifiers.add(relation.id)
            source = modelo.revisions.get(relation.from_revision)
            if relation.to_revision != revision.id:
                failures.append(prefix + "relationship must be authored only in its target revision")
            if source is None or relation.to_revision not in modelo.revisions:
                failures.append(prefix + "unknown endpoint revision")
                continue
            if predecessor is None or predecessor.id != source.id or revisions_coexist(source, revision):
                failures.append(prefix + "boundary must match the non-coexisting predecessor succession")
            if positions[source.id] >= index:
                failures.append(prefix + "source revision must precede target revision")
            for side, endpoint, lineages in (
                ("source", source, relation.source_lineages),
                ("target", revision, relation.target_lineages),
            ):
                for lineage in lineages:
                    key = (side, str(endpoint.id), str(lineage))
                    if key in owned:
                        failures.append(prefix + f"overlapping {side} ownership for {lineage!r}")
                    owned.add(key)
                    if counts[endpoint.id][lineage] != 1:
                        failures.append(prefix + f"{side} endpoint {lineage!r} must resolve to exactly one casilla")
                    other_revisions = ordered[positions[source.id] + 1 :] if side == "source" else ordered[:index]
                    if any(counts[other.id][lineage] for other in other_revisions):
                        failures.append(
                            prefix
                            + f"{side} identity {lineage!r} must {'end' if side == 'source' else 'begin'} at boundary"
                        )
            endpoints = set(relation.source_lineages) | set(relation.target_lineages)
            if any(
                evolution.from_revision == source.id
                and evolution.to_revision == revision.id
                and evolution.continuidad_id in endpoints
                for owner in ordered
                for evolution in owner.casilla_continuidad_evolutions
            ):
                failures.append(prefix + "conflicting single-chain lifecycle declaration")
            if any(
                row.continuidad_id in relation.target_lineages
                and (row.continuidad_origin is not None or row.continuidad_evidence is not None)
                for row in revision.casillas
            ):
                failures.append(
                    prefix + "structural targets must not duplicate classification in row origin or evidence"
                )
            if any(
                attestation.continuidad_id in endpoints
                and attestation.from_revision == source.id
                and attestation.to_revision == revision.id
                for attestation in revision.lineage_attestations
            ):
                failures.append(prefix + "conflicting lineage attestation")
    return tuple(failures)


def validated_structural_targets(modelo: ModeloDefinition, revision_id: str) -> frozenset[str]:
    """Only valid relationship membership resolves a successor's origin totality."""
    if not modelo.revisions[revision_id].casilla_structural_successions:
        return frozenset[str]()
    if structural_succession_failures(modelo):
        return frozenset[str]()
    return frozenset(
        lineage
        for relation in modelo.revisions[revision_id].casilla_structural_successions
        for lineage in relation.target_lineages
    )
