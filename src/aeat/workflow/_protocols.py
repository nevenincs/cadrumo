"""Protocol stubs for every component the workflow engine composes.

The composite workflow engine is defined against ``typing.Protocol``
surfaces — not concrete classes — for two reasons:

1. **In-flight-branch rebase safety.** The status reader (#43), the
   notifications inbox (#46), and the certificate auth backend (#8)
   are still in flight on sibling branches. Hard-importing them would
   either break the build or require speculative scaffolding in their
   territory. Protocols let this subpackage compile and test standalone
   today and pick up the real implementations via constructor injection
   when they land.
2. **No-mocks testing.** The project forbids mocks/patches/fakes/stubs
   in its test suite. Protocols let us substitute hand-rolled
   Protocol-conforming classes in tests instead, one per scenario.

Every Protocol here describes **only** the attributes the workflow
engine actually reads. The adapter wrappers in
:mod:`aeat.workflow._adapters` translate the richer real surfaces onto
these narrow Protocols. Small companion pydantic v2 stubs model
in-flight types (``ExpedienteLike``, ``RequerimientoLike``,
``SubmittedFilingLike``) so the schema-strict workflow can round-trip
them.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from ..deadlines import AutonomoProfile, Schedule
from ..submission import FilingDraftLike, LoadedCertificate

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


@runtime_checkable
class DeadlineEngineProtocol(Protocol):
    """Narrow surface over :class:`aeat.deadlines.DeadlineEngine`."""

    def compute(
        self,
        profile: AutonomoProfile,
        year: int,
        *,
        today: date | None = None,
    ) -> Schedule:
        """Return a :class:`Schedule` for ``profile`` in ``year``."""
        ...


@runtime_checkable
class FilingDraftBuilderProtocol(Protocol):
    """Narrow surface over :func:`aeat.filing.build_draft`."""

    def build(
        self,
        *,
        modelo: str,
        period: str,
        profile: AutonomoProfile,
        inputs: Mapping[str, object],
        fail_on_warning: bool = False,
    ) -> FilingDraftLike:
        """Build and return a :class:`FilingDraftLike`."""
        ...


class SubmittedFilingLike(BaseModel):
    """Narrow pydantic v2 stub for a submitted filing.

    The workflow engine records only the identifier and status of a
    dry-run or live submission attempt, so the full
    :class:`aeat.submission.SubmittedFiling` is intentionally not
    imported here — the adapter projects the relevant fields.
    """

    model_config = _STRICT_FROZEN

    submission_id: str = Field(min_length=1)
    draft_id: str = Field(min_length=1)
    modelo: str = Field(min_length=1)
    period: str = Field(min_length=1)
    status: str = Field(min_length=1)
    submitted_at: datetime


@runtime_checkable
class SubmissionEngineProtocol(Protocol):
    """Narrow surface over :class:`aeat.submission.SubmissionEngine`."""

    def preflight(self, draft: FilingDraftLike, *, today: date) -> None:
        """Run preflight gates against ``draft``; raise on failure."""
        ...

    async def submit_draft(
        self,
        draft: FilingDraftLike,
        *,
        dry_run: bool,
        today: date | None = None,
    ) -> SubmittedFilingLike:
        """Submit ``draft`` with an explicit dry-run choice."""
        ...


class SyncRunSummary(BaseModel):
    """Narrow stub for a sync run outcome.

    The workflow engine only needs to know whether the sync succeeded
    and surface a numeric summary for diagnostics; the full
    :class:`aeat.sync.SyncRunResult` graph is intentionally not
    imported here.
    """

    model_config = _STRICT_FROZEN

    divergence_count: int = Field(ge=0)
    auto_healed_count: int = Field(ge=0)
    escalated_count: int = Field(ge=0)


@runtime_checkable
class SyncRunnerProtocol(Protocol):
    """Narrow surface over :class:`aeat.sync.LiveSyncRunner`."""

    async def run(
        self,
        *,
        modelo: str | None = None,
        period: str | None = None,
        auto_heal: bool = False,
    ) -> SyncRunSummary:
        """Execute one sync cycle and return a narrow summary."""
        ...


class ExpedienteLike(BaseModel):
    """Narrow stub for the status-reader's expediente record (#43)."""

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1)
    period: str = Field(min_length=1)
    tax_id: str = Field(min_length=1)
    filed_at: datetime | None = None


@runtime_checkable
class StatusReaderProtocol(Protocol):
    """Narrow stub for the live status reader (#43, in flight)."""

    async def fetch_expedientes(self, *, tax_id: str) -> tuple[ExpedienteLike, ...]:
        """Return every expediente currently attached to ``tax_id``."""
        ...


class RequerimientoLike(BaseModel):
    """Narrow stub for an inbox requerimiento (#46, in flight)."""

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1)
    notificacion_id: str = Field(min_length=1)
    received_at: datetime
    blocks_submission: bool = True
    subject: str = ""


@runtime_checkable
class InboxProtocol(Protocol):
    """Narrow stub for the notifications inbox (#46, in flight)."""

    async def fetch_blocking_requerimientos(
        self,
        *,
        tax_id: str,
        modelo: str,
    ) -> tuple[RequerimientoLike, ...]:
        """Return any blocking requerimientos for ``(tax_id, modelo)``."""
        ...


@runtime_checkable
class CertificateBundleProtocol(Protocol):
    """Narrow stub for the certificate auth backend (#8, in flight).

    The workflow engine calls :meth:`load` once during the preflight
    stage to prove the certificate is present and decodable. Any
    exception raised here is translated into
    :attr:`aeat.workflow.WorkflowAbortReason.CERT_INVALID`.
    """

    def load(self) -> LoadedCertificate:
        """Return the active loaded certificate; raise on failure."""
        ...


@runtime_checkable
class FilingInputsProviderProtocol(Protocol):
    """Provides raw casilla inputs for the draft stage.

    The default adapter reads the inputs from a JSON file at
    ``settings.aeat_workflow_draft_inputs_path``; tests inject a
    hand-rolled Protocol-conforming provider to control the shape.
    """

    def load_inputs(
        self,
        *,
        modelo: str,
        period: str,
        profile: AutonomoProfile,
    ) -> Mapping[str, object]:
        """Return the raw casilla inputs for the draft build."""
        ...


# Re-exported for adapter convenience (tests use the fully-qualified
# path directly, so this exists purely to keep `_adapters.py` tidy).
__all__ = [
    "CertificateBundleProtocol",
    "DeadlineEngineProtocol",
    "ExpedienteLike",
    "FilingDraftBuilderProtocol",
    "FilingInputsProviderProtocol",
    "InboxProtocol",
    "RequerimientoLike",
    "StatusReaderProtocol",
    "SubmissionEngineProtocol",
    "SubmittedFilingLike",
    "SyncRunSummary",
    "SyncRunnerProtocol",
]
