"""Immutable calculation-revision amendment identity and M303 motive authority."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, model_validator

from ...core.identity import FilingRecordId
from ...core.models import STRICT_FROZEN_CONFIG
from ..calculations.registry.ids import RevisionId
from ..calculations.registry.schema import RegistrySnapshot
from ..calculations.registry.schema_references import SourceReference
from .errors import ModeloValidationError


class CalculationRevisionAmendmentKind(StrEnum):
    """Closed catalogue of amendment kinds a calculation revision may carry.

    Each member names the instrument it files, so the article travels with the
    kind rather than only with the regime that admits it:

    * ``COMPLEMENTARIA`` -- LGT art. 122.2 (``ley-58-2003:art-122``), an
      additional declaration correcting an already-presented one upward.
    * ``SUSTITUTIVA`` -- LGT art. 122.1 (``ley-58-2003:art-122``), a material
      restatement that replaces an already-presented filing in full. Not
      time-boxed by the rectificativa reform, which is why it is admitted in
      both regimes below.
    * ``RECTIFICATIVA`` -- LGT art. 120.4, the unified ordinary-correction
      mechanism each modelo adopts from its own effective period.
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


_M303_RECTIFICATIVA_RECORD_DESIGNS: frozenset[tuple[RevisionId, str, str, str]] = frozenset(
    {
        (
            "2024-desde-09-y-3t",
            "aeat-dr-303-2024-late",
            "2095dd633413f4aed28053bc88402461d80865f454156c01ebc4a2ab68cb76a8",
            "2024-late",
        ),
        (
            "2025",
            "aeat-dr-303-2025",
            "6c3d7eeb714e0deb52f91d7e8dbadeb83f16c1d32d25f9e871756f3ddf0117e6",
            "2025",
        ),
        (
            "2026-y-siguientes",
            "aeat-dr-303-2026",
            "0be8b156da2250c6b11f6253e0165221ed2e549ec4c65a562021bec6b9b8489b",
            "2026",
        ),
    },
)


def m303_rectificativa_motive_is_applicable(
    *,
    registry_revision_id: RevisionId,
    record_design: SourceReference,
) -> bool:
    """Return whether the exact reviewed revision/source coordinate admits a motive."""
    return (
        registry_revision_id,
        record_design.id,
        record_design.sha256,
        record_design.record_design_epoch or "",
    ) in _M303_RECTIFICATIVA_RECORD_DESIGNS


def m303_rectificativa_record_design_from_snapshot(
    snapshot: RegistrySnapshot,
) -> SourceReference | None:
    """Resolve the sole admitted record-design source owned by one :class:`~RegistrySnapshot`."""
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
