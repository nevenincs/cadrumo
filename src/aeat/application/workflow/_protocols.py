"""Protocol contracts for every component the workflow engine composes.

The composite workflow engine is defined against ``typing.Protocol``
surfaces — not concrete classes — for two reasons:

1. **Cross-subpackage decoupling.** Each Protocol lets the workflow
   engine integrate with an in-house subpackage without forcing a
   hard import dependency at the engine layer; adapters in
   :mod:`aeat.application.workflow._adapters` translate the richer real surfaces
   onto these narrow Protocols.
2. **No-mocks testing.** The project forbids mocks/patches/fakes/stubs
   in its test suite. Protocols let us substitute hand-rolled
   Protocol-conforming classes in tests instead, one per scenario.

Every Protocol here describes **only** the attributes the workflow
engine actually reads.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from ...adapters.outbound.aeat.export import AuthProviderDescription, FilingDraftLike
from ...domain.deadlines import AutonomoProfile, Schedule

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


@runtime_checkable
class DeadlineEngineProtocol(Protocol):
    """Narrow surface over :class:`aeat.domain.deadlines.DeadlineEngine`."""

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
    """Narrow surface over :func:`aeat.application.filing.build_draft`."""

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


@runtime_checkable
class SubmissionEngineProtocol(Protocol):
    """Read-only preflight surface over :class:`aeat.adapters.outbound.aeat.export.SubmissionEngine`."""

    def preflight(self, draft: FilingDraftLike, *, today: date) -> None:
        """Run preflight gates against ``draft``; raise on failure."""
        ...


class SyncRunSummary(BaseModel):
    """Narrow contract for a sync run outcome.

    The workflow engine only needs to know whether the sync succeeded
    and surface a numeric summary for diagnostics; the full
    :class:`aeat.application.sync.SyncRunResult` graph is intentionally not
    imported here.
    """

    model_config = _STRICT_FROZEN

    divergence_count: int = Field(ge=0)
    auto_healed_count: int = Field(ge=0)
    escalated_count: int = Field(ge=0)


@runtime_checkable
class SyncRunnerProtocol(Protocol):
    """Narrow surface over :class:`aeat.application.sync.LiveSyncRunner`."""

    async def run(
        self,
        *,
        modelo: str | None = None,
        period: str | None = None,
        auto_heal: bool = False,
    ) -> SyncRunSummary:
        """Execute one sync cycle and return a narrow summary."""
        ...


@runtime_checkable
class CertificateBundleProtocol(Protocol):
    """Narrow contract for the auth-provider probe used by workflow preflight.

    The workflow engine calls :meth:`describe` once during the
    preflight stage to prove the configured auth provider is present
    and healthy. Any exception raised here is translated into
    :attr:`aeat.application.workflow.WorkflowAbortReason.CERT_INVALID` to preserve
    the existing workflow abort taxonomy.
    """

    def describe(self) -> AuthProviderDescription:
        """Return the current auth-provider description; raise on failure."""
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
    "FilingDraftBuilderProtocol",
    "FilingInputsProviderProtocol",
    "SubmissionEngineProtocol",
    "SyncRunSummary",
    "SyncRunnerProtocol",
]
