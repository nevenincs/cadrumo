"""Protocol stubs for cross-subpackage dependencies still in flight.

These Protocols let the submission engine compile and ship before its
upstream siblings land on ``main``:

- ``ModeloIdentifier`` — rebase-swap stub for ``aeat.models`` (#6).
- ``Portal`` / ``PortalCatalogue`` — stubs for ``aeat.portals`` (#7).
- ``AuthProviderDescription`` / ``AuthProviderProbe`` — stubs for
  the provider-agnostic auth surface (#281).
- ``CasillaRecord`` / ``CasillaCatalogue`` — stubs for
  ``aeat.casillas`` (#23).
- ``DeadlineWindowChecker`` — narrow stub that mirrors the surface
  the submission engine needs from ``aeat.deadlines`` (#38, already
  on main; decoupled here for rebase-safety).
- ``FilingFinding`` / ``FilingDraftLike`` / ``DraftLoader`` — stubs
  for ``aeat.filing`` (#39).
- ``Justificante`` / ``JustificanteParser`` — stubs for
  ``aeat.justificante`` (#44).

Every stub is either a strict+frozen pydantic v2 model or a
``runtime_checkable`` ``Protocol``; no dataclasses; no bare dicts.
Rebase-swap against the real siblings is a mechanical one-file diff.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

from ..i18n import Translatable

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")

_MODELO_RE = re.compile(r"^\d{3}[A-Z]?$")


class ModeloIdentifier(str):
    """Typed string identifier for an AEAT modelo (e.g. ``"130"``, ``"303"``).

    Rebase-swap stub for the real enum from ``aeat.models`` (#6).
    Shape-compatible with ``aeat.deadlines._protocols.ModeloIdentifier``.
    """

    __slots__ = ()

    def __new__(cls, value: str) -> ModeloIdentifier:
        """Construct and validate a modelo identifier.

        Args:
            value: The raw string identifier.

        Returns:
            The validated :class:`ModeloIdentifier`.

        Raises:
            ValueError: If ``value`` does not match the
                ``^\\d{3}[A-Z]?$`` pattern.
        """
        if not isinstance(value, str) or not _MODELO_RE.match(value):
            raise ValueError(f"Invalid modelo identifier: {value!r}")
        return super().__new__(cls, value)

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: Any,
        handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        """Return a pydantic core schema that validates via :meth:`__new__`."""
        return core_schema.no_info_after_validator_function(
            cls,
            core_schema.str_schema(pattern=_MODELO_RE.pattern),
        )


class Portal(BaseModel):
    """Rebase-swap stub for ``aeat.portals.Portal`` (#7).

    Attributes:
        modelo: The modelo identifier the portal serves.
        presentation_url: The canonical AEAT portal URL for the
            presentación of this modelo.
        label: Optional trilingual label for UI display.
    """

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1)
    presentation_url: str = Field(min_length=1)
    label: Translatable | None = None


@runtime_checkable
class PortalCatalogue(Protocol):
    """Rebase-swap stub for ``aeat.portals.PortalCatalogue`` (#7)."""

    def portal_for(self, modelo: str) -> Portal:
        """Return the :class:`Portal` that serves ``modelo``."""
        ...


class AuthProviderKind(StrEnum):
    """Local stub for the auth-provider kind enum."""

    CERTIFICATE = "certificate"
    CLAVE_PERMANENTE = "clave_permanente"
    CLAVE_MOVIL = "clave_movil"
    CLAVE_PIN = "clave_pin"


class AuthProviderDescription(BaseModel):
    """Safe description of one auth provider's current state."""

    model_config = _STRICT_FROZEN

    kind: AuthProviderKind
    label: str = Field(min_length=1)
    configured: bool
    available: bool
    identity_nif: str | None = None
    subject: str | None = None
    expires_on: date | None = None
    health_severity: str | None = None
    days_until_expiry: int | None = None
    health_summary: str | None = None


@runtime_checkable
class AuthProviderProbe(Protocol):
    """Narrow submission-facing auth-provider surface."""

    kind: AuthProviderKind

    def describe(self) -> AuthProviderDescription:
        """Return a safe description of the active auth provider."""
        ...


class CasillaInputKind(StrEnum):
    """The input control kind used on the AEAT portal for a casilla."""

    TEXT = "TEXT"
    NUMBER = "NUMBER"
    DATE = "DATE"
    CHECKBOX = "CHECKBOX"
    SELECT = "SELECT"


class CasillaRecord(BaseModel):
    """Rebase-swap stub for ``aeat.casillas.CasillaRecord`` (#23).

    Attributes:
        id: The casilla identifier (e.g. ``"01"``, ``"03"``).
        label: Trilingual label for the casilla.
        input_kind: The control kind used on the AEAT portal.
    """

    model_config = _STRICT_FROZEN

    id: str = Field(min_length=1)
    label: Translatable
    input_kind: CasillaInputKind


@runtime_checkable
class CasillaCatalogue(Protocol):
    """Rebase-swap stub for ``aeat.casillas.CasillaCatalogue`` (#23)."""

    def casillas_for_modelo(self, modelo: str) -> tuple[CasillaRecord, ...]:
        """Return the tuple of casillas registered for ``modelo``."""
        ...

    def get(self, casilla_id: str) -> CasillaRecord:
        """Return the :class:`CasillaRecord` with ``casilla_id``."""
        ...


@runtime_checkable
class DeadlineWindowChecker(Protocol):
    """Narrow stub for the subset of ``aeat.deadlines`` we consume (#38).

    ``aeat.deadlines`` already lives on ``main``, but the submission
    engine still wires through a Protocol so rebase is decoupled from
    any future internal API drift in the deadline engine.
    """

    def is_window_open(self, modelo: str, period: str, today: date) -> bool:
        """Return ``True`` iff the AEAT filing window for ``modelo`` /
        ``period`` is open on ``today``."""
        ...


class FilingFindingSeverity(StrEnum):
    """Severity of a :class:`FilingFinding`."""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class FilingFinding(BaseModel):
    """Rebase-swap stub for ``aeat.filing.FilingFinding`` (#39).

    Attributes:
        severity: The finding severity; ``ERROR`` blocks submission.
        message: Trilingual finding message.
    """

    model_config = _STRICT_FROZEN

    severity: FilingFindingSeverity
    message: Translatable


class DraftStatus(StrEnum):
    """Rebase-swap stub for ``aeat.filing.DraftStatus`` (#39)."""

    DRAFT = "DRAFT"
    INCOMPLETE = "INCOMPLETE"
    READY_TO_SUBMIT = "READY_TO_SUBMIT"


@runtime_checkable
class FilingDraftLike(Protocol):
    """Rebase-swap stub for ``aeat.filing.FilingDraft`` (#39).

    Properties are declared as attributes; any class that provides
    them structurally conforms.
    """

    draft_id: str
    modelo: str
    period: str
    profile_tax_id: str
    status: object
    values: Mapping[str, str] | Iterable[object]
    findings: tuple[object, ...]


@runtime_checkable
class DraftLoader(Protocol):
    """Rebase-swap stub for ``aeat.filing.DraftLoader`` (#39)."""

    def load(self, draft_path: Path) -> FilingDraftLike:
        """Load and return the :class:`FilingDraftLike` at ``draft_path``."""
        ...


class Justificante(BaseModel):
    """Rebase-swap stub for ``aeat.justificante.Justificante`` (#44).

    Attributes:
        csv: The AEAT-issued CSV (código seguro de verificación).
        pdf_path: Local filesystem path where the justificante PDF
            was written.
    """

    model_config = _STRICT_FROZEN

    csv: str = Field(min_length=1)
    pdf_path: Path


@runtime_checkable
class JustificanteParser(Protocol):
    """Rebase-swap stub for ``aeat.justificante.JustificanteParser`` (#44)."""

    def parse(self, raw_bytes: bytes) -> Justificante:
        """Parse ``raw_bytes`` (a downloaded PDF) into a :class:`Justificante`."""
        ...
