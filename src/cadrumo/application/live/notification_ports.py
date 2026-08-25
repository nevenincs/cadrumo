"""Application-owned ports for notification-document custody.

The live notification service consumes these structural ports. Concrete sede,
PDF/parser and persistence adapters are assembled by an entrypoint instead of
being imported by the application service.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import date
from typing import Protocol

from ...core.identity import AeatCertificadoId
from ...domain.notifications import SancionLiquidacion


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
]
