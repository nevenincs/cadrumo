"""Narrow Protocol surfaces and value types for the submission engine.

The submission engine is composed of read-only sub-systems that the
test suite exercises with concrete, hand-rolled Protocol-conforming
classes (no mocks, no patches). Each Protocol declares only the
surface the engine actually consumes, decoupling submission from the
richer surfaces of its sibling subpackages.

- ``ModeloIdentifier`` — typed validating string for an AEAT modelo.
- ``Portal`` / ``PortalCatalogue`` — minimal portal record / lookup
  contract; the submission engine reads only ``modelo`` and
  ``presentation_url``.
- ``AuthProviderProbe`` — narrow surface over
  :class:`aeat.auth.AuthProvider` for the preflight gate.
- ``CasillaRecord`` / ``CasillaCatalogue`` — minimal casilla
  record / lookup contract used by per-modelo submitters.
- ``DeadlineWindowChecker`` — narrow surface over
  :mod:`aeat.deadlines` used by preflight.
- ``FilingFinding`` / ``FilingDraftLike`` / ``DraftLoader`` — narrow
  filing draft surfaces; :class:`aeat.filing.FilingDraft`
  structurally conforms to ``FilingDraftLike``.
- ``Justificante`` / ``JustificanteParser`` — narrow record / parser
  surface for the post-submission acknowledgement.

Every record is either a strict+frozen pydantic v2 model or a
``runtime_checkable`` ``Protocol``; no dataclasses; no bare dicts.
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

from ..auth import AuthProviderDescription, AuthProviderKind
from ..i18n import Translatable

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")

_MODELO_RE = re.compile(r"^\d{3}[A-Z]?$")


class ModeloIdentifier(str):
    """Typed string identifier for an AEAT modelo (e.g. ``"130"``, ``"303"``).

    Shape-compatible with :class:`aeat.deadlines.ModeloIdentifier`.
    Intentionally wider than :class:`aeat.models.ModeloCode`: any
    well-formed three-digit modelo identifier is accepted, including
    modelos outside the v1 closed catalogue.
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
    """Minimal portal record consumed by per-modelo submitters.

    Captures only the modelo + presentation URL pair the engine drives
    at submit time. Distinct from :class:`aeat.portals.PortalMetadata`,
    which carries the full curated metadata graph used by the catalogue
    integrity invariants and by the live-sync engine.

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
    """Lookup contract for the engine's narrow :class:`Portal` records."""

    def portal_for(self, modelo: str) -> Portal:
        """Return the :class:`Portal` that serves ``modelo``."""
        ...


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
    """Minimal casilla record consumed by per-modelo submitters.

    Captures only the (id, label, input_kind) tuple the engine drives
    a portal form against. Distinct from
    :class:`aeat.casillas.CasillaRecord`, which carries the curated
    catalogue's wider provenance fields.

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
    """Lookup contract for the engine's narrow :class:`CasillaRecord` records."""

    def casillas_for_modelo(self, modelo: str) -> tuple[CasillaRecord, ...]:
        """Return the tuple of casillas registered for ``modelo``."""
        ...

    def get(self, casilla_id: str) -> CasillaRecord:
        """Return the :class:`CasillaRecord` with ``casilla_id``."""
        ...


@runtime_checkable
class DeadlineWindowChecker(Protocol):
    """Narrow surface over :mod:`aeat.deadlines` for the preflight gate."""

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
    """Minimal finding record consumed by the preflight gate.

    Distinct from :class:`aeat.filing.FilingValidationFinding`, which
    carries the validator's full provenance graph; the submission
    engine reads only ``severity`` to decide whether the draft is
    blocked.

    Attributes:
        severity: The finding severity; ``ERROR`` blocks submission.
        message: Trilingual finding message.
    """

    model_config = _STRICT_FROZEN

    severity: FilingFindingSeverity
    message: Translatable


class DraftStatus(StrEnum):
    """Mirror of :class:`aeat.filing.FilingDraftStatus` for preflight.

    Kept in sync with the source enum; the engine uses only the
    ``APPROVED`` and ``APPROVAL_STALE`` members on its happy path.
    """

    DRAFT = "DRAFT"
    VALIDATED = "VALIDATED"
    READY_TO_SUBMIT = "READY_TO_SUBMIT"
    APPROVED = "APPROVED"
    APPROVAL_STALE = "APPROVAL_STALE"
    SUBMITTED = "SUBMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    REJECTED = "REJECTED"
    AMENDED = "AMENDED"
    CANCELLED = "CANCELLED"


@runtime_checkable
class FilingDraftLike(Protocol):
    """Narrow surface over a filing draft.

    :class:`aeat.filing.FilingDraft` structurally conforms to this
    Protocol so the engine can accept either the real draft or any
    Protocol-conforming hand-rolled class in tests.
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
    """Loads a :class:`FilingDraftLike` from a draft path on disk."""

    def load(self, draft_path: Path) -> FilingDraftLike:
        """Load and return the :class:`FilingDraftLike` at ``draft_path``."""
        ...


class Justificante(BaseModel):
    """Minimal justificante record consumed by the engine's transport.

    Distinct from :class:`aeat.justificante.Justificante`, which carries
    the full parsed receipt graph (modelo, period, presented_at, total
    amounts, source PDF sha256, ...). The submission engine only
    threads (csv, pdf_path) through to the persisted
    :class:`aeat.submission.SubmittedFiling` record; downstream
    consumers re-parse the PDF via :mod:`aeat.justificante` for the
    richer surface.

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
    """Parses raw PDF bytes into the engine's narrow :class:`Justificante`."""

    def parse(self, raw_bytes: bytes) -> Justificante:
        """Parse ``raw_bytes`` (a downloaded PDF) into a :class:`Justificante`."""
        ...
