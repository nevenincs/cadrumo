"""Typed non-filing projection of one registry revision.

Static generators inspect a reviewed source design against the declarations of
one named revision.  That work must not manufacture a filing context or obtain
a :class:`RegistrySnapshot`: a snapshot is the later, filing-instance
authority.  This model deliberately exposes only the immutable facts a static
consumer may admit.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from pydantic import Field, model_validator

from ....core import CasillaId
from ._casilla_membership import casillas_by_id
from ._ids import BindingId, LegalRefId, ModeloId, RevisionId, SourceRefId
from ._schema import ModeloDefinition, ModeloRevision, ProjectionEndpointDeclaration, SourceReference
from ._schema_base import RegistryModel

__all__ = ["RegistryRevisionInspection"]


class RegistryRevisionInspection(RegistryModel):
    """The static admission facts for one explicit registry revision.

    It intentionally carries neither a filing year nor a period.  A caller
    must select ``revision_id`` explicitly, then use the retained source,
    casilla, binding, projection, and legal identifiers to validate generated
    static artefacts.  It cannot calculate, render, or file anything.
    """

    modelo_id: ModeloId
    revision_id: RevisionId
    source_root: Path
    revision_source_refs: tuple[SourceRefId, ...] = Field(min_length=1)
    sources: Mapping[SourceRefId, SourceReference]
    legal_ref_ids: frozenset[LegalRefId]
    casilla_ids: frozenset[CasillaId]
    binding_ids: frozenset[BindingId]
    projection_endpoints: tuple[ProjectionEndpointDeclaration, ...]

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
        return cls(
            modelo_id=modelo.id,
            revision_id=revision.id,
            source_root=source_root,
            revision_source_refs=revision.source_refs,
            sources=sources,
            legal_ref_ids=legal_ref_ids,
            casilla_ids=frozenset(casillas_by_id(revision)),
            binding_ids=frozenset(binding.id for binding in revision.bindings),
            projection_endpoints=revision.projection_endpoints,
        )

    @model_validator(mode="after")
    def _require_complete_static_admission(self) -> RegistryRevisionInspection:
        if len(set(self.revision_source_refs)) != len(self.revision_source_refs):
            raise ValueError("static inspection revision source references must be unique")
        missing_sources = tuple(
            source_ref for source_ref in self.revision_source_refs if source_ref not in self.sources
        )
        if missing_sources:
            raise ValueError(
                "static inspection revision source references are absent from its source catalogue: "
                f"{missing_sources!r}",
            )
        mismatched_sources = tuple(source_ref for source_ref, source in self.sources.items() if source_ref != source.id)
        if mismatched_sources:
            raise ValueError(
                f"static inspection source catalogue keys must match source identifiers: {mismatched_sources!r}",
            )
        return self
