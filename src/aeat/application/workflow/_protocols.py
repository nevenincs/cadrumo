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
engine actually reads. :class:`DeadlineEngineProtocol` wraps the
deadline engine's ``compute`` method that returns a :class:`Schedule`
for a given :class:`TaxpayerProfile`.

See Also:
    :class:`~aeat.application.workflow.WorkflowEngine`
        Orchestrates these contracts stage by stage.
    :mod:`aeat.application.workflow._adapters`
        Adapts production deadline, draft-building, submission, and live-read
        components to these contracts.
    :class:`~aeat.domain.submission.SubmissionEngine`
        Implements the read-only preflight surface described by
        :class:`SubmissionEngineProtocol`.
    :class:`~aeat.application.workflow.WorkflowPurpose`
        Decides when workflow callers skip the AEAT filing-window preflight
        gate for local verification or local mark-as-filed paths.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from datetime import date
from typing import Protocol, runtime_checkable

from ...application.auth import AuthProviderDescription
from ...core import Period
from ...domain.deadlines import Schedule, TaxpayerProfile

# ``ModeloInputs`` and its element aliases have a single canonical
# definition in :mod:`aeat.domain.filing._protocols`. The workflow
# engine re-exports them here so adapters can import the contract from
# the workflow package without taking a second divergent definition.
from ...domain.filing import ModeloInputs, ModeloInputScalar, ModeloInputValue
from ...domain.submission._protocols import ModeloDraftLike


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


@runtime_checkable
class ModeloDraftBuilderProtocol(Protocol):
    """Narrow surface over :func:`aeat.application.filing.build_draft`."""

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
    """Read-only preflight surface over :class:`~aeat.domain.submission.SubmissionEngine`."""

    def preflight(
        self,
        draft: RegistryModeloDraftProtocol,
        *,
        today: date,
        skip_deadline_window: bool = False,
    ) -> None:
        """Run preflight gates against ``draft``; raise on failure.

        ``skip_deadline_window`` skips the AEAT filing-window gate. The
        local workflow uses this for both :attr:`WorkflowPurpose.VERIFY`
        and :attr:`WorkflowPurpose.FILE`: VERIFY is calendar-independent,
        while FILE is a local mark-as-filed path whose obligation existence
        has already been enforced by the deadline stage.
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
        """Return the current auth-provider description; raise on failure.

        Returns an :class:`AuthProviderDescription` with the provider's
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
    def modelo(self) -> str | None: ...

    @property
    def ejercicio(self) -> int | None: ...


class WorkflowNotificationProtocol(Protocol):
    """Narrow read surface for one AEAT inbox notification entry.

    The workflow engine reads ``tipo``, ``leida``, ``certificado_id``,
    and ``concepto`` to decide whether an unread blocking notification
    (typically a requerimiento) should abort the current run.
    """

    @property
    def tipo(self) -> str: ...

    @property
    def leida(self) -> bool | None: ...

    @property
    def certificado_id(self) -> str: ...

    @property
    def concepto(self) -> str: ...


class WorkflowNotificationsSnapshotProtocol(Protocol):
    """Container protocol for a point-in-time AEAT inbox snapshot.

    Wraps a sequence of :class:`WorkflowNotificationProtocol` rows returned
    by the AEAT inbox adapter. The engine iterates ``rows`` once to find
    blocking requerimientos.
    """

    @property
    def rows(self) -> Sequence[WorkflowNotificationProtocol]: ...


ExpedientesSource = Callable[[object, str | None], Awaitable[tuple[WorkflowExpedienteProtocol, ...]]]
"""Async callable that fetches open expedientes for a session.

Args:
    arg0: The authenticated AEAT session object.
    arg1: Optional modelo filter; ``None`` returns all open expedientes.

Returns:
    A tuple of :class:`WorkflowExpedienteProtocol` entries.
"""

NotificationsSource = Callable[[object], Awaitable[WorkflowNotificationsSnapshotProtocol]]
"""Async callable that fetches the AEAT inbox snapshot for a session.

Args:
    arg0: The authenticated AEAT session object.

Returns:
    A :class:`WorkflowNotificationsSnapshotProtocol` with all current
    notification rows.
"""


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
