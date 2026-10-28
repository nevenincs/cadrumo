"""The registered profile, session custody and operation host a Sede view test runs against.

The tax application owns how a profile with certificate-backed session custody
is built. The runtime tests consume that world through these ports and receive
it from the repository fixture, so they import no tax test support.
"""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager, AbstractContextManager
from pathlib import Path
from typing import Protocol
from uuid import UUID

from cadrumo.application.auth.certificate_secret_backend import CertificateSecretBackendFactory
from cadrumo.application.auth.operator_scope_ports import OperatorScopePorts
from cadrumo.core.operations import OperationEffect
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation


class ViewOperationHost(Protocol):
    """The effect guard and effect reporter the supervisor supplies to a session acquisition."""

    def effect_guard(self) -> AbstractAsyncContextManager[None]: ...

    async def report(self, effect: OperationEffect) -> None: ...


class ViewSessionWorld(Protocol):
    """A certificate-provider profile and the encrypted session stored for it."""

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
