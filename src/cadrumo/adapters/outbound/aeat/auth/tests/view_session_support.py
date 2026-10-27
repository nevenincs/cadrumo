"""A registered profile, its encrypted session custody and a stood-in operation host for Sede view tests.

The profile, custody and providers are the real ones. Only the operation
host's effect guard and effect reporter are stood in, because the supervisor
that supplies them is not the behaviour under test.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import Final

from pydantic import SecretStr

from cadrumo.adapters.persistence.profile.tests.profile_registration import register_minimal_profile
from cadrumo.adapters.persistence.storage.operator_scope import build_operator_scope_ports
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import open_test_profile_session
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.auth.acquisition_lock import AuthAcquisitionLockState, inspect_auth_acquisition_lock
from cadrumo.application.auth.operator import configure_operator_auth
from cadrumo.application.auth.sessions import storage_state_paths
from cadrumo.application.auth.tests.certificate_secret_fakes import InMemoryCertificateSecretBackendFactory
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
    tmp_path: Path, operation: PinnedAuthorityOperation, *, tax_id: str = CERTIFICATE_NIF
) -> Generator[None]:
    """A registered, unlocked profile whose configured provider is a certificate for ``tax_id``'s holder."""
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        override_settings(
            cadrumo_active_profile=None,
            cadrumo_certificate_path=_build_bundle(tmp_path),
            cadrumo_certificate_password_secret=SecretStr(CERTIFICATE_INPUT),
            cadrumo_browser_close_timeout_ms=15_000,
        ),
        open_test_profile_session(PROFILE_ID),
    ):
        register_minimal_profile(profile_id=PROFILE_ID, overrides={"identity.tax_id": tax_id})
        configure_operator_auth("certificate", operator_scope_ports=OPERATOR_SCOPE_PORTS, operation=operation)
        yield


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
