"""Application-owned capabilities and DTOs for live expedientes reads.

The expedientes lifecycle stores an application snapshot and consumes a
read-only declaration-register capability.  Browser, Sede DTO, and encrypted
storage implementations are composed outside this module and translated at
that boundary.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal, Protocol

from pydantic import BaseModel, Field, model_validator

from ...core.config import Settings
from ...core.filing_year import FilingYear
from ...core.identity.aeat_expediente import AeatExpedienteId
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period
from .snapshot_base import SnapshotRepository

if TYPE_CHECKING:
    from ..auth.session_types import AeatSession


class ExpedientesDeclaration(BaseModel):
    """Application DTO for one read-only declaration-register row."""

    model_config = STRICT_FROZEN_CONFIG

    modelo: str = Field(min_length=1, max_length=8)
    ejercicio: FilingYear
    period: Period
    expediente_id: AeatExpedienteId
    estado: str = Field(min_length=1, max_length=16)
    tipo_solicitud: str | None = Field(default=None, max_length=128)
    observaciones: str | None = Field(default=None, max_length=512)
    presented_at: datetime
    justificante_link_text: str | None = Field(default=None, max_length=32)
    archive_link_text: str | None = Field(default=None, max_length=32)
    declaration_copy_link_text: str | None = Field(default=None, max_length=32)
    justificante_cell_index: int = Field(default=7, ge=0)
    archive_cell_index: int | None = Field(default=8, ge=0)
    declaration_copy_cell_index: int | None = Field(default=None, ge=0)
    mode: Literal["read"] = "read"

    @model_validator(mode="after")
    def _period_year_matches_ejercicio(self) -> ExpedientesDeclaration:
        if self.period.filing_year != self.ejercicio:
            raise ValueError("period.filing_year must match ejercicio")
        return self


class ExpedientesRegisterProtocol(Protocol):
    """Reusable authenticated declaration-register read session."""

    async def walk(self, *, modelo: str, ejercicio: int) -> tuple[ExpedientesDeclaration, ...]:
        """Return application-owned rows for one modelo/year query."""
        ...


class ExpedientesDeclarationReaderProtocol(Protocol):
    """Open a translated, read-only declaration-register session."""

    def open_register(
        self,
        session: AeatSession,
        *,
        settings: Settings,
    ) -> AbstractAsyncContextManager[ExpedientesRegisterProtocol]:
        """Yield a register whose adapter DTOs/errors never cross the port."""
        ...


ExpedientesSnapshotRepositoryFactory = Callable[[str], SnapshotRepository[Any]]


@dataclass(frozen=True, slots=True)
class ExpedientesPorts:
    """Required live-read and bucket-persistence capabilities."""

    declaration_reader: ExpedientesDeclarationReaderProtocol
    snapshot_repository_factory: ExpedientesSnapshotRepositoryFactory


class ExpedientesPortsFactory(Protocol):
    """Construct expedientes capabilities for one profile bucket."""

    def __call__(self, *, bucket_id: str) -> ExpedientesPorts:
        """Return the required bundle for ``bucket_id``."""
        ...


__all__ = [
    "ExpedientesDeclaration",
    "ExpedientesDeclarationReaderProtocol",
    "ExpedientesPorts",
    "ExpedientesPortsFactory",
    "ExpedientesRegisterProtocol",
    "ExpedientesSnapshotRepositoryFactory",
]
