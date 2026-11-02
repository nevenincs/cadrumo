"""The real adapter readers behind each capture flow.

Importing this module is harmless, but calling a driver contacts AEAT, so only the
explicitly flagged run path reaches here. Every result is dropped: the capture's
evidence is the request stream, and nothing a reader returns is written anywhere.
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable, Generator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Final

from cadrumo.adapters.outbound.aeat.auth.clave_movil_support import auth_browser_action_policy
from cadrumo.adapters.outbound.aeat.auth.provider_selection import select_provider
from cadrumo.adapters.outbound.aeat.auth.session_store import build_session_store
from cadrumo.adapters.outbound.aeat.browser.factory import default_browser_session_factory
from cadrumo.adapters.outbound.aeat.sede.censal_datos import READ_GUARD_POLICY as CENSAL_READ_POLICY
from cadrumo.adapters.outbound.aeat.sede.censal_datos import fetch_censal_datos
from cadrumo.adapters.outbound.aeat.sede.declarations import (
    assert_declarations_read_landing,
    open_declarations_register,
    walk_declarations_register,
)
from cadrumo.adapters.outbound.aeat.sede.groi_check import READ_GUARD_POLICY as GROI_READ_POLICY
from cadrumo.adapters.outbound.aeat.sede.groi_check import collect_groi_observations
from cadrumo.adapters.outbound.aeat.sede.iva_compensation_wallet import (
    PRE303_PRESENTATION_SERVICE_URL,
    fetch_iva_compensation_wallet,
)
from cadrumo.adapters.outbound.aeat.sede.iva_compensation_wallet_parsing import IVA_COMPENSATION_WALLET_READ_POLICY
from cadrumo.adapters.outbound.aeat.sede.notifications import READ_GUARD_POLICY as NOTIFICATIONS_READ_POLICY
from cadrumo.adapters.outbound.aeat.sede.notifications import fetch_notifications_query
from cadrumo.adapters.outbound.aeat.sede.schema import FiledDeclaracionArtefact
from cadrumo.adapters.outbound.aeat.sede.signed_in_identity import READ_GUARD_POLICY as IDENTITY_READ_POLICY
from cadrumo.adapters.persistence.profile.buckets import build_bucket_event_history_repository
from cadrumo.adapters.persistence.profile.tests.profile_registration import (
    LiveAeatProfile,
    live_clave_movil_profile_scope,
)
from cadrumo.adapters.persistence.storage.certificate_secret_backend import build_certificate_secret_backend
from cadrumo.adapters.persistence.storage.operator_scope import build_operator_scope_ports
from cadrumo.adapters.persistence.storage.profile_persistence_composition import composed_profile_persistence_ports
from cadrumo.application.auth.protocols import bind_session_store
from cadrumo.application.auth.providers import bind_auth_provider_selector
from cadrumo.application.auth.session_types import AeatSession
from cadrumo.application.auth.sessions import ensure_authenticated_aeat_session
from cadrumo.application.browser_location import playwright_browsers_root
from cadrumo.application.bucket_event_repository import bind_bucket_event_history_repository_factory
from cadrumo.core.auth_provider import AuthProviderKind
from cadrumo.core.config import Settings, load_settings
from cadrumo.core.operator_progress import OperatorProgress, operator_progress_sink
from cadrumo.core.period import Period
from cadrumo.core.redaction.tax_identity_admission import bind_tax_identity_admission
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.remote_state_guard import RemoteStateGuardPolicy
from cadrumo.domain.calculations.registry.tax_identity_admission import RegistryTaxIdentityAdmission
from cadrumo.tests.collection_storage_root import link_installed_component

from .flows import LOGIN, ReadFlow
from .listener import RequestListener, notification_detail_path
from .recorder import CaptureRecorder, write_report
from .runner import run_flows

# The public corporate NIF the live GROI lane already probes; no taxpayer's own.
_GROI_PROBE_NIF: Final = "A28015865"
_BROWSER_MEMBER: Final = "components/playwright"


@dataclass
class LiveCaptureState:
    """What the live flows share: settings, the query to run, and the login's session."""

    settings: Settings
    modelo: str
    ejercicio: int
    session: AeatSession | None = field(default=None)

    def require_session(self) -> AeatSession:
        """Return the session the login flow acquired."""
        if self.session is None:
            raise RuntimeError("This flow needs the session the login flow acquires")
        return self.session


def declarations_read_policy() -> RemoteStateGuardPolicy:
    """Return the register's policy, which its package publishes only as this default argument."""
    policy = inspect.signature(assert_declarations_read_landing).parameters["policy"].default
    if not isinstance(policy, RemoteStateGuardPolicy):
        raise TypeError("The declarations landing check no longer defaults to its read policy")
    return policy


def guard_policies(settings: Settings) -> tuple[RemoteStateGuardPolicy, ...]:
    """Return every policy a captured request is evaluated against."""
    return (
        auth_browser_action_policy(settings),
        IDENTITY_READ_POLICY,
        CENSAL_READ_POLICY,
        declarations_read_policy(),
        IVA_COMPENSATION_WALLET_READ_POLICY,
        NOTIFICATIONS_READ_POLICY,
        GROI_READ_POLICY,
    )


def notification_detail_route(settings: Settings) -> str:
    """Return the configured route that serves a notification when opened."""
    return settings.external_constants().aeat.sede_paths.notifications_detail


async def _acquire(state: LiveCaptureState, *, fresh: bool, operation: str, target_url: str | None) -> AeatSession:
    with bundled_indexed_authority().operation() as authority_operation:
        result = await ensure_authenticated_aeat_session(
            state.settings,
            certificate_secret_backend_factory=build_certificate_secret_backend,
            browser_session_factory=default_browser_session_factory,
            kind=AuthProviderKind.CLAVE_MOVIL,
            fresh=fresh,
            operation=operation,
            target_url=target_url,
            operator_scope_ports=build_operator_scope_ports(),
            profile_decode_context=authority_operation.profile_decode_context(),
        )
    return result.session


async def _login(state: LiveCaptureState) -> None:
    # Fresh, because a reused session would skip the choreography this capture exists to observe.
    state.session = await _acquire(state, fresh=True, operation="aeat-request-capture-login", target_url=None)


async def _censo(state: LiveCaptureState) -> None:
    session = state.require_session()
    await fetch_censal_datos(session, taxpayer_nif=session.identity_nif, settings=state.settings)


def _discard_body(
    _observation_key: object, artefact: FiledDeclaracionArtefact, _body: bytes
) -> FiledDeclaracionArtefact:
    return artefact


async def _filed_declarations(state: LiveCaptureState) -> None:
    session = state.require_session()
    declarations = await walk_declarations_register(session, modelo=state.modelo, ejercicio=state.ejercicio)
    if not declarations:
        return
    with bundled_indexed_authority().operation() as authority_operation:
        async with open_declarations_register(session, operation=authority_operation) as register:
            await register.capture_observation(declarations[0], artefact_sink=_discard_body)


async def _iva_wallet(state: LiveCaptureState) -> None:
    today = date.today()
    period = Period.from_year_and_code(today.year, f"{(today.month - 1) // 3 + 1}T")
    # The session is re-acquired against the wallet's target, as the registered capture does.
    session = await _acquire(
        state,
        fresh=False,
        operation="aeat-request-capture-wallet",
        target_url=PRE303_PRESENTATION_SERVICE_URL,
    )
    await fetch_iva_compensation_wallet(session, target_year=today.year, target_period=period, settings=state.settings)


async def _notifications(state: LiveCaptureState) -> None:
    await fetch_notifications_query(state.require_session(), settings=state.settings)


async def _groi(state: LiveCaptureState) -> None:
    await collect_groi_observations(b"", expected={_GROI_PROBE_NIF: "valid"}, settings=state.settings)


LIVE_DRIVERS: Final[Mapping[str, Callable[[LiveCaptureState], Awaitable[None]]]] = {
    LOGIN: _login,
    "censo": _censo,
    "filed-declarations": _filed_declarations,
    "iva-wallet": _iva_wallet,
    "notifications": _notifications,
    "groi": _groi,
}


def forbidden_values(settings: Settings) -> tuple[str, ...]:
    """Return the configured private values that must not appear in the report."""
    secrets = (settings.cadrumo_clave_movil_dni_nie, settings.cadrumo_clave_movil_nie_soporte)
    return (
        *(secret.get_secret_value() for secret in secrets if secret is not None),
        settings.cadrumo_clave_movil_dni_fecha or "",
    )


@contextmanager
def _linked_browser_build(storage_root: Path, installed: Path) -> Generator[None]:
    """Expose the installed browser build inside the dedicated profile's storage root.

    The product looks for its browser only beneath the storage root, and that root
    moves when the dedicated profile's scope opens. The link is removed, never
    followed, so clearing the profile's folder cannot reach the installed tree.
    """
    link = storage_root / _BROWSER_MEMBER
    if link.is_dir() and not link.is_junction() and not link.is_symlink() and not any(link.iterdir()):
        link.rmdir()
    link_installed_component(storage_root, _BROWSER_MEMBER, installed)
    try:
        yield
    finally:
        if link.is_symlink():
            link.unlink()
        elif link.is_junction():
            link.rmdir()


@contextmanager
def _composed_ports() -> Generator[None]:
    """Bind the adapters a login needs; the worker's composition does this for the product."""
    with (
        bind_tax_identity_admission(RegistryTaxIdentityAdmission()),
        composed_profile_persistence_ports(),
        bind_bucket_event_history_repository_factory(build_bucket_event_history_repository),
        bind_auth_provider_selector(select_provider),
        bind_session_store(build_session_store()),
    ):
        yield


@contextmanager
def _operator_scope(profile_base: Path, *, show: Callable[[str], None]) -> Generator[LiveAeatProfile]:
    """Log in the dedicated live profile and show the Cl@ve comparison code to the operator."""

    async def show_progress(progress: OperatorProgress) -> None:
        show(progress.render())

    with live_clave_movil_profile_scope(profile_base) as profile, operator_progress_sink(show_progress):
        yield profile


def run_live_capture(
    flows: Sequence[ReadFlow],
    drivers: Mapping[str, Callable[[LiveCaptureState], Awaitable[None]]],
    *,
    settings: Settings,
    modelo: str,
    ejercicio: int,
    profile_base: Path,
    output: Path,
    show: Callable[[str], None],
) -> CaptureRecorder:
    """Run ``flows`` in the dedicated profile, writing the report however the run ends."""
    detail_path = notification_detail_path(notification_detail_route(settings))
    recorder = CaptureRecorder(guard_policies(settings), notification_detail_paths=(detail_path,))
    listener = RequestListener(recorder, notification_detail_paths=(detail_path,))
    try:
        with (
            _composed_ports(),
            _operator_scope(profile_base, show=show) as profile,
            _linked_browser_build(profile.storage_root, playwright_browsers_root(settings=settings)),
        ):
            # The scope moved the storage root, so settings read before it point at the wrong one.
            state = LiveCaptureState(settings=load_settings(), modelo=modelo, ejercicio=ejercicio)
            asyncio.run(run_flows(flows, drivers, state, recorder=recorder, listener=listener))
    finally:
        write_report(recorder.report(), output, forbidden_values=forbidden_values(settings))
    return recorder
