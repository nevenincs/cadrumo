"""The registered profile, session custody, browser and supervision a Sede view test runs against.

The tax application owns how a profile with certificate-backed session custody
is built. The runtime tests consume that world through these ports and receive
it from the repository fixture, so they import no tax test support.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager, AbstractContextManager
from pathlib import Path
from typing import Protocol
from uuid import UUID

from cadrumo.application.auth.certificate_secret_backend import CertificateSecretBackendFactory
from cadrumo.application.auth.operator_scope_ports import OperatorScopePorts
from cadrumo.application.auth.protocols import BrowserSessionFactoryPort
from cadrumo.application.operations.models import OperationId
from cadrumo.application.operations.persistence.journal import OperationPersistedSnapshot
from cadrumo.application.operations.supervisor import OperationSupervisor
from cadrumo.core.operations import OperationEffect
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation


class ViewOperationHost(Protocol):
    """The effect guard and effect reporter the supervisor supplies to a session acquisition."""

    def effect_guard(self) -> AbstractAsyncContextManager[None]: ...

    async def report(self, effect: OperationEffect) -> None: ...


class ViewHttpBoundary(Protocol):
    """The local HTTP origin a view test's browsers reach in place of the Sede."""

    def browser_session_factory(self, *, profile_name: str) -> BrowserSessionFactoryPort:
        """A factory of production browser sessions that reach this origin instead of the Sede."""
        ...


class ViewSessionWorld(Protocol):
    """A certificate-provider profile, the encrypted session stored for it and the means to drive a view."""

    @property
    def profile_id(self) -> UUID: ...

    @property
    def certificate_secret_backend_factory(self) -> CertificateSecretBackendFactory: ...

    @property
    def operator_scope_ports(self) -> OperatorScopePorts: ...

    def registered_profile(self, tmp_path: Path, operation: PinnedAuthorityOperation) -> AbstractContextManager[None]:
        """Register and unlock the profile for the duration of the context."""
        ...

    def operation_host(self) -> ViewOperationHost:
        """A fresh host for one session acquisition."""
        ...

    def stored_digest(self) -> str | None:
        """The stored session's ``storage_state_sha256``, or ``None`` when none is stored."""
        ...

    def stored_cookie_names(self) -> set[str]:
        """The cookie names in the stored session."""
        ...

    def opened_http_boundary(self) -> AbstractAsyncContextManager[ViewHttpBoundary]:
        """Serve the local HTTP origin for the duration of the context."""
        ...

    async def until(self, condition: Callable[[], bool], *, timeout: float) -> None:
        """Wait until ``condition`` holds, failing the test after ``timeout`` seconds."""
        ...

    async def run_to_settlement(
        self, supervisor: OperationSupervisor, operation_id: OperationId
    ) -> OperationPersistedSnapshot:
        """Start ``operation_id`` and return what its supervised task concluded, raising the error that stopped it."""
        ...
