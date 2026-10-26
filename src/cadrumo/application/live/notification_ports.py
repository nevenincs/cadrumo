"""Application-owned ports and DTOs for live notifications.

The live notification service consumes these structural ports. Concrete sede,
PDF/parser and persistence adapters are assembled by an entrypoint instead of
being imported by the application service.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

from ...core.config import Settings
from ...core.identity.aeat_certificado import AeatCertificadoId
from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.notifications.sancion import SancionLiquidacion
from ..auth.session_types import AeatSession
from .snapshot_base import SnapshotRepository


class NotificationType(StrEnum):
    """Application-owned classification of one remote notification row."""

    NOTIFICACION = "notificacion"
    COMUNICACION = "comunicacion"
    PENDIENTE = "pendiente"
    UNKNOWN = "unknown"


NotificationTypeValue = Literal[
    NotificationType.NOTIFICACION,
    NotificationType.COMUNICACION,
    NotificationType.PENDIENTE,
    NotificationType.UNKNOWN,
]


class RemoteNotification(BaseModel):
    """Application DTO for one observed AEAT notification row.

    The Sede adapter owns its scraped DTO and translates it to this record before
    the row enters application orchestration or encrypted custody.
    """

    model_config = STRICT_FROZEN_CONFIG

    certificado_id: AeatCertificadoId
    tipo: NotificationTypeValue
    concepto: str = Field(default="", max_length=256)
    titular_nif: str = Field(min_length=4, max_length=32)
    titular_nombre: str = Field(max_length=256)
    destinatario_nif: str = Field(max_length=32)
    destinatario_nombre: str = Field(max_length=256)
    fecha_emision: date
    fecha_notificacion: date | None = None
    modo_notificacion: str | None = Field(default=None, max_length=64)
    leida: bool | None = None
    source_url: str = Field(min_length=1)
    mode: Literal["read"] = "read"


class NotificationsSnapshot(BaseModel):
    """Application DTO for one read-only notifications query result."""

    model_config = STRICT_FROZEN_CONFIG

    rows: tuple[RemoteNotification, ...]
    captured_at: datetime
    source_url: str = Field(min_length=1)
    mode: Literal["read"] = "read"


class NotificationSnapshotQueryProtocol(Protocol):
    """Read the authenticated notification surface and translate its result."""

    async def fetch(self, session: AeatSession, *, settings: Settings) -> NotificationsSnapshot:
        """Return one application-owned notifications snapshot."""
        ...


NotificationSnapshotRepositoryFactory = Callable[[str], SnapshotRepository[Any]]


@dataclass(frozen=True, slots=True)
class NotificationsPorts:
    """Required live-query and bucket-persistence capabilities for notifications."""

    snapshot_query: NotificationSnapshotQueryProtocol
    snapshot_repository_factory: NotificationSnapshotRepositoryFactory


class NotificationRowProtocol(Protocol):
    """The notification-row facts needed by the custody use case."""

    @property
    def certificado_id(self) -> AeatCertificadoId:
        """Execute this public contract operation."""
        ...

    @property
    def tipo(self) -> str:
        """Execute this public contract operation."""
        ...

    @property
    def fecha_emision(self) -> date:
        """Execute this public contract operation."""
        ...

    @property
    def leida(self) -> bool | None:
        """Execute this public contract operation."""
        ...


class NotificationDocumentProtocol(Protocol):
    """The in-memory document facts needed by the custody use case."""

    @property
    def certificado_id(self) -> AeatCertificadoId:
        """Execute this public contract operation."""
        ...

    @property
    def pdf_bytes(self) -> bytes:
        """Execute this public contract operation."""
        ...

    @property
    def pdf_sha256(self) -> str:
        """Execute this public contract operation."""
        ...

    @property
    def source_url(self) -> object:
        """Execute this public contract operation."""
        ...


class NotificationDocumentReaderProtocol(Protocol):
    """Read document bytes into a domain reading or an explicit refusal."""

    def read(
        self,
        document: NotificationDocumentProtocol,
    ) -> tuple[SancionLiquidacion | None, str | None]:
        """Execute this public contract operation."""
        ...


# The adapter signatures carry concrete session/row types. ``...`` keeps the
# application port independent of those adapter classes while still requiring
# the callable shape at runtime.
NotificationContentGuard = Callable[..., None]
NotificationDocumentFetcher = Callable[..., Awaitable[NotificationDocumentProtocol]]


__all__ = [
    "NotificationContentGuard",
    "NotificationDocumentFetcher",
    "NotificationDocumentProtocol",
    "NotificationDocumentReaderProtocol",
    "NotificationRowProtocol",
    "NotificationSnapshotQueryProtocol",
    "NotificationSnapshotRepositoryFactory",
    "NotificationType",
    "NotificationTypeValue",
    "NotificationsPorts",
    "NotificationsSnapshot",
    "RemoteNotification",
]
