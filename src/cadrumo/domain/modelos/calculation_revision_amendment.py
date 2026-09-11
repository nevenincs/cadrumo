"""Immutable calculation-revision amendment identity and M303 motive authority."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from enum import StrEnum

from pydantic import BaseModel, model_validator

from ...core.identity.hex_ids import FilingRecordId
from ...core.models import STRICT_FROZEN_CONFIG
from ..calculations.registry.authority import bundled_authority
from ..calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ..calculations.registry.ids import RevisionId
from ..calculations.registry.queries import RegistryQueryService
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


def _registry_m303_rectificativa_declarations() -> Mapping[str, str]:
    """Resolve M303 amendment declarations from the dated registry mapping."""
    authority = bundled_authority()
    model_report = RegistryQueryService(authority).describe_modelo("303")
    resolved = authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id="modelo-303-rectificativa-record-design-mapping",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=date.today(),
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise ModeloValidationError("M303 rectificativa declarations must resolve as a mapping fact")
    del model_report
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
) -> bool:
    """Return whether the exact reviewed revision/source coordinate admits a motive."""
    declarations = _registry_m303_rectificativa_declarations()
    prefix = f"record_design.{registry_revision_id}"
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


def m303_rectificativa_record_design_from_snapshot(snapshot: RegistrySnapshot) -> SourceReference | None:
    """Resolve the sole admitted record-design source owned by a snapshot."""
    candidates = tuple(
        source
        for source in snapshot.sources.values()
        if source.id in snapshot.revision.source_refs
        and m303_rectificativa_motive_is_applicable(
            registry_revision_id=snapshot.revision.id,
            record_design=source,
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
