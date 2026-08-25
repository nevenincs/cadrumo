"""Projection-endpoint declaration validation."""

from __future__ import annotations

from collections.abc import Mapping

from ....core import CasillaId, FilingProjectionRef, filing_projection_ref_casilla_id
from .schema import (
    CasillaDefinition,
    LegalReference,
    ModeloRevision,
    ProjectionEndpointDeclaration,
    SourceReference,
)
from .schema_input_kind import InputKind
from ._validate_evidence import EvidenceValidator
from ._validate_helpers import missing_refs as _missing_refs


def validate_projection_endpoint_declarations(
    failures: list[str],
    *,
    prefix: str,
    revision: ModeloRevision,
    casillas: set[CasillaId],
    casilla_by_id: Mapping[CasillaId, CasillaDefinition],
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
    evidence: EvidenceValidator,
) -> None:
    """Validate revision-owned projection endpoint declarations."""
    references_by_casilla: dict[CasillaId, list[FilingProjectionRef]] = {}
    for reference, declarations in revision.projection_endpoint_index().items():
        _validate_projection_endpoint_reference(
            failures,
            prefix=prefix,
            revision=revision,
            reference=reference,
            declarations=declarations,
            casillas=casillas,
            casilla_by_id=casilla_by_id,
            legal_refs=legal_refs,
            source_refs=source_refs,
            evidence=evidence,
            references_by_casilla=references_by_casilla,
        )
    _validate_projection_endpoint_casilla_multiplicity(
        failures,
        prefix=prefix,
        references_by_casilla=references_by_casilla,
    )
    _validate_undeclared_projection_endpoint_casillas(
        failures,
        prefix=prefix,
        revision=revision,
        references_by_casilla=references_by_casilla,
    )


def _validate_projection_endpoint_reference(
    failures: list[str],
    *,
    prefix: str,
    revision: ModeloRevision,
    reference: FilingProjectionRef,
    declarations: tuple[ProjectionEndpointDeclaration, ...],
    casillas: set[CasillaId],
    casilla_by_id: Mapping[CasillaId, CasillaDefinition],
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
    evidence: EvidenceValidator,
    references_by_casilla: dict[CasillaId, list[FilingProjectionRef]],
) -> None:
    """Validate one endpoint identity and index its numbered casilla."""
    if len(declarations) != 1:
        failures.append(
            f"{prefix}: projection_ref {reference!r} is admitted by {len(declarations)} projection declarations; "
            "expected exactly one",
        )
    for declaration in declarations:
        _validate_projection_endpoint_declaration_evidence(
            failures,
            prefix=prefix,
            revision=revision,
            declaration=declaration,
            legal_refs=legal_refs,
            source_refs=source_refs,
            evidence=evidence,
        )
    casilla_id = filing_projection_ref_casilla_id(reference)
    if casilla_id is None:
        return
    references_by_casilla.setdefault(casilla_id, []).append(reference)
    if casilla_id not in casillas:
        failures.append(f"{prefix}: projection_ref {reference!r} references unknown casilla {casilla_id!r}")
        return
    if casilla_by_id[casilla_id].input_kind is not InputKind.PROJECTION_ONLY:
        failures.append(
            f"{prefix}: projection_ref {reference!r} references casilla {casilla_id!r} that is not projection_only",
        )


def _validate_projection_endpoint_casilla_multiplicity(
    failures: list[str],
    *,
    prefix: str,
    references_by_casilla: Mapping[CasillaId, list[FilingProjectionRef]],
) -> None:
    """Require each numbered endpoint casilla to have one projection identity."""
    for casilla_id, references in references_by_casilla.items():
        if len(references) != 1:
            failures.append(
                f"{prefix}: projection endpoint casilla {casilla_id!r} is addressed by multiple projection_refs",
            )


def _validate_undeclared_projection_endpoint_casillas(
    failures: list[str],
    *,
    prefix: str,
    revision: ModeloRevision,
    references_by_casilla: Mapping[CasillaId, list[FilingProjectionRef]],
) -> None:
    """Require every projection-only casilla to have a revision declaration."""
    undeclared = tuple(
        casilla.id
        for casilla in revision.casillas
        if casilla.input_kind is InputKind.PROJECTION_ONLY and casilla.id not in references_by_casilla
    )
    if undeclared:
        failures.append(
            f"{prefix}: projection_only casillas lack revision-owned projection declarations: {undeclared!r}",
        )


def _validate_projection_endpoint_declaration_evidence(
    failures: list[str],
    *,
    prefix: str,
    revision: ModeloRevision,
    declaration: ProjectionEndpointDeclaration,
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
    evidence: EvidenceValidator,
) -> None:
    """Require catalogue-grounded, revision-pinned endpoint evidence."""
    owner = f"projection endpoint {declaration.projection_ref!r}"
    failures.extend(_missing_refs(prefix, owner, declaration.legal_refs, legal_refs, "legal"))
    failures.extend(_missing_refs(prefix, owner, declaration.source_refs, source_refs, "source"))
    failures.extend(evidence.require_source_tier(prefix, owner, declaration.source_refs, "layout_authority"))
    foreign_sources = tuple(sorted(set(declaration.source_refs) - set(revision.source_refs)))
    if foreign_sources:
        failures.append(
            f"{prefix}: {owner} cites source refs outside the selected revision authority: {foreign_sources!r}",
        )
