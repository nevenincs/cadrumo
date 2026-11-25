"""Immutable evidence projected from an admitted filing coordinate."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.ids import LegalRefId, ModeloId, RevisionId, SourceRefId
from cadrumo.domain.calculations.registry.schema_live_verification import LiveCrossReferenceDecision
from cadrumo.domain.calculations.registry.schema_references import SourceReference
from cadrumo.domain.calculations.registry.schema_verification import WorkbookParityReference


@dataclass(frozen=True, slots=True)
class RegistryCoverageFacts:
    """Immutable evidence collections for one admitted filing coordinate."""

    modelo: ModeloId
    revision: RevisionId
    filing_year: int
    period: str
    legal: tuple[LegalRefId, ...]
    sources: Mapping[SourceRefId, SourceReference]
    workbook_parity_refs: tuple[WorkbookParityReference, ...]
    live_cross_references: tuple[LiveCrossReferenceDecision, ...]


def coverage_facts(
    authority: ValidatedRegistryAuthority,
    modelo_id: str,
    *,
    filing_year: int,
    period: str,
    on: date | None = None,
    revision_id: RevisionId | None = None,
    grade: RegistryAuthorityGrade = RegistryAuthorityGrade.FILING,
) -> RegistryCoverageFacts:
    """Project immutable evidence from the same admitted snapshot consumers read."""
    snapshot = authority.snapshot(
        modelo_id,
        filing_year=filing_year,
        period=period,
        on=on,
        revision_id=revision_id,
        grade=grade,
    )
    return RegistryCoverageFacts(
        modelo=snapshot.modelo.id,
        revision=snapshot.revision.id,
        filing_year=snapshot.filing_year,
        period=snapshot.period,
        legal=tuple(snapshot.legal),
        sources=snapshot.sources,
        workbook_parity_refs=tuple(snapshot.workbook_parity_refs.values()),
        live_cross_references=tuple(snapshot.live_cross_references.values()),
    )
