"""Protocol contracts for every component the workflow engine composes.

The composite workflow engine is defined against ``typing.Protocol``
surfaces — not concrete classes — for two reasons:

1. **Cross-subpackage decoupling.** Each Protocol lets the workflow
   engine integrate with an in-house subpackage without forcing a
   hard import dependency at the engine layer; adapters in
   :mod:`aeat.application.workflow._adapters` translate the richer real surfaces
   onto these narrow Protocols.
2. **Protocol-shaped tests.** Tests can supply narrow
   Protocol-conforming classes per scenario without importing the
   production adapters at the workflow layer.

Every Protocol here describes **only** the attributes the workflow
engine actually reads.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import date
from typing import Protocol, runtime_checkable

from ...adapters.outbound.aeat.export import ModeloDraftLike
from ...application.auth import AuthProviderDescription
from ...domain.deadlines import AutonomoProfile, Schedule


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
class RegistryModeloDraftProtocol(ModeloDraftLike, Protocol):
    """Workflow draft surface after registry-backed filing construction."""

    schema_version: str


@runtime_checkable
class ModeloDraftBuilderProtocol(Protocol):
    """Narrow surface over :func:`aeat.application.filing.build_draft`."""

    def build(
        self,
        *,
        modelo: str,
        period: str,
        profile: AutonomoProfile,
        inputs: Mapping[str, object],
        fail_on_warning: bool = False,
    ) -> RegistryModeloDraftProtocol:
        """Build and return a registry-backed filing draft."""
        ...


@runtime_checkable
class SubmissionEngineProtocol(Protocol):
    """Read-only preflight surface over :class:`aeat.adapters.outbound.aeat.export.SubmissionEngine`."""

    def preflight(self, draft: RegistryModeloDraftProtocol, *, today: date) -> None:
        """Run preflight gates against ``draft``; raise on failure."""
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
class ModeloInputsProviderProtocol(Protocol):
    """Provides filing inputs for the draft stage.

    Production adapters load inputs from bucket-scoped, secure application
    services rather than operator-supplied files.
    """

    def load_inputs(
        self,
        *,
        modelo: str,
        period: str,
        profile: AutonomoProfile,
    ) -> Mapping[str, object]:
        """Return the filing inputs for the draft build."""
        ...


class WorkflowExpedienteProtocol(Protocol):
    modelo: str | None
    ejercicio: int | None


class WorkflowNotificationProtocol(Protocol):
    tipo: str
    leida: bool | None
    certificado_id: str
    concepto: str


class WorkflowNotificationsSnapshotProtocol(Protocol):
    rows: Sequence[WorkflowNotificationProtocol]


ExpedientesSource = Callable[[object, str | None], Awaitable[tuple[WorkflowExpedienteProtocol, ...]]]
NotificationsSource = Callable[[object], Awaitable[WorkflowNotificationsSnapshotProtocol]]


# Re-exported for adapter convenience (tests use the fully-qualified
# path directly, so this exists purely to keep `_adapters.py` tidy).
__all__ = [
    "CertificateBundleProtocol",
    "DeadlineEngineProtocol",
    "ExpedientesSource",
    "ModeloDraftBuilderProtocol",
    "ModeloInputsProviderProtocol",
    "NotificationsSource",
    "RegistryModeloDraftProtocol",
    "SubmissionEngineProtocol",
    "WorkflowExpedienteProtocol",
    "WorkflowNotificationProtocol",
    "WorkflowNotificationsSnapshotProtocol",
]
