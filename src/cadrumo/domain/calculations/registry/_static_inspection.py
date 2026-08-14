"""Typed non-filing projection of one registry revision.

Static generators inspect a reviewed source design against the declarations of
one named revision.  That work must not manufacture a filing context or obtain
a :class:`RegistrySnapshot`: a snapshot is the later, filing-instance
authority.  This model deliberately exposes only the immutable facts a static
consumer may admit.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from importlib import import_module
from pathlib import Path
from typing import cast

from pydantic import Field, model_validator

from ....core import CasillaId
from ._casilla_membership import casillas_by_id
from ._ids import BindingId, LegalRefId, ModeloId, RevisionId, SourceRefId
from ._schema import (
    DataBindingDefinition,
    FormulaDefinition,
    LiveCrossReferenceDecision,
    ModeloDefinition,
    ModeloRevision,
    ParameterDefinition,
    ProjectionEndpointDeclaration,
    RelationDefinition,
    SourceReference,
    WorkbookParityReference,
)
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
    """The exact source catalogue slice exercised by this model/revision."""

    source_ref_ids: frozenset[SourceRefId]
    legal_ref_ids: frozenset[LegalRefId]
    """The exact legal-reference union exercised by this model/revision."""

    casilla_ids: frozenset[CasillaId]
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
        snapshot_module = import_module(f"{__package__}._snapshot")
        snapshot_ref_collector_name = "_collect_snapshot_ref_ids"
        collect_snapshot_ref_ids = cast(
            Callable[[ModeloDefinition, ModeloRevision], tuple[set[str], set[str]]],
            getattr(snapshot_module, snapshot_ref_collector_name),
        )
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
        return cls(
            modelo_id=modelo.id,
            revision_id=revision.id,
            source_root=source_root,
            revision_source_refs=revision.source_refs,
            sources=selected_sources,
            source_ref_ids=frozenset(selected_source_ids),
            legal_ref_ids=frozenset(selected_legal_ids),
            casilla_ids=frozenset(casillas_by_id(revision)),
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
