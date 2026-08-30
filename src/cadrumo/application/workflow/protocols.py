"""Protocol contracts for every component the workflow engine composes.

The composite workflow engine is defined against ``typing.Protocol``
surfaces — not concrete classes — for two reasons:

1. **Cross-subpackage decoupling.** Each Protocol lets the workflow
   engine integrate with an in-house subpackage without forcing a
   hard import dependency at the engine layer; adapters in
   :mod:`application.workflow.adapters` translate the richer real surfaces
   onto these narrow Protocols.
2. **Protocol-shaped tests.** Tests can supply narrow
   Protocol-conforming classes per scenario without importing the
   production adapters at the workflow layer.

Every Protocol here describes **only** the attributes the workflow
engine actually reads. :class:`DeadlineEngineProtocol` wraps the
deadline engine's ``compute`` method that returns a :class:`Schedule`
for a given :class:`TaxpayerProfile`.

See Also:
    :class:`~application.workflow.WorkflowEngine`
        Orchestrates these contracts stage by stage.
    :mod:`application.workflow.adapters`
        Adapts production deadline, draft-building, submission, and live-read
        components to these contracts.
    :class:`~domain.submission.SubmissionEngine`
        Implements the read-only preflight surface described by
        :class:`SubmissionEngineProtocol`.
    :class:`~application.workflow.WorkflowPurpose`
        Decides when workflow callers skip the AEAT filing-window preflight
        gate for local verification or local mark-as-filed paths.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from datetime import date
from typing import Protocol, override, runtime_checkable

from ...core import AuthProviderDescription
from ...core.period import Period
from ...core.errors.severity import BaseSeverity
from ...domain.deadlines.models import Schedule, TaxpayerProfile

# ``ModeloInputs`` and its element aliases are domain-owned input contracts.
# This module consumes them for its protocol annotations; callers import them
# directly from :mod:`cadrumo.domain.filing`.
from ...domain.filing.protocols import ModeloInputs
from ...domain.submission import ModeloDraftLike


@runtime_checkable
class WorkflowFindingLike(Protocol):
    """Narrow structural port over one registry-backed draft finding.

    Wider than :class:`domain.submission.ModeloFindingLike`, which declares
    only ``severity`` -- the preflight gate's minimal
    :class:`domain.submission.ModeloFinding` carries no ``code``. Every
    finding a :class:`RegistryModeloDraftProtocol` draft actually carries is
    a :class:`domain.filing.ModeloValidationFinding`, which declares both
    ``severity`` and ``code`` as required fields with no default. Typing
    :attr:`RegistryModeloDraftProtocol.findings` through this Protocol lets
    workflow-layer readers use ``finding.severity`` / ``finding.code``
    directly instead of a ``getattr(..., None)`` guess -- a field rename now
    fails loud instead of silently excluding every finding from whatever
    reads through it.
    """

    @property
    def severity(self) -> BaseSeverity:
        """Return the severity that the workflow preflight should report."""
        ...

    @property
    def code(self) -> str:
        """Return the stable registry code identifying this finding."""
        ...


@runtime_checkable
class DeadlineEngineProtocol(Protocol):
    """Narrow surface over :class:`domain.deadlines.DeadlineEngine`."""

    def compute(
        self,
        profile: TaxpayerProfile,
        year: int,
        *,
        today: date | None = None,
    ) -> Schedule:
        """Return a :class:`Schedule` for ``profile`` in ``year``.

        Args:
            profile: The :class:`TaxpayerProfile` whose filing obligations are scheduled.
            year: The calendar year for which the schedule is computed.
            today: Optional reference date for open-period classification.
        """
        ...


@runtime_checkable
class RegistryModeloDraftProtocol(ModeloDraftLike, Protocol):
    """Workflow draft surface after registry-backed filing construction."""

    schema_version: str

    @property
    @override
    def findings(self) -> tuple[WorkflowFindingLike, ...]: ...


@runtime_checkable
class ModeloDraftBuilderProtocol(Protocol):
    """Narrow surface over :func:`application.filing.build_draft`."""

    def build(
        self,
        *,
        modelo: str,
        period: Period,
        profile: TaxpayerProfile,
        inputs: ModeloInputs,
        fail_on_warning: bool = False,
    ) -> RegistryModeloDraftProtocol:
        """Build a registry-backed filing draft for the given :class:`TaxpayerProfile`.

        Returns a :class:`RegistryModeloDraftProtocol`.
        """
        ...


@runtime_checkable
class SubmissionEngineProtocol(Protocol):
    """Read-only preflight surface over :class:`~domain.submission.SubmissionEngine`."""

    def preflight(
        self,
        draft: RegistryModeloDraftProtocol,
        *,
        today: date,
        skip_deadline_window: bool = False,
        skip_auth_readiness: bool = False,
    ) -> None:
        """Run preflight gates against ``draft``; raise on failure.

        ``skip_deadline_window`` skips the AEAT filing-window gate. The
        local workflow uses this for both :attr:`WorkflowPurpose.VERIFY`
        and :attr:`WorkflowPurpose.FILE`: VERIFY is calendar-independent,
        while FILE is a local mark-as-filed path whose obligation existence
        has already been enforced by the deadline stage.

        ``skip_auth_readiness`` skips the auth-provider readiness gate. Both
        workflow purposes are local (the app never performs an actual AEAT
        submission), so auth is not required to complete the local
        build/verify/file/export flow; only live/AEAT-touching callers keep
        the gate enabled.
        """
        ...


@runtime_checkable
class CertificateBundleProtocol(Protocol):
    """Narrow contract for the auth-provider probe used by workflow preflight.

    The workflow engine calls :meth:`describe` once during the
    preflight stage to prove the configured auth provider is present
    and healthy. Any exception raised here is translated into
    :attr:`application.workflow.WorkflowAbortReason.CERT_INVALID` to preserve
    the existing workflow abort taxonomy.
    """

    def describe(self) -> AuthProviderDescription:
        """Return the current auth-provider description; raise on failure.

        Returns a :class:`core.AuthProviderDescription` with the provider's
        configured and available state.
        """
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
        period: Period,
        profile: TaxpayerProfile,
    ) -> ModeloInputs:
        """Return the filing inputs for the draft build against the given :class:`TaxpayerProfile`."""
        ...


class WorkflowExpedienteProtocol(Protocol):
    """Narrow read surface for one AEAT expediente (open proceeding) entry.

    An expediente is an administrative dossier AEAT associates with one
    modelo (e.g. ``"303"``) and one ejercicio (tax year). The workflow
    engine reads these two fields to decide whether an open proceeding
    blocks filing.
    """

    @property
    def modelo(self) -> str | None:
        """Return the expediente's modelo identifier, when declared."""
        ...

    @property
    def ejercicio(self) -> int | None:
        """Return the expediente's tax year, when declared."""
        ...


class WorkflowNotificationProtocol(Protocol):
    """Narrow read surface for one AEAT inbox notification entry.

    The workflow engine reads ``tipo``, ``leida``, ``certificado_id``,
    and ``concepto`` to decide whether an unread blocking notification
    (typically a requerimiento) should abort the current run.
    """

    @property
    def tipo(self) -> str:
        """Return the AEAT notification type."""
        ...

    @property
    def leida(self) -> bool | None:
        """Return whether the source marks this notification as read."""
        ...

    @property
    def certificado_id(self) -> str:
        """Return the certificate identifier associated with the notification."""
        ...

    @property
    def concepto(self) -> str:
        """Return the notification's concept or subject."""
        ...


class WorkflowNotificationsSnapshotProtocol(Protocol):
    """Container protocol for a point-in-time AEAT inbox snapshot.

    Wraps a sequence of :class:`WorkflowNotificationProtocol` rows returned
    by the AEAT inbox adapter. The engine iterates ``rows`` once to find
    blocking requerimientos.
    """

    @property
    def rows(self) -> Sequence[WorkflowNotificationProtocol]:
        """Return the notification rows contained in this snapshot."""
        ...


type ExpedientesSource = Callable[[object, str | None], Awaitable[tuple[WorkflowExpedienteProtocol, ...]]]
"""Async callable that fetches open expedientes for a session.

Args:
    arg0: The authenticated AEAT session object.
    arg1: Optional modelo filter; ``None`` returns all open expedientes.

Returns:
    A tuple of :class:`WorkflowExpedienteProtocol` entries.
"""

type NotificationsSource = Callable[[object], Awaitable[WorkflowNotificationsSnapshotProtocol]]
"""Async callable that fetches the AEAT inbox snapshot for a session.

Args:
    arg0: The authenticated AEAT session object.

Returns:
    A :class:`WorkflowNotificationsSnapshotProtocol` with all current
    notification rows.
"""


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
    "WorkflowFindingLike",
    "WorkflowNotificationProtocol",
    "WorkflowNotificationsSnapshotProtocol",
]
