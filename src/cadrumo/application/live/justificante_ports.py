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
from ...domain.buckets.event import BucketEvent
from ...domain.justificante.schema import Justificante
from ...domain.modelos.filing_record import ModeloRecordCatalogue


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
    def bucket_id(self) -> str: ...

    def exists(self, snapshot_id: str) -> bool: ...

    def load(self, snapshot_id: str) -> object: ...

    def list_snapshots(self) -> Sequence[object]: ...

    def resolve(self, snapshot_id: str) -> object: ...

    def save(self, snapshot: object) -> None: ...


class JustificanteMetadataPort(Protocol):
    """Durable metadata registration for a parsed receipt."""

    def save(self, justificante: Justificante) -> None: ...


class JustificanteFilingPort(Protocol):
    """Load and save the local filing catalogue."""

    def load(self) -> ModeloRecordCatalogue: ...

    def save(self, catalogue: ModeloRecordCatalogue) -> None: ...


class JustificanteEventPort(Protocol):
    """Append the capture's lifecycle event through the owning history store."""

    def emit(self, events: tuple[BucketEvent, ...]) -> None: ...


@dataclass(frozen=True, slots=True)
class JustificanteRegistrationPorts:
    """Application-owned local persistence dependencies for receipt enrolment."""

    parse_pdf: Callable[[bytes], Justificante]
    metadata: JustificanteMetadataPort
    filing: JustificanteFilingPort
    events: JustificanteEventPort


class JustificanteLiveReadPort(Protocol):
    """Read the declaration register, procedure tree, and selected receipt."""

    async def declarations_and_expedientes(
        self,
        *,
        modelo: str,
        year: int,
    ) -> tuple[Sequence[JustificanteDeclaration], Sequence[JustificanteExpediente]]: ...

    async def capture(self, *, expediente_id: str) -> CapturedJustificante: ...


class JustificanteAuthenticityVerifierPort(Protocol):
    """Read-only CSV cotejo operation."""

    def verify(
        self,
        csv: str,
        *,
        browser: object | None = None,
        browser_session_factory: Callable[[], object] | None = None,
    ) -> Awaitable[bool]: ...
