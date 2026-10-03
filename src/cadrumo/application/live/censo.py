"""Authenticated, read-only censo acquisition from AEAT.

The returned observation is not adopted until the user-profile workflow reviews
and commits it through its separate canonical authority.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import TYPE_CHECKING

from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ..auth.certificate_secret_backend import CertificateSecretBackendFactory
from ..auth.operator_scope_ports import OperatorScopePorts
from ..auth.protocols import BrowserSessionFactoryPort
from .censo_ports import CensalFetchPort
from .session import SessionWriteReporter, active_verified_session

if TYPE_CHECKING:
    from ..user_profile.censal_observation import CensalObservation

LIVE_CENSAL_READ_OPERATION = "live-censal-read"


async def pull_censal_datos(
    *,
    certificate_secret_backend_factory: CertificateSecretBackendFactory,
    browser_session_factory: BrowserSessionFactoryPort,
    operator_scope_ports: OperatorScopePorts,
    censal_fetch_port: CensalFetchPort,
    guarded_read_context: str | None = None,
    authority_operation: PinnedAuthorityOperation | None = None,
    effect_guard: Callable[[], AbstractAsyncContextManager[None]] | None = None,
    on_session_write: SessionWriteReporter | None = None,
) -> CensalObservation:
    """Read the authenticated taxpayer's censo state without persisting or adopting it."""
    session, settings = await active_verified_session(
        certificate_secret_backend_factory=certificate_secret_backend_factory,
        browser_session_factory=browser_session_factory,
        operation=LIVE_CENSAL_READ_OPERATION,
        operator_scope_ports=operator_scope_ports,
        guarded_read_context=guarded_read_context,
        authority_operation=authority_operation,
        effect_guard=effect_guard,
        on_session_write=on_session_write,
    )
    return await censal_fetch_port(session, taxpayer_nif=session.identity_nif, settings=settings)


__all__ = ["LIVE_CENSAL_READ_OPERATION", "pull_censal_datos"]
