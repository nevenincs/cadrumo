"""Deterministic registry-side inputs to the source-connectivity census.

This module projects validated registry authority.  It deliberately does not
reconstruct producer joins or infer legal equivalence from casilla labels and
numbers: those contracts remain owned by ``ModeloRevision`` and its typed
declarations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ...core import CasillaId
from ...domain.calculations.registry import (
    InputKind,
    InputKindValue,
    LegalRefId,
    ModeloId,
    RegistrySnapshot,
    RevisionId,
    SourceRefId,
)

__all__ = [
    "ManualCasillaRequirement",
    "RegistryDestinationRecord",
    "derive_registry_destination_records",
]

type ManualCasillaRequirement = Literal["required", "optional"]


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
