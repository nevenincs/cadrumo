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

from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager, nullcontext

from ...core.access_gate.gate import AeatAccessGate
from ...core.config import Settings, load_settings
from ...core.errors.hierarchy import InternalInvariantError
from ...core.operations import OperationEffect
from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...domain.calculations.registry.authority_artifact import ProfileDecodeContext
from ..auth.certificate_secret_backend import CertificateSecretBackendFactory
from ..auth.operator_scope_ports import OperatorScopePorts
from ..auth.protocols import BrowserSessionFactoryPort, session_store
from ..auth.session_types import AeatSession
from ..auth.sessions import AuthenticatedAeatSessionResult, ensure_authenticated_aeat_session

type SessionWriteReporter = Callable[[OperationEffect], Awaitable[None]]


class LiveSessionWriteReceipt:
    """Track provider session publication alongside a registered capture's other effects."""

    def __init__(self, emit: SessionWriteReporter) -> None:
        self._emit = emit
        self.written = False

    async def __call__(self, effect: OperationEffect) -> None:
        """Record uncertain publication before a write and its verified outcome after."""
        await self._emit(effect)
        if effect is OperationEffect.UPDATED:
            self.written = True

    def combine(self, other: OperationEffect) -> OperationEffect:
        """Retain a completed session write when the capture itself changed nothing."""
        return OperationEffect.UPDATED if self.written and other is OperationEffect.NONE else other


async def ensure_live_authenticated_session(
    settings: Settings,
    *,
    certificate_secret_backend_factory: CertificateSecretBackendFactory,
    browser_session_factory: BrowserSessionFactoryPort,
    operation: str,
    target_url: str | None,
    operator_scope_ports: OperatorScopePorts,
    profile_decode_context: ProfileDecodeContext,
    effect_guard: Callable[[], AbstractAsyncContextManager[None]] | None = None,
    on_session_write: SessionWriteReporter | None = None,
) -> AuthenticatedAeatSessionResult:
    """Publish provider session writes only after a guarded live acquisition."""
    if effect_guard is None:
        return await ensure_authenticated_aeat_session(
            settings,
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            browser_session_factory=browser_session_factory,
            operation=operation,
            target_url=target_url,
            operator_scope_ports=operator_scope_ports,
            profile_decode_context=profile_decode_context,
        )
    with session_store().defer_writes() as staged:
        result = await ensure_authenticated_aeat_session(
            settings,
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            browser_session_factory=browser_session_factory,
            operation=operation,
            target_url=target_url,
            operator_scope_ports=operator_scope_ports,
            profile_decode_context=profile_decode_context,
            effect_guard=effect_guard,
        )
        if staged.has_changes:
            if on_session_write is None:
                raise InternalInvariantError("guarded live session publication needs an effect receipt")
            async with effect_guard():
                await on_session_write(OperationEffect.UNKNOWN)
                staged.publish()
                await on_session_write(OperationEffect.UPDATED)
        return result


async def active_verified_session(
    *,
    certificate_secret_backend_factory: CertificateSecretBackendFactory,
    browser_session_factory: BrowserSessionFactoryPort,
    operation: str = "live-filed-read",
    target_url: str | None = None,
    operator_scope_ports: OperatorScopePorts,
    guarded_read_context: str | None = None,
    authority_operation: PinnedAuthorityOperation | None = None,
    effect_guard: Callable[[], AbstractAsyncContextManager[None]] | None = None,
    on_session_write: SessionWriteReporter | None = None,
) -> tuple[AeatSession, Settings]:
    """Return an authenticated session and :class:`Settings` after the live-read gate.

    The ``operation`` and optional ``target_url`` are forwarded to the
    authentication service for diagnostics and provider routing after
    :class:`AeatAccessGate` has authorized a read-only live operation.
    ``guarded_read_context`` names a guarded caller, such as a test run, whose
    read the gate refuses unless the live-test opt-in is enabled.
    A supplied ``authority_operation`` also governs profile decoding so a
    registered worker does not lease a different published generation.
    """
    settings = load_settings()
    AeatAccessGate(settings).require_live_read(guarded_read_context=guarded_read_context)
    operation_scope = (
        nullcontext(authority_operation) if authority_operation is not None else bundled_indexed_authority().operation()
    )
    with operation_scope as pinned_operation:
        result = await ensure_live_authenticated_session(
            settings,
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            browser_session_factory=browser_session_factory,
            operation=operation,
            target_url=target_url,
            operator_scope_ports=operator_scope_ports,
            profile_decode_context=pinned_operation.profile_decode_context(),
            effect_guard=effect_guard,
            on_session_write=on_session_write,
        )
    session: AeatSession = result.session
    return session, settings


__all__ = ["active_verified_session"]
