"""A registered profile, its encrypted session custody and a stood-in operation host for Sede view tests.

The profile, custody and providers are the real ones. Only the operation
host's effect guard and effect reporter are stood in, because the supervisor
that supplies them is not the behaviour under test.
"""

from __future__ import annotations

import shutil
from collections.abc import AsyncGenerator, Callable, Generator
from contextlib import AbstractContextManager, asynccontextmanager, contextmanager
from pathlib import Path
from typing import Final
from uuid import UUID

from pydantic import SecretStr

from cadrumo.adapters.outbound.aeat.browser.tests.real_http_boundary import (
    LocalHttpBoundary,
    opened_http_boundary,
    real_browser_factory,
)
from cadrumo.adapters.outbound.aeat.browser.tests.view_page_support import until
from cadrumo.adapters.persistence.operations.tests.supervision_support import run_to_settlement
from cadrumo.adapters.persistence.profile.tests.profile_registration import register_minimal_profile
from cadrumo.adapters.persistence.storage.operator_scope import build_operator_scope_ports
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import open_test_profile_session
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.auth.acquisition_lock import AuthAcquisitionLockState, inspect_auth_acquisition_lock
from cadrumo.application.auth.operator import configure_operator_auth
from cadrumo.application.auth.operator_scope_ports import OperatorScopePorts
from cadrumo.application.auth.protocols import BrowserSessionFactoryPort
from cadrumo.application.auth.sessions import storage_state_paths
from cadrumo.application.auth.tests.certificate_secret_fakes import InMemoryCertificateSecretBackendFactory
from cadrumo.application.operations.models import OperationId
from cadrumo.application.operations.persistence.journal import OperationPersistedSnapshot
from cadrumo.application.operations.supervisor import OperationSupervisor
from cadrumo.core.auth_provider import AuthProviderKind
from cadrumo.core.config import load_settings, override_settings
from cadrumo.core.operations import OperationEffect
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation

from .. import session_store
from ._auth_fixtures import CERTIFICATE_INPUT
from ._authenticator_support import _build_bundle

PROFILE_ID: Final[str] = "1f6b0000-0000-4000-8000-00000000c1c1"
CERTIFICATE_NIF: Final[str] = "12345678Z"
SESSION_COOKIE: Final[str] = "AEAT_SESSION"
OPERATOR_SCOPE_PORTS: Final = build_operator_scope_ports()
CERTIFICATE_SECRET_BACKEND_FACTORY: Final = InMemoryCertificateSecretBackendFactory()


class OperationHost:
    """Record the effect reports and guard entries the supervisor would journal."""

    def __init__(
        self,
        *,
        kind: AuthProviderKind = AuthProviderKind.CERTIFICATE,
        interrupt_before_updated: BaseException | None = None,
    ) -> None:
        self.effects: list[OperationEffect] = []
        self.guard_entries = 0
        self.lock_state_at_unknown: AuthAcquisitionLockState | None = None
        self._kind = kind
        self._interrupt_before_updated = interrupt_before_updated

    @asynccontextmanager
    async def effect_guard(self) -> AsyncGenerator[None]:
        self.guard_entries += 1
        yield

    async def report(self, effect: OperationEffect) -> None:
        if effect is OperationEffect.UPDATED and self._interrupt_before_updated is not None:
            # The write has run; the host is interrupted before journaling its outcome.
            raise self._interrupt_before_updated
        self.effects.append(effect)
        if effect is OperationEffect.UNKNOWN:
            self.lock_state_at_unknown = lock_state(self._kind)


@contextmanager
def certificate_profile(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    *,
    tax_id: str = CERTIFICATE_NIF,
    template: Path | None = None,
) -> Generator[None]:
    """A registered, unlocked profile whose configured provider is a certificate for ``tax_id``'s holder.

    With ``template`` -- the storage root :func:`certificate_profile_template`
    left behind -- the profile is a copy of that already-registered root rather
    than a fresh registration, so the password wrap is paid once per template.
    """
    with (
        isolated_profile_storage_root(tmp_path=tmp_path) as storage_root,
        override_settings(
            cadrumo_active_profile=None,
            cadrumo_certificate_path=_build_bundle(tmp_path),
            cadrumo_certificate_password_secret=SecretStr(CERTIFICATE_INPUT),
            cadrumo_browser_close_timeout_ms=15_000,
        ),
        open_test_profile_session(PROFILE_ID),
    ):
        if template is None:
            register_minimal_profile(profile_id=PROFILE_ID, overrides={"identity.tax_id": tax_id})
            configure_operator_auth("certificate", operator_scope_ports=OPERATOR_SCOPE_PORTS, operation=operation)
        else:
            shutil.copytree(template, storage_root, dirs_exist_ok=True)
        yield


def certificate_profile_template(
    base: Path, operation: PinnedAuthorityOperation, *, tax_id: str = CERTIFICATE_NIF
) -> Path:
    """Register a certificate profile once and return its closed, copyable storage root."""
    with certificate_profile(base, operation, tax_id=tax_id):
        pass
    return base / "cadrumo-storage"


@contextmanager
def clave_permanente_profile(tmp_path: Path, operation: PinnedAuthorityOperation) -> Generator[None]:
    """A registered, unlocked profile whose configured provider is Cl@ve Permanente for its own NIF."""
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        override_settings(
            cadrumo_active_profile=None,
            cadrumo_clave_permanente_password=SecretStr(CERTIFICATE_INPUT),
            cadrumo_browser_close_timeout_ms=15_000,
        ),
        open_test_profile_session(PROFILE_ID),
    ):
        register_minimal_profile(
            profile_id=PROFILE_ID,
            overrides={"identity.tax_id": CERTIFICATE_NIF, "auth.dni_nie": CERTIFICATE_NIF},
        )
        configure_operator_auth("clave_permanente", operator_scope_ports=OPERATOR_SCOPE_PORTS, operation=operation)
        yield


def session_path(kind: AuthProviderKind = AuthProviderKind.CERTIFICATE) -> Path:
    return storage_state_paths(kind).storage_state


def stored_digest(kind: AuthProviderKind = AuthProviderKind.CERTIFICATE) -> str | None:
    return session_store.durable_storage_state_sha256(session_path(kind))


def stored_cookie_names(kind: AuthProviderKind = AuthProviderKind.CERTIFICATE) -> set[str]:
    persisted = session_store.load(session_path(kind))
    assert persisted is not None
    cookies = persisted.storage_state.get("cookies")
    assert isinstance(cookies, list)
    return {str(cookie.get("name")) for cookie in cookies if isinstance(cookie, dict)}


def lock_state(kind: AuthProviderKind = AuthProviderKind.CERTIFICATE) -> AuthAcquisitionLockState:
    return inspect_auth_acquisition_lock(load_settings(), kind).state


class LocalSedeOrigin:
    """The local HTTP boundary, offered to a view test as the means to open browsers that reach it."""

    def __init__(self, boundary: LocalHttpBoundary) -> None:
        self._boundary = boundary

    def browser_session_factory(self, *, profile_name: str) -> BrowserSessionFactoryPort:
        return real_browser_factory(boundary=self._boundary, profile_name=profile_name)


class CertificateViewSessionWorld:
    """The certificate-provider profile and stored session, offered to hosts that drive a Sede view."""

    @property
    def profile_id(self) -> UUID:
        return UUID(PROFILE_ID)

    @property
    def certificate_secret_backend_factory(self) -> InMemoryCertificateSecretBackendFactory:
        return CERTIFICATE_SECRET_BACKEND_FACTORY

    @property
    def operator_scope_ports(self) -> OperatorScopePorts:
        return OPERATOR_SCOPE_PORTS

    def registered_profile(self, tmp_path: Path, operation: PinnedAuthorityOperation) -> AbstractContextManager[None]:
        return certificate_profile(tmp_path, operation)

    def operation_host(self) -> OperationHost:
        return OperationHost()

    def stored_digest(self) -> str | None:
        return stored_digest()

    def stored_cookie_names(self) -> set[str]:
        return stored_cookie_names()

    @asynccontextmanager
    async def opened_http_boundary(self) -> AsyncGenerator[LocalSedeOrigin]:
        async with opened_http_boundary() as boundary:
            yield LocalSedeOrigin(boundary)

    async def until(self, condition: Callable[[], bool], *, timeout: float) -> None:
        await until(condition, timeout=timeout)

    async def run_to_settlement(
        self, supervisor: OperationSupervisor, operation_id: OperationId
    ) -> OperationPersistedSnapshot:
        return await run_to_settlement(supervisor, operation_id)
