"""Application ports for live justificante capture.

The capture workflow names only the values it needs from Sede and from local
storage.  Adapter and entrypoint code implement these ports; this module owns
no transport, browser, parser, or secure-store construction.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from ...core.period import Period
from ...domain.justificante.schema import Justificante
from ...domain.modelos.filing_record import ModeloRecordCatalogue
from .filed_observation_ports import FiledFilingReconciliationPort


@dataclass(frozen=True, slots=True)
class JustificanteDeclaration:
    """Period-bearing declaration data used to select an expediente."""

    modelo: str
    period: Period
    expediente_id: str
    estado: str
    presented_at: datetime


@dataclass(frozen=True, slots=True)
class JustificanteExpediente:
    """Minimal Sede procedure-tree entry needed to fetch a receipt."""

    expediente_id: str


@dataclass(frozen=True, slots=True)
class CapturedJustificante:
    """Authenticated receipt bytes and Sede references returned by a live read."""

    expediente_id: str
    csv: str
    pdf_bytes: bytes
    pdf_sha256: str


class JustificanteSnapshotPersistencePort(Protocol):
    """Bucket-bound encrypted persistence for capture snapshots."""

    @property
    def bucket_id(self) -> str:
        """Return the bucket identity that owns these snapshots."""
        ...

    def exists(self, snapshot_id: str) -> bool:
        """Return whether a snapshot identifier is persisted."""
        ...

    def load(self, snapshot_id: str) -> object:
        """Load one persisted snapshot by identifier."""
        ...

    def list_snapshots(self) -> Sequence[object]:
        """Return the persisted snapshots visible to this bucket."""
        ...

    def resolve(self, snapshot_id: str) -> object:
        """Resolve one snapshot identifier to its persisted record."""
        ...

    def save(self, snapshot: object) -> None:
        """Persist one capture snapshot through the encrypted store."""
        ...


class JustificanteMetadataPort(Protocol):
    """Durable metadata registration for a parsed receipt."""

    def save(self, justificante: Justificante) -> None:
        """Persist parsed receipt metadata."""
        ...


class JustificanteFilingPort(Protocol):
    """Load and save the local filing catalogue."""

    def load(self) -> ModeloRecordCatalogue:
        """Load the local filing catalogue."""
        ...

    def save(self, catalogue: ModeloRecordCatalogue) -> None:
        """Persist the local filing catalogue."""
        ...


@dataclass(frozen=True, slots=True)
class JustificanteRegistrationPorts:
    """Application-owned local persistence dependencies for receipt enrolment."""

    parse_pdf: Callable[[bytes], Justificante]
    metadata: JustificanteMetadataPort
    filing: JustificanteFilingPort
    filing_reconciliation: FiledFilingReconciliationPort


class JustificanteLiveReadPort(Protocol):
    """Read the declaration register, procedure tree, and selected receipt."""

    async def declarations_and_expedientes(
        self,
        *,
        modelo: str,
        year: int,
    ) -> tuple[Sequence[JustificanteDeclaration], Sequence[JustificanteExpediente]]:
        """Read declarations and their matching procedure-tree entries."""
        ...

    async def capture(self, *, expediente_id: str) -> CapturedJustificante:
        """Capture one authenticated receipt for an expediente."""
        ...


class JustificanteAuthenticityVerifierPort(Protocol):
    """Read-only CSV cotejo operation."""

    def verify(
        self,
        csv: str,
        *,
        browser: object | None = None,
        browser_session_factory: Callable[[], object] | None = None,
    ) -> Awaitable[bool]:
        """Verify a receipt CSV through the live cotejo operation."""
        ...
