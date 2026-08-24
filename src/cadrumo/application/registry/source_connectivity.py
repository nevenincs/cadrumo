"""Deterministic registry-side inputs to the source-connectivity census.

This module projects validated registry authority.  It deliberately does not
reconstruct producer joins or infer legal equivalence from casilla labels and
numbers: those contracts remain owned by ``ModeloRevision`` and its typed
declarations.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from ...core import (
    STRICT_FROZEN_CONFIG,
    BindingSourceKind,
    CasillaId,
    ModeloCalculationRouteId,
    Period,
    SourceConnectivityCensusRow,
    SourceConnectivityDisposition,
    SourceConnectivityExecutableEvidenceRole,
    SourceConnectivityGroundingLocatorKind,
    SourceConnectivityProofAuthority,
)
from ...core.resources import bundled_path
from ...domain.calculations.registry import (
    BindingId,
    DataBindingDefinition,
    FormulaDefinition,
    FormulaId,
    InputKind,
    InputKindValue,
    LegalRefId,
    ModeloId,
    RegistrySnapshot,
    RelationConsumptionChannel,
    RelationDefinition,
    RelationId,
    RevisionId,
    SourceRefId,
    ValidatedRegistryAuthority,
    casillas_by_binding,
    expression_binding_refs,
    expression_casilla_refs,
    expression_relation_refs,
    relation_consumption_channels,
    relation_consumption_index,
    select_revision,
)
from ..aggregation import BindingSourceDisposition
from ..modelo import CALCULATION_ROUTE_SOURCE_DISPOSITIONS

__all__ = [
    "ManualCasillaRequirement",
    "RegistryBindingRecord",
    "RegistryDestinationCandidate",
    "RegistryDestinationRecord",
    "RegistryFormulaRecord",
    "RegistryRelationRecord",
    "RegistrySourceDispositionRecord",
    "SourceConnectivityCensusEntry",
    "SourceConnectivityCensusManifest",
    "derive_registry_binding_records",
    "derive_registry_destination_records",
    "derive_registry_formula_records",
    "derive_registry_relation_records",
    "derive_registry_source_disposition_records",
    "load_source_connectivity_census",
    "validate_census_destination_candidates",
]

type ManualCasillaRequirement = Literal["required", "optional"]
type CapabilityCoverageSelector = Literal[
    "remaining_calculation_helpers",
    "remaining_ingress_surfaces",
    "remaining_row_assemblers",
    "remaining_secure_repositories",
    "remaining_source_ownership",
    "remaining_source_readiness",
]
type RegistryDestinationCandidateKind = Literal["binding_source", "casilla_semantic_role"]


class RegistryDestinationCandidate(BaseModel):
    """Typed registry-resolvable destination candidate, never a lexical inference."""

    model_config = STRICT_FROZEN_CONFIG

    kind: RegistryDestinationCandidateKind
    modelo_id: ModeloId
    revision_id: RevisionId
    filing_year: int = Field(ge=1980, le=2200)
    period: Period
    semantic_role: str | None = Field(default=None, min_length=1, max_length=256)
    source_kind: BindingSourceKind | None = None

    @model_validator(mode="after")
    def _require_kind_payload(self) -> RegistryDestinationCandidate:
        if self.period.filing_year != self.filing_year:
            raise ValueError("registry destination period must carry its declared filing_year")
        if self.kind == "casilla_semantic_role":
            if self.semantic_role is None or self.source_kind is not None:
                raise ValueError("semantic-role destination requires only semantic_role")
        elif self.source_kind is None or self.semantic_role is not None:
            raise ValueError("binding-source destination requires only source_kind")
        return self

    @property
    def identity(self) -> tuple[str, str, str, str, str, str]:
        """Return the canonical typed identity used for one-owner checks."""
        token = self.semantic_role if self.semantic_role is not None else self.source_kind.value
        return (
            self.kind,
            str(self.modelo_id),
            str(self.revision_id),
            str(self.filing_year),
            self.period.registry_token,
            token,
        )


class SourceConnectivityCensusEntry(SourceConnectivityCensusRow):
    """Reviewed census row linked to generated capabilities and advisory destinations."""

    capability_locators: tuple[str, ...] = Field(min_length=1)
    capability_ids: tuple[str, ...] = ()
    capability_selector: CapabilityCoverageSelector | None = None
    expected_capability_digest: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    advisory_destination_refs: tuple[str, ...] = ()
    registry_destination_candidates: tuple[RegistryDestinationCandidate, ...] = ()

    @model_validator(mode="after")
    def _coverage_refs_are_unique(self) -> SourceConnectivityCensusEntry:
        if len(set(self.capability_locators)) != len(self.capability_locators):
            raise ValueError("connectivity census capability locators must be unique within one entry")
        if len(set(self.advisory_destination_refs)) != len(self.advisory_destination_refs):
            raise ValueError("connectivity census advisory destination refs must be unique within one entry")
        destination_ids = tuple(candidate.identity for candidate in self.registry_destination_candidates)
        if len(set(destination_ids)) != len(destination_ids):
            raise ValueError("connectivity census registry destination candidates must be unique within one entry")
        if len(set(self.capability_ids)) != len(self.capability_ids):
            raise ValueError("connectivity census capability ids must be unique within one entry")
        if self.capability_selector is None:
            if not self.capability_ids or self.expected_capability_digest is not None:
                raise ValueError("explicit census coverage requires capability_ids and no expected digest")
        elif self.capability_ids or self.expected_capability_digest is None:
            raise ValueError("selector census coverage requires an expected digest and no explicit capability ids")
        return self


class SourceConnectivityCensusManifest(BaseModel):
    """Versioned reviewed decisions over the generated connectivity inventories."""

    model_config = STRICT_FROZEN_CONFIG

    schema_version: Literal[1]
    census_id: Literal["source-domain-to-casilla-connectivity"]
    entries: tuple[SourceConnectivityCensusEntry, ...] = ()

    @model_validator(mode="after")
    def _candidate_ids_are_unique(self) -> SourceConnectivityCensusManifest:
        candidate_ids = tuple(row.candidate_id for row in self.entries)
        if len(set(candidate_ids)) != len(candidate_ids):
            raise ValueError("source-connectivity census candidate ids must be unique")
        destination_ids = tuple(
            candidate.identity
            for row in self.entries
            for candidate in row.registry_destination_candidates
        )
        if len(set(destination_ids)) != len(destination_ids):
            raise ValueError("source-connectivity registry destinations must have one census owner")
        return self


def load_source_connectivity_census(
    path: Path | None = None,
    *,
    proof_authority: SourceConnectivityProofAuthority | None = None,
) -> SourceConnectivityCensusManifest:
    """Load the canonical TOML census and enforce its closed typed contract."""
    census_path = path or bundled_path("source_connectivity", "census.toml")
    raw = _hydrate_census_tokens(_freeze_toml_arrays(tomllib.loads(census_path.read_text(encoding="utf-8"))))
    context = {} if proof_authority is None else {"source_connectivity_proof_authority": proof_authority}
    return SourceConnectivityCensusManifest.model_validate(raw, context=context)


def validate_census_destination_candidates(
    manifest: SourceConnectivityCensusManifest,
    authority: ValidatedRegistryAuthority,
) -> None:
    """Resolve every destination against its exact law-selected filing coordinate."""
    authority.validate_registry()
    modelos_by_id = {modelo.id: modelo for modelo in authority.modelos}
    for entry in manifest.entries:
        for candidate in entry.registry_destination_candidates:
            modelo = modelos_by_id.get(candidate.modelo_id)
            if modelo is None:
                raise ValueError(
                    f"census destination references absent modelo {candidate.modelo_id}: {entry.candidate_id}"
                )
            try:
                revision = select_revision(
                    modelo,
                    filing_year=candidate.filing_year,
                    period=candidate.period.registry_token,
                )
            except ValueError as error:
                raise ValueError(
                    "census destination filing coordinate is not law-selectable: "
                    f"{candidate.modelo_id}/{candidate.filing_year}/{candidate.period.registry_token}: "
                    f"{entry.candidate_id}"
                ) from error
            if revision.id != candidate.revision_id:
                raise ValueError(
                    "census destination revision does not match its law-selected filing coordinate: "
                    f"declared {candidate.modelo_id}/{candidate.revision_id}, "
                    f"selected {candidate.modelo_id}/{revision.id} for "
                    f"{candidate.filing_year}/{candidate.period.registry_token}: {entry.candidate_id}"
                )
            if candidate.kind == "casilla_semantic_role":
                matches = tuple(
                    casilla for casilla in revision.casillas if casilla.semantic_role == candidate.semantic_role
                )
                if len(matches) > 1:
                    raise ValueError(
                        f"census destination semantic role is ambiguous in {modelo.id}/{revision.id}: "
                        f"{candidate.semantic_role}"
                    )
                if not matches:
                    raise ValueError(
                        f"census destination semantic role is absent from {modelo.id}/{revision.id}: "
                        f"{candidate.semantic_role}"
                    )
            elif not any(binding.source is candidate.source_kind for binding in revision.bindings):
                raise ValueError(
                    f"census destination binding source is absent from {modelo.id}/{revision.id}: "
                    f"{candidate.source_kind.value}"
                )


def _freeze_toml_arrays(value: object) -> object:
    """Hydrate TOML arrays into the canonical strict immutable tuple shape."""
    if isinstance(value, list):
        return tuple(_freeze_toml_arrays(item) for item in value)
    if isinstance(value, Mapping):
        return {key: _freeze_toml_arrays(item) for key, item in value.items()}
    return value


_CENSUS_TOKEN_TYPES = {
    "disposition": SourceConnectivityDisposition,
    "locator_kind": SourceConnectivityGroundingLocatorKind,
    "role": SourceConnectivityExecutableEvidenceRole,
    "route_id": ModeloCalculationRouteId,
    "source_kind": BindingSourceKind,
}


def _hydrate_census_tokens(value: object, *, field_name: str | None = None) -> object:
    """Hydrate TOML strings into the census contract's strict closed enums."""
    if field_name == "period" and isinstance(value, str):
        return Period.from_string(value)
    token_type = _CENSUS_TOKEN_TYPES.get(field_name or "")
    if token_type is not None and isinstance(value, str):
        return token_type(value)
    if isinstance(value, tuple):
        return tuple(_hydrate_census_tokens(item) for item in value)
    if isinstance(value, Mapping):
        return {key: _hydrate_census_tokens(item, field_name=key) for key, item in value.items()}
    return value


@dataclass(frozen=True, slots=True)
class RegistryDestinationRecord:
    """One revision-local casilla destination from a validated snapshot.

    The record retains canonical ids and authored declaration facts only.
    Later census projections may attach producer declarations and dispositions,
    but must not replace these identities with labels or numeric box metadata.
    """

    modelo_id: ModeloId
    revision_id: RevisionId
    filing_year: int
    period: str
    casilla_id: CasillaId
    number: str
    segmento: str | None
    input_kind: InputKindValue
    required: bool
    manual_requirement: ManualCasillaRequirement | None
    legal_refs: tuple[LegalRefId, ...]
    source_refs: tuple[SourceRefId, ...]


@dataclass(frozen=True, slots=True)
class RegistryBindingRecord:
    """One declared binding and its canonical casilla targets.

    ``binding`` is the validated registry declaration itself, preserving its
    typed selector and aggregation model.  Target derivation delegates to the
    registry's canonical binding/casilla dual instead of reproducing the join.
    """

    modelo_id: ModeloId
    revision_id: RevisionId
    filing_year: int
    period: str
    binding_id: BindingId
    binding: DataBindingDefinition
    target_casilla_ids: tuple[CasillaId, ...]


@dataclass(frozen=True, slots=True)
class RegistryFormulaRecord:
    """One formula declaration with dependencies from canonical expression walkers."""

    modelo_id: ModeloId
    revision_id: RevisionId
    formula_id: FormulaId
    formula: FormulaDefinition
    casilla_dependency_ids: tuple[CasillaId, ...]
    binding_dependency_ids: tuple[BindingId, ...]
    relation_dependency_ids: tuple[RelationId, ...]


@dataclass(frozen=True, slots=True)
class RegistryRelationRecord:
    """One relation declaration and its canonical consumption channels."""

    modelo_id: ModeloId
    revision_id: RevisionId
    relation_id: RelationId
    relation: RelationDefinition
    consumption_channels: tuple[RelationConsumptionChannel, ...]


@dataclass(frozen=True, slots=True)
class RegistrySourceDispositionRecord:
    """One binding source used by the revision and its live route disposition."""

    modelo_id: ModeloId
    revision_id: RevisionId
    source_kind: BindingSourceKind
    disposition: BindingSourceDisposition


def derive_registry_destination_records(snapshot: RegistrySnapshot) -> tuple[RegistryDestinationRecord, ...]:
    """Project every casilla in ``snapshot`` in canonical identity order.

    ``RegistrySnapshot`` is the filing-instance authority and has already
    selected and validated the applicable revision.  Sorting by canonical
    ``casilla.id`` makes the projection independent of fragment and tuple
    authoring order without discarding any declaration.
    """
    return tuple(
        RegistryDestinationRecord(
            modelo_id=snapshot.modelo.id,
            revision_id=snapshot.revision.id,
            filing_year=snapshot.filing_year,
            period=snapshot.period,
            casilla_id=casilla.id,
            number=casilla.number,
            segmento=casilla.segmento,
            input_kind=casilla.input_kind,
            required=casilla.required,
            manual_requirement=(
                "required" if casilla.required else "optional"
            )
            if casilla.input_kind is InputKind.MANUAL
            else None,
            legal_refs=tuple(casilla.legal_refs),
            source_refs=tuple(casilla.source_refs),
        )
        for casilla in sorted(snapshot.revision.casillas, key=lambda item: item.id)
    )


def derive_registry_binding_records(snapshot: RegistrySnapshot) -> tuple[RegistryBindingRecord, ...]:
    """Project declared bindings with typed selectors, aggregation, and targets."""
    targets_by_binding = casillas_by_binding(snapshot.revision)
    return tuple(
        RegistryBindingRecord(
            modelo_id=snapshot.modelo.id,
            revision_id=snapshot.revision.id,
            filing_year=snapshot.filing_year,
            period=snapshot.period,
            binding_id=binding.id,
            binding=binding,
            target_casilla_ids=tuple(sorted(targets_by_binding.get(binding.id, ()))),
        )
        for binding in sorted(snapshot.revision.bindings, key=lambda item: item.id)
    )


def derive_registry_formula_records(snapshot: RegistrySnapshot) -> tuple[RegistryFormulaRecord, ...]:
    """Project formulas and all typed dependency axes without parsing expressions anew."""
    return tuple(
        RegistryFormulaRecord(
            modelo_id=snapshot.modelo.id,
            revision_id=snapshot.revision.id,
            formula_id=formula.id,
            formula=formula,
            casilla_dependency_ids=tuple(sorted(set(expression_casilla_refs(formula.expression)))),
            binding_dependency_ids=tuple(sorted(set(expression_binding_refs(formula.expression)))),
            relation_dependency_ids=tuple(sorted(set(expression_relation_refs(formula.expression)))),
        )
        for formula in sorted(snapshot.revision.formulas, key=lambda item: (item.id, item.target_casilla_id))
    )


def derive_registry_relation_records(snapshot: RegistrySnapshot) -> tuple[RegistryRelationRecord, ...]:
    """Project relations with consumption derived by the canonical registry index."""
    consumption_index = relation_consumption_index(snapshot.revision)
    return tuple(
        RegistryRelationRecord(
            modelo_id=snapshot.modelo.id,
            revision_id=snapshot.revision.id,
            relation_id=relation.id,
            relation=relation,
            consumption_channels=relation_consumption_channels(relation, consumption_index),
        )
        for relation in sorted(snapshot.revision.relations, key=lambda item: item.id)
    )


def derive_registry_source_disposition_records(
    snapshot: RegistrySnapshot,
) -> tuple[RegistrySourceDispositionRecord, ...]:
    """Project live dispositions for every binding source used by the revision."""
    source_kinds = sorted({binding.source for binding in snapshot.revision.bindings}, key=lambda item: item.value)
    return tuple(
        RegistrySourceDispositionRecord(
            modelo_id=snapshot.modelo.id,
            revision_id=snapshot.revision.id,
            source_kind=source_kind,
            disposition=CALCULATION_ROUTE_SOURCE_DISPOSITIONS[source_kind],
        )
        for source_kind in source_kinds
    )
