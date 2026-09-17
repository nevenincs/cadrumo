"""Live AEAT session acquisition helpers.

This module is the shared read-only entry gate for application-live services.
It loads :class:`Settings`, enforces
:meth:`cadrumo.core.access_gate.gate.AeatAccessGate.require_live_read`, and only then
returns an authenticated :class:`AeatSession`. It never calls
``require_live_write`` and never performs AEAT-side mutations.

See Also:
    :class:`~cadrumo.core.access_gate.gate.AeatAccessGate`
        Core gate that authorizes pytest live reads and refuses all live writes.
    :func:`~cadrumo.application.auth.sessions.ensure_authenticated_aeat_session`
        Auth service called only after the read gate passes.
    :mod:`cadrumo.application.live`
        Public read-only live facade that routes remote acquisition helpers
        through this session boundary.
"""

from __future__ import annotations

from ...application.auth.certificate_secret_backend import CertificateSecretBackendFactory
from ...application.auth.operator_scope_ports import OperatorScopePorts
from ...application.auth.protocols import BrowserSessionFactoryPort
from ...application.auth.session_types import AeatSession
from ...application.auth.sessions import ensure_authenticated_aeat_session
from ...core.access_gate.gate import AeatAccessGate
from ...core.config import Settings, load_settings
from ...domain.calculations.registry.authority import bundled_indexed_authority


async def active_verified_session(
    *,
    certificate_secret_backend_factory: CertificateSecretBackendFactory,
    browser_session_factory: BrowserSessionFactoryPort,
    operation: str = "live-filed-read",
    target_url: str | None = None,
    operator_scope_ports: OperatorScopePorts,
    guarded_read_context: str | None = None,
) -> tuple[AeatSession, Settings]:
    """Return an authenticated session and :class:`Settings` after the live-read gate.

    The ``operation`` and optional ``target_url`` are forwarded to the
    authentication service for diagnostics and provider routing after
    :class:`AeatAccessGate` has authorized a read-only live operation.
    ``guarded_read_context`` names a guarded caller, such as a test run, whose
    read the gate refuses unless the live-test opt-in is enabled.
    """
    settings = load_settings()
    AeatAccessGate(settings).require_live_read(guarded_read_context=guarded_read_context)
    with bundled_indexed_authority().operation() as authority_operation:
        result = await ensure_authenticated_aeat_session(
            settings,
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            browser_session_factory=browser_session_factory,
            operation=operation,
            target_url=target_url,
            operator_scope_ports=operator_scope_ports,
            profile_decode_context=authority_operation.profile_decode_context(),
        )
    session: AeatSession = result.session
    return session, settings


__all__ = ["active_verified_session"]
