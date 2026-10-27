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
from ..auth.protocols import (
    BrowserContextPort,
    BrowserSessionFactoryPort,
    ViewLoginSessionFactoryPort,
    session_store,
)
from ..auth.session_types import AeatSession
from ..auth.sessions import (
    AuthenticatedAeatSessionResult,
    ViewSessionBaseline,
    ViewSessionPublication,
    ViewSessionSeed,
    assist_view_login,
    ensure_authenticated_aeat_session,
    publish_view_session_state,
    resume_view_session,
)

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


async def open_live_view_session(
    *,
    certificate_secret_backend_factory: CertificateSecretBackendFactory,
    browser_session_factory: BrowserSessionFactoryPort,
    operator_scope_ports: OperatorScopePorts,
    authority_operation: PinnedAuthorityOperation,
    effect_guard: Callable[[], AbstractAsyncContextManager[None]],
    on_session_write: SessionWriteReporter,
) -> tuple[ViewSessionSeed, Settings]:
    """Resume the profile's AEAT session for a view, or return the seed of a signed-out view.

    The read gate applies first. The configured provider's own probe proves the
    stored session, with any refreshed record published under ``effect_guard``
    exactly as a sync publishes it. A view never logs in here: with no valid
    stored session it opens signed out and the person signs in inside it. Both
    the acquisition lock and the auth mutation span are released before this
    returns, so the view browses without holding either.
    """
    settings = load_settings()
    AeatAccessGate(settings).require_live_read()
    seed = await resume_view_session(
        settings,
        certificate_secret_backend_factory=certificate_secret_backend_factory,
        browser_session_factory=browser_session_factory,
        operator_scope_ports=operator_scope_ports,
        profile_decode_context=authority_operation.profile_decode_context(),
        effect_guard=effect_guard,
        on_session_write=on_session_write,
    )
    return seed, settings


async def publish_live_view_session(
    settings: Settings,
    *,
    baseline: ViewSessionBaseline,
    view_context: BrowserContextPort,
    certificate_secret_backend_factory: CertificateSecretBackendFactory,
    browser_session_factory: BrowserSessionFactoryPort,
    operator_scope_ports: OperatorScopePorts,
    authority_operation: PinnedAuthorityOperation,
    effect_guard: Callable[[], AbstractAsyncContextManager[None]],
    on_session_write: SessionWriteReporter,
    operation: str = "live-sede-view-close",
) -> ViewSessionPublication:
    """Publish a view's storage state through the canonical custody path.

    A view calls this when the person may have signed in inside it, and when
    it closes, with the view context still open. The read gate is checked
    again, then :func:`~cadrumo.application.auth.sessions.publish_view_session_state`
    captures, verifies and publishes under its digest precondition.
    """
    AeatAccessGate(settings).require_live_read()
    return await publish_view_session_state(
        settings,
        baseline=baseline,
        view_context=view_context,
        certificate_secret_backend_factory=certificate_secret_backend_factory,
        browser_session_factory=browser_session_factory,
        operator_scope_ports=operator_scope_ports,
        profile_decode_context=authority_operation.profile_decode_context(),
        effect_guard=effect_guard,
        on_session_write=on_session_write,
        operation=operation,
    )


async def assist_live_view_login(
    settings: Settings,
    *,
    baseline: ViewSessionBaseline,
    login_session_factory: ViewLoginSessionFactoryPort,
    certificate_secret_backend_factory: CertificateSecretBackendFactory,
    operator_scope_ports: OperatorScopePorts,
    authority_operation: PinnedAuthorityOperation,
    effect_guard: Callable[[], AbstractAsyncContextManager[None]],
    on_session_write: SessionWriteReporter,
    on_login_verified: Callable[[], None],
) -> ViewSessionPublication:
    """Run the configured provider's login inside a signed-out view and publish it at once.

    The read gate is checked again, then
    :func:`~cadrumo.application.auth.sessions.assist_view_login` runs the
    canonical fresh acquisition against the view's own context and publishes
    under the digest precondition. The caller may cancel it until
    ``on_login_verified`` is called.
    """
    AeatAccessGate(settings).require_live_read()
    return await assist_view_login(
        settings,
        baseline=baseline,
        login_session_factory=login_session_factory,
        certificate_secret_backend_factory=certificate_secret_backend_factory,
        operator_scope_ports=operator_scope_ports,
        profile_decode_context=authority_operation.profile_decode_context(),
        effect_guard=effect_guard,
        on_session_write=on_session_write,
        on_login_verified=on_login_verified,
    )


__all__ = [
    "active_verified_session",
    "assist_live_view_login",
    "open_live_view_session",
    "publish_live_view_session",
]
