"""Persistence integration tests for the live provider-choice projection.

``aeat config auth configure --provider X`` records X on the witnessed
:class:`~cadrumo.application.workflow.WorkflowState`, and that record is the
operator's decision. The live-read bring-up must resolve the same value, or
one surface reports a provider the other never authenticates through.

That divergence shipped: the live resolver read only
:attr:`Settings.cadrumo_auth_provider` and defaulted to the certificate
provider, so an operator who had configured Cl@ve Móvil was refused for a
certificate file they had never chosen to configure. There is no dotenv
source, so the settings field is unset on an ordinary operator machine and
the default was reached every time.

Every test drives the real profile store through the real workflow-state
repository. The public application resolver receives its certificate-secret
capability and operator-scope capability explicitly at this outer seam.
"""

# "Live" names the session provider resolution under test, not a network
# call; every case drives local profile storage and touches no AEAT surface.

from __future__ import annotations

import asyncio
from pathlib import Path

import keyring
import pytest
from pydantic import SecretStr

from cadrumo.adapters.persistence.profile.tests.certificate_secret_fakes import InMemoryCertificateSecretBackendFactory
from cadrumo.adapters.persistence.profile.tests.operator_scope_fakes import (
    build_inward_operator_scope_ports_for_active_route,
)
from cadrumo.adapters.persistence.profile.tests.profile_registration import (
    live_clave_movil_profile_scope,
    register_minimal_profile,
)
from cadrumo.adapters.persistence.storage.operator_scope import build_operator_scope_ports
from cadrumo.adapters.persistence.storage.tests.profile_storage_root_fixture import bucket_session_storage_fixture
from cadrumo.application.auth.actions import update_auth
from cadrumo.application.auth.credentials import resolve_active_provider_kind
from cadrumo.application.auth.operator_scope import active_profile_storage_span
from cadrumo.application.auth.protocols import BrowserSessionPort
from cadrumo.application.auth.sessions import ensure_authenticated_aeat_session
from cadrumo.application.workflow.persistence import workflow_state_repository
from cadrumo.core.auth_provider import AuthProviderKind
from cadrumo.core.config import Settings, load_settings, override_settings
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority

_OPERATOR_SCOPE_PORTS = build_inward_operator_scope_ports_for_active_route()

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

#: This module's OWN bucket. A bucket shared with a sibling module makes
#: the two suites' isolation fixtures interchangeable and puts both on one
#: bucket-scoped master-key session in the same run.
_BUCKET_ID = "c0000003-0000-4000-8000-000000000003"
_PROFILE_LABEL = "live-provider-operator"
_TAX_ID = "12345678Z"
_CERTIFICATE_SECRET_BACKEND_FACTORY = InMemoryCertificateSecretBackendFactory()


_isolated_backend = bucket_session_storage_fixture(_BUCKET_ID)


def _resolve_provider_kind_for_test(
    settings: Settings,
    requested_provider: AuthProviderKind | None = None,
) -> AuthProviderKind:
    """Bind the public provider resolver to this profile integration fixture."""

    resolved = resolve_active_provider_kind(
        certificate_secret_backend_factory=_CERTIFICATE_SECRET_BACKEND_FACTORY,
        settings=settings,
        requested_provider=requested_provider.value if requested_provider is not None else None,
        fallback_provider=(settings.cadrumo_auth_provider or AuthProviderKind.CERTIFICATE).value,
        operator_scope_ports=_OPERATOR_SCOPE_PORTS,
    )
    if resolved is None:
        raise AssertionError("provider resolver returned no provider for a live session")
    return resolved


def _register_profile_selecting(provider: AuthProviderKind | None) -> None:
    """Register the active profile, recording ``provider`` as the operator's choice."""
    register_minimal_profile(profile_id=_BUCKET_ID, display_name=_PROFILE_LABEL, overrides={"identity.tax_id": _TAX_ID})
    if provider is None:
        return
    workflow_state_repository().update(lambda state: update_auth(state, provider=provider.value))


def test_the_persisted_selection_is_resolved_when_settings_name_no_provider() -> None:
    """The configured provider reaches the live path with no settings help.

    This is the operator's real machine: nothing exports a provider, so a
    resolver reading settings alone falls to its certificate default. The
    persisted selection must win instead.
    """
    _register_profile_selecting(AuthProviderKind.CLAVE_MOVIL)

    with override_settings(cadrumo_auth_provider=None) as settings:
        assert settings.cadrumo_auth_provider is None
        assert _resolve_provider_kind_for_test(settings) is AuthProviderKind.CLAVE_MOVIL


def test_the_persisted_selection_beats_a_divergent_settings_default() -> None:
    """Settings is a fallback, never an override.

    The settings value is deliberately the OTHER provider, so a pass here
    cannot be explained by the fallback path: only the persisted selection
    can produce this answer.
    """
    _register_profile_selecting(AuthProviderKind.CLAVE_MOVIL)

    with override_settings(cadrumo_auth_provider=AuthProviderKind.CERTIFICATE) as settings:
        assert _resolve_provider_kind_for_test(settings) is AuthProviderKind.CLAVE_MOVIL


def test_an_explicit_kind_still_wins_over_the_persisted_selection() -> None:
    """A caller naming a provider outranks both other sources.

    Without this, the fix would have replaced a settings-shaped defect with
    a state-shaped one: a caller that explicitly targets one provider - a
    per-provider logout or probe - must not be redirected to another.
    """
    _register_profile_selecting(AuthProviderKind.CLAVE_MOVIL)

    with override_settings(cadrumo_auth_provider=None) as settings:
        resolved = _resolve_provider_kind_for_test(settings, AuthProviderKind.CERTIFICATE)

    assert resolved is AuthProviderKind.CERTIFICATE


def test_the_settings_fallback_applies_only_with_nothing_persisted() -> None:
    """With no operator choice recorded, the deployment default is honoured.

    Pinning this direction too keeps the precedence a three-way ordering
    rather than an assertion that state always wins, which would have made
    the settings field silently dead.
    """
    _register_profile_selecting(None)

    with override_settings(cadrumo_auth_provider=AuthProviderKind.CLAVE_MOVIL) as settings:
        assert _resolve_provider_kind_for_test(settings) is AuthProviderKind.CLAVE_MOVIL


def test_nothing_configured_anywhere_resolves_the_certificate_default() -> None:
    """The documented terminal default survives, so the fix narrows nothing."""
    _register_profile_selecting(None)

    with override_settings(cadrumo_auth_provider=None) as settings:
        assert _resolve_provider_kind_for_test(settings) is AuthProviderKind.CERTIFICATE


class _BrowserLaunchReachedError(Exception):
    """Raised where the live lane would launch the browser that contacts AEAT."""


async def _refuse_browser_launch(settings: Settings) -> BrowserSessionPort:
    del settings
    raise _BrowserLaunchReachedError


def test_the_live_lane_profile_reaches_the_provider_step_on_a_clean_storage_root(tmp_path: Path) -> None:
    """The live-lane fixture yields a logged-in profile on first use and on every later one.

    Without it, a clean environment refused every live test with ``no_session``
    before any AEAT contact. The first entry creates the profile, the second
    logs in to the one it left, and each time the live session entry resolves
    the persisted Cl@ve Movil choice and proceeds to the browser launch -- the
    last step before AEAT. The OS keychain is pinned away for the span and
    restored after it.
    """
    operator_scope_ports = build_operator_scope_ports()
    ambient_keyring = keyring.get_keyring()
    with override_settings(
        cadrumo_clave_movil_dni_nie=SecretStr(_TAX_ID),
        cadrumo_clave_movil_dni_fecha="2030-01-01",
        cadrumo_auth_provider=None,
    ):
        for _entry in range(2):
            with live_clave_movil_profile_scope(tmp_path / "live-tests") as profile:
                assert keyring.get_keyring() is not ambient_keyring
                with active_profile_storage_span(
                    load_settings(), operator_scope_ports=operator_scope_ports
                ) as bucket_id:
                    assert bucket_id == profile.profile_id
                with bundled_indexed_authority().operation() as operation, pytest.raises(_BrowserLaunchReachedError):
                    asyncio.run(
                        ensure_authenticated_aeat_session(
                            load_settings(),
                            certificate_secret_backend_factory=_CERTIFICATE_SECRET_BACKEND_FACTORY,
                            browser_session_factory=_refuse_browser_launch,
                            operation="live-lane-profile-offline-proof",
                            operator_scope_ports=operator_scope_ports,
                            profile_decode_context=operation.profile_decode_context(),
                        )
                    )
            assert keyring.get_keyring() is ambient_keyring
