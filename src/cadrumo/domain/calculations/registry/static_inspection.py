"""Typed non-filing projection of one registry revision.

Static generators inspect a reviewed source design against the declarations of
one named revision.  That work must not manufacture a filing context or obtain
a :class:`RegistrySnapshot`: a snapshot is the later, filing-instance
authority.  This model deliberately exposes only the immutable facts a static
consumer may admit.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from types import MappingProxyType
from typing import Literal, Protocol

from pydantic import Field, model_validator

from ....core import RevisionReviewStatus
from ....core.casilla_id import CasillaId
from .casilla_membership import casillas_by_id
from .ids import BindingId, LegalRefId, ModeloId, RevisionId, SourceRefId
from .schema import (
    DataBindingDefinition,
    FormulaDefinition,
    ModeloDefinition,
    ModeloRevision,
    SchemaFamilyDispositionDeclaration,
)
from .schema_base import RegistryModel
from .schema_exports import ProjectionEndpointDeclaration
from .schema_formula import ParameterDefinition
from .schema_references import SourceReference
from .schema_surfaces import RelationDefinition
from .schema_verification import LiveCrossReferenceDecision, WorkbookParityReference

__all__ = [
    "GeneratedArtifactInspection",
    "GeneratedArtifactSource",
    "RegistryRevisionInspection",
    "StaticGeneratedArtifactInspection",
    "StaticGeneratedArtifactSource",
]


type _GeneratedArtifactSourceKind = Literal[
    "record_design",
    "manual_pdf",
    "instructions",
    "xsd",
    "dictionary",
    "form_spec",
    "suppression_notice",
]
type _GeneratedArtifactCorpusTier = Literal["full_consolidated", "provision_excerpt"]


class GeneratedArtifactSource(Protocol):
    """The byte-authority fields a generated-artifact verifier consumes."""

    id: SourceRefId
    kind: _GeneratedArtifactSourceKind
    corpus_path: str
    sha256: str
    bytes: int
    applies_from: date | None
    applies_to: date | None
    record_design_epoch: str | None
    corpus_tier: _GeneratedArtifactCorpusTier | None

    def applies_across(self, span_from: date, span_to: date | None) -> bool:
        """Report whether this source's applicability window overlaps one date span.

        See :meth:`SourceReference.applies_across` for the one definition of
        the overlap rule this Protocol member declares.
        """
        ...


class GeneratedArtifactInspection(Protocol):
    """The static revision facts required to verify a generated artefact."""

    modelo_id: ModeloId
    revision_id: RevisionId
    revision_source_refs: tuple[SourceRefId, ...]
    sources: Mapping[SourceRefId, GeneratedArtifactSource]
    legal_ref_ids: frozenset[LegalRefId]
    casilla_ids: frozenset[CasillaId]
    binding_ids: frozenset[BindingId]
    projection_endpoints: tuple[ProjectionEndpointDeclaration, ...]


@dataclass(frozen=True, slots=True)
class StaticGeneratedArtifactSource:
    """Immutable byte-authority facts copied for diagnostic verification."""

    id: SourceRefId
    kind: _GeneratedArtifactSourceKind
    corpus_path: str
    sha256: str
    bytes: int
    applies_from: date | None
    applies_to: date | None
    record_design_epoch: str | None
    corpus_tier: _GeneratedArtifactCorpusTier | None

    @classmethod
    def from_source(cls, source: SourceReference) -> StaticGeneratedArtifactSource:
        """Copy the exact source fields used by generated-artifact verification."""
        return cls(
            id=source.id,
            kind=source.kind,
            corpus_path=source.corpus_path,
            sha256=source.sha256,
            bytes=source.bytes,
            applies_from=source.applies_from,
            applies_to=source.applies_to,
            record_design_epoch=source.record_design_epoch,
            corpus_tier=source.corpus_tier,
        )


@dataclass(frozen=True, slots=True)
class StaticGeneratedArtifactInspection:
    """Minimal immutable revision facts for diagnostic generated-artifact checks."""

    modelo_id: ModeloId
    revision_id: RevisionId
    revision_source_refs: tuple[SourceRefId, ...]
    sources: Mapping[SourceRefId, StaticGeneratedArtifactSource]
    legal_ref_ids: frozenset[LegalRefId]
    casilla_ids: frozenset[CasillaId]
    binding_ids: frozenset[BindingId]
    projection_endpoints: tuple[ProjectionEndpointDeclaration, ...]

    @classmethod
    def from_inspection(
        cls,
        inspection: RegistryRevisionInspection,
    ) -> StaticGeneratedArtifactInspection:
        """Copy only the fields the shared generated-artifact verifier reads."""
        return cls(
            modelo_id=inspection.modelo_id,
            revision_id=inspection.revision_id,
            revision_source_refs=tuple(inspection.revision_source_refs),
            sources=MappingProxyType(
                {
                    source_ref: StaticGeneratedArtifactSource.from_source(source)
                    for source_ref, source in inspection.sources.items()
                }
            ),
            legal_ref_ids=frozenset(inspection.legal_ref_ids),
            casilla_ids=frozenset(inspection.casilla_ids),
            binding_ids=frozenset(inspection.binding_ids),
            projection_endpoints=tuple(endpoint.model_copy(deep=True) for endpoint in inspection.projection_endpoints),
        )


class RegistryRevisionInspection(RegistryModel):
    """The static admission facts for one explicit registry revision.

    It intentionally carries neither a filing year nor a period.  A caller
    must select ``revision_id`` explicitly, then use the retained source,
    casilla, binding, projection, and legal identifiers to validate generated
    static artefacts.  It cannot calculate, render, or file anything.
    """

    modelo_id: ModeloId
    revision_id: RevisionId
    review_status: RevisionReviewStatus
    """The revision's own governance stamp -- not filing-grade content, so it
    stays in scope for a static inspection whose job is validating generated
    static artefacts against a revision it may or may not trust yet."""
    family_dispositions: Mapping[str, SchemaFamilyDispositionDeclaration]
    """The revision's declared not-applicable schema families and their
    grounding reason/legal_refs/source_refs -- classification metadata, not
    filing-grade content, so it stays in scope for a static inspection."""
    source_root: Path
    revision_source_refs: tuple[SourceRefId, ...] = Field(min_length=1)
    sources: Mapping[SourceRefId, SourceReference]
    """The exact source catalogue slice exercised by this model/revision."""

    source_ref_ids: frozenset[SourceRefId]
    legal_ref_ids: frozenset[LegalRefId]
    """The exact legal-reference union exercised by this model/revision."""

    casilla_ids: frozenset[CasillaId]
    casilla_sections: Mapping[CasillaId, tuple[str, ...]] = MappingProxyType({})
    """Each casilla's declared section path, as the revision itself declares it.

    Carried alongside the ids because the ids alone cannot say where a casilla
    sits in the modelo's own structure, and a consumer needing that structure
    would otherwise have to re-read the revision -- the wholesale exposure this
    projection exists to avoid. Read from the same casilla definitions the id
    set is derived from, so the two cannot disagree.
    """
    binding_ids: frozenset[BindingId]
    projection_endpoints: tuple[ProjectionEndpointDeclaration, ...]
    # These declaration tuples are the non-filing evidence surface consumed by
    # coverage audits.  They are deliberately copied into this projection
    # instead of exposing ``revision`` wholesale: an inspection object cannot
    # be passed to calculation, filing, or export APIs expecting a snapshot.
    formulas: tuple[FormulaDefinition, ...] = ()
    parameters: tuple[ParameterDefinition, ...] = ()
    bindings: tuple[DataBindingDefinition, ...] = ()
    relations: tuple[RelationDefinition, ...] = ()
    workbook_parity_refs: tuple[WorkbookParityReference, ...] = ()
    live_cross_references: tuple[LiveCrossReferenceDecision, ...] = ()

    @classmethod
    def from_revision(
        cls,
        *,
        modelo: ModeloDefinition,
        revision: ModeloRevision,
        source_root: Path,
        sources: Mapping[SourceRefId, SourceReference],
        legal_ref_ids: frozenset[LegalRefId],
    ) -> RegistryRevisionInspection:
        """Project one loaded revision without creating a filing snapshot."""
        # Keep this projection on the exact same nested legal/source union as
        # ``RegistrySnapshot``.  The import is local because the public
        # registry facade imports this module before the snapshot module; the
        # call itself only occurs after the authority has completed loading.
        # It is a literal statement rather than a computed module name so the
        # target is legible to a reader and to static analysis alike: the
        # deferral is what breaks the cycle, and naming the module through an
        # f-string bought nothing while hiding where the call actually lands.
        from ._snapshot_internals import collect_snapshot_ref_ids

        selected_legal_ids, selected_source_ids = collect_snapshot_ref_ids(modelo, revision)
        missing_legal_refs = selected_legal_ids.difference(legal_ref_ids)
        if missing_legal_refs:
            raise ValueError(
                "static inspection legal references are absent from its legal catalogue: "
                f"{tuple(sorted(missing_legal_refs))!r}",
            )
        selected_sources = {
            source_ref: sources[source_ref] for source_ref in sorted(selected_source_ids) if source_ref in sources
        }
        revision_casillas = casillas_by_id(revision)
        return cls(
            modelo_id=modelo.id,
            revision_id=revision.id,
            review_status=revision.review_status,
            family_dispositions=revision.family_dispositions,
            source_root=source_root,
            revision_source_refs=revision.source_refs,
            sources=selected_sources,
            source_ref_ids=frozenset(selected_source_ids),
            legal_ref_ids=frozenset(selected_legal_ids),
            casilla_ids=frozenset(revision_casillas),
            casilla_sections=MappingProxyType(
                {casilla_id: tuple(casilla.section) for casilla_id, casilla in revision_casillas.items()}
            ),
            binding_ids=frozenset(binding.id for binding in revision.bindings),
            projection_endpoints=revision.projection_endpoints,
            formulas=revision.formulas,
            parameters=revision.parameters,
            bindings=revision.bindings,
            relations=revision.relations,
            workbook_parity_refs=revision.workbook_parity_refs,
            live_cross_references=revision.live_cross_references,
        )

    @model_validator(mode="after")
    def _require_complete_static_admission(self) -> RegistryRevisionInspection:
        _validate_revision_source_refs(self)
        _validate_source_catalogue_keys(self)
        _validate_selected_source_union(self)
        return self


def _validate_revision_source_refs(inspection: RegistryRevisionInspection) -> None:
    """Require unique, non-empty revision sources that are catalogue-owned."""
    if len(set(inspection.revision_source_refs)) != len(inspection.revision_source_refs):
        raise ValueError("static inspection revision source references must be unique")
    if not inspection.revision_source_refs:
        raise ValueError("static inspection revision source references must not be empty")
    missing_sources = tuple(
        source_ref for source_ref in inspection.revision_source_refs if source_ref not in inspection.sources
    )
    if missing_sources:
        raise ValueError(
            f"static inspection revision source references are absent from its source catalogue: {missing_sources!r}",
        )


def _validate_source_catalogue_keys(inspection: RegistryRevisionInspection) -> None:
    """Require each selected source catalogue key to match its source id."""
    mismatched_sources = tuple(
        source_ref for source_ref, source in inspection.sources.items() if source_ref != source.id
    )
    if mismatched_sources:
        raise ValueError(
            f"static inspection source catalogue keys must match source identifiers: {mismatched_sources!r}",
        )


def _validate_selected_source_union(inspection: RegistryRevisionInspection) -> None:
    """Require the selected source union to contain every revision source."""
    source_ids = frozenset(inspection.sources)
    if source_ids != inspection.source_ref_ids:
        raise ValueError(
            "static inspection source catalogue does not match its selected source-reference union: "
            f"expected {tuple(sorted(inspection.source_ref_ids))!r}, got {tuple(sorted(source_ids))!r}",
        )
    if not set(inspection.revision_source_refs).issubset(source_ids):
        raise ValueError("static inspection revision sources must be present in the selected source catalogue")
