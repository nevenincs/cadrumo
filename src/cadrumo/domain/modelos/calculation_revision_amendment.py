"""Immutable calculation-revision amendment identity and M303 motive authority."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

from pydantic import BaseModel, model_validator

from ...core.identity.hex_ids import FilingRecordId
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.time.clock import today_madrid
from ..calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ..calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ..calculations.registry.ids import RevisionId
from ..calculations.registry.schema import RegistrySnapshot
from ..calculations.registry.schema_base import DateAxis
from ..calculations.registry.schema_references import SourceReference
from .errors import ModeloValidationError


class CalculationRevisionAmendmentKind(StrEnum):
    """Closed catalogue of amendment kinds a calculation revision may carry.

    Each member names the instrument it files, so the article travels with the
    kind rather than only with the regime that admits it:

    * ``COMPLEMENTARIA`` -- an additional declaration correcting an
      already-presented one upward.
    * ``SUSTITUTIVA`` -- a material restatement that replaces an
      already-presented filing in full.
    * ``RECTIFICATIVA`` -- the ordinary-correction mechanism selected by the
      applicable modelo revision.
    """

    COMPLEMENTARIA = "complementaria"
    SUSTITUTIVA = "sustitutiva"
    RECTIFICATIVA = "rectificativa"


class M303RectificativaMotive(StrEnum):
    """The two mutually-exclusive motives admitted by the M303 record design."""

    RECTIFICACIONES = "rectificaciones"
    DISCREPANCIA_CRITERIO_ADMINISTRATIVO = "discrepancia_criterio_administrativo"


class CalculationRevisionAmendmentIdentity(BaseModel):
    """The sole content-addressed amendment identity carried by a revision."""

    model_config = STRICT_FROZEN_CONFIG

    kind: CalculationRevisionAmendmentKind
    amends_filing_record_id: FilingRecordId
    m303_rectificativa_motive: M303RectificativaMotive | None

    @model_validator(mode="after")
    def _motive_requires_rectificativa_kind(self) -> CalculationRevisionAmendmentIdentity:
        if (
            self.m303_rectificativa_motive is not None
            and self.kind is not CalculationRevisionAmendmentKind.RECTIFICATIVA
        ):
            raise ModeloValidationError("an M303 rectificativa motive is valid only for amendment kind rectificativa")
        return self


def _registry_m303_rectificativa_declarations(
    *,
    operation: PinnedAuthorityOperation,
) -> Mapping[str, str]:
    """Resolve M303 amendment declarations from the dated registry mapping."""
    if not any(metadata.contains_date(today_madrid()) for metadata in operation.modelo_directory("303").revisions):
        raise ModeloValidationError("M303 has no registry revision for today's date")
    resolved = operation.resolve_governed_fact(
        MappingFactQuery(
            fact_id="modelo-303-rectificativa-record-design-mapping",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=today_madrid(),
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise ModeloValidationError("M303 rectificativa declarations must resolve as a mapping fact")
    return {str(entry.key): str(entry.value) for entry in resolved.payload.entries}


def _required_registry_declaration(declarations: Mapping[str, str], key: str) -> str:
    try:
        return declarations[key]
    except KeyError as exc:
        raise ModeloValidationError(f"M303 rectificativa registry declaration is missing: {key}") from exc


def m303_rectificativa_motive_is_applicable(
    *,
    registry_revision_id: RevisionId,
    record_design: SourceReference,
    operation: PinnedAuthorityOperation | None = None,
) -> bool:
    """Return whether the exact reviewed revision/source coordinate admits a motive."""
    if operation is None:
        with bundled_indexed_authority().operation() as indexed_operation:
            return m303_rectificativa_motive_is_applicable(
                registry_revision_id=registry_revision_id,
                record_design=record_design,
                operation=indexed_operation,
            )
    declarations = _registry_m303_rectificativa_declarations(operation=operation)
    prefix = f"record_design.{registry_revision_id}"
    # The mapping enumerates every revision whose record design carries the
    # rectificativa motive; an unlisted revision's design has no such field.
    if f"{prefix}.source_ref" not in declarations:
        return False
    return (
        registry_revision_id,
        record_design.id,
        record_design.sha256,
        record_design.record_design_epoch or "",
    ) == (
        registry_revision_id,
        _required_registry_declaration(declarations, f"{prefix}.source_ref"),
        _required_registry_declaration(declarations, f"{prefix}.content_digest"),
        _required_registry_declaration(declarations, f"{prefix}.epoch"),
    )


def m303_rectificativa_record_design_from_snapshot(
    snapshot: RegistrySnapshot,
    *,
    operation: PinnedAuthorityOperation | None = None,
) -> SourceReference | None:
    """Resolve the sole admitted record-design source owned by a snapshot.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`.
    """
    if operation is None:
        with bundled_indexed_authority().operation() as indexed_operation:
            return m303_rectificativa_record_design_from_snapshot(snapshot, operation=indexed_operation)
    candidates = tuple(
        source
        for source in snapshot.sources.values()
        if source.id in snapshot.revision.source_refs
        and m303_rectificativa_motive_is_applicable(
            registry_revision_id=snapshot.revision.id,
            record_design=source,
            operation=operation,
        )
    )
    if len(candidates) > 1:
        raise ModeloValidationError("M303 revision owns more than one admitted rectificativa record design")
    return candidates[0] if candidates else None


__all__ = [
    "CalculationRevisionAmendmentIdentity",
    "CalculationRevisionAmendmentKind",
    "M303RectificativaMotive",
    "m303_rectificativa_motive_is_applicable",
    "m303_rectificativa_record_design_from_snapshot",
]
