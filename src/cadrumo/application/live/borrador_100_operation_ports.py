"""Exact-profile snapshot custody and in-memory borrador parsing capabilities."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, Protocol
from uuid import UUID

from ...core.casilla_id import CasillaId
from ...core.identity.digest import ContentDigest
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.schema_extraction import ExtractionProfileDefinition
from .borrador_100 import Borrador100SnapshotRepository

type Borrador100ArtefactKind = Literal["BORRADOR", "PREDECLARACION", "DECLARACION"]


@dataclass(frozen=True, slots=True)
class Borrador100PrintedValue:
    """One observed row; an absent printed value differs from decimal zero."""

    casilla_id: CasillaId
    value: Decimal | str | None


@dataclass(frozen=True, slots=True)
class Borrador100ImportObservation:
    """Parser receipt without the document's taxpayer identifier or CSV stamp."""

    ejercicio: str
    extraction_profile_id: str | None
    extraction_coverage: Decimal | None
    artefact_kind: Borrador100ArtefactKind
    source_pdf_sha256: ContentDigest
    values: tuple[Borrador100PrintedValue, ...]
    warnings: tuple[str, ...] = ()


class Borrador100ImportParserPort(Protocol):
    """Parse a single source capture with the published, explicitly selected year."""

    def parse(
        self,
        pdf_bytes: bytes,
        *,
        filing_year: int,
        extraction_profile: ExtractionProfileDefinition,
    ) -> Borrador100ImportObservation:
        """Return the canonical parser's observed values and profile receipt."""
        ...


@dataclass(frozen=True, slots=True)
class Borrador100OperationPorts:
    """Immutable worker/profile binding for every operation in this family."""

    profile_id: UUID
    operation: PinnedAuthorityOperation
    repository: Borrador100SnapshotRepository
    parser: Borrador100ImportParserPort


class Borrador100OperationPortsFactory(Protocol):
    """Compose local capabilities only after exact-profile worker admission."""

    def __call__(self, *, profile_id: UUID, operation: PinnedAuthorityOperation) -> Borrador100OperationPorts:
        """Return encrypted snapshot custody and a parser without reading a file."""
        ...
