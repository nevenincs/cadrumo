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

from collections.abc import Awaitable, Callable, Sequence
from datetime import date
from typing import Protocol, runtime_checkable

from ...adapters.outbound.aeat.export import ModeloDraftLike
from ...application.auth import AuthProviderDescription
from ...domain.deadlines import Schedule, TaxpayerProfile

# ``ModeloInputs`` and its element aliases have a single canonical
# definition in :mod:`aeat.domain.filing._protocols`. The workflow
# engine re-exports them here so adapters can import the contract from
# the workflow package without taking a second divergent definition.
from ...domain.filing import ModeloInputs, ModeloInputScalar, ModeloInputValue


@runtime_checkable
class DeadlineEngineProtocol(Protocol):
    """Narrow surface over :class:`aeat.domain.deadlines.DeadlineEngine`."""

    def compute(
        self,
        profile: TaxpayerProfile,
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
        profile: TaxpayerProfile,
        inputs: ModeloInputs,
        fail_on_warning: bool = False,
    ) -> RegistryModeloDraftProtocol:
        """Build and return a registry-backed filing draft."""
        ...


@runtime_checkable
class SubmissionEngineProtocol(Protocol):
    """Read-only preflight surface over :class:`aeat.adapters.outbound.aeat.export.SubmissionEngine`."""

    def preflight(
        self,
        draft: RegistryModeloDraftProtocol,
        *,
        today: date,
        skip_deadline_window: bool = False,
    ) -> None:
        """Run preflight gates against ``draft``; raise on failure.

        ``skip_deadline_window`` skips the AEAT filing-window gate so a
        calculation can be verified independently of the filing
        calendar; filing always runs the window gate.
        """
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
        profile: TaxpayerProfile,
    ) -> ModeloInputs:
        """Return the filing inputs for the draft build."""
        ...


class WorkflowExpedienteProtocol(Protocol):
    @property
    def modelo(self) -> str | None: ...

    @property
    def ejercicio(self) -> int | None: ...


class WorkflowNotificationProtocol(Protocol):
    @property
    def tipo(self) -> str: ...

    @property
    def leida(self) -> bool | None: ...

    @property
    def certificado_id(self) -> str: ...

    @property
    def concepto(self) -> str: ...


class WorkflowNotificationsSnapshotProtocol(Protocol):
    @property
    def rows(self) -> Sequence[WorkflowNotificationProtocol]: ...


ExpedientesSource = Callable[[object, str | None], Awaitable[tuple[WorkflowExpedienteProtocol, ...]]]
NotificationsSource = Callable[[object], Awaitable[WorkflowNotificationsSnapshotProtocol]]


# Re-exported for adapter convenience (tests use the fully-qualified
# path directly, so this exists purely to keep `_adapters.py` tidy).
__all__ = [
    "CertificateBundleProtocol",
    "DeadlineEngineProtocol",
    "ExpedientesSource",
    "ModeloDraftBuilderProtocol",
    "ModeloInputScalar",
    "ModeloInputValue",
    "ModeloInputs",
    "ModeloInputsProviderProtocol",
    "NotificationsSource",
    "RegistryModeloDraftProtocol",
    "SubmissionEngineProtocol",
    "WorkflowExpedienteProtocol",
    "WorkflowNotificationProtocol",
    "WorkflowNotificationsSnapshotProtocol",
]
