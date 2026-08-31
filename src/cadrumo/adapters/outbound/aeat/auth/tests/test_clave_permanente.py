"""Production-direct policy and configuration tests for Cl@ve Permanente."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

import pytest
from pydantic import AnyUrl

from ......application.auth.session_types import AeatSession, ClavePermanenteSessionDetail
from ......core.auth_provider import AuthProviderKind
from ......core.errors.hierarchy import AeatLoginAssertionError
from ......domain.calculations.registry.errors import RegistryValidationError
from ......domain.calculations.registry.remote_state_guard import RemoteOperation, assert_remote_operation_allowed
from ......tests.secure_sql import isolated_runtime_profile
from ..clave_permanente import ClavePermanenteAuthProvider
from ..clave_permanente_support import clave_permanente_auth_browser_action_policy
from ..errors import AuthConfigurationError
from ._clave_permanente_support import (
    _DOMAINS,
    _aeat_url,
    _run,
    _settings_for,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


@pytest.fixture(autouse=True)
def _isolated_secure_session_backend(tmp_path: Path):
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="9948ab37-fed4-473e-aa6f-1f6f28992186"):
        yield


# ── enum + catalogue enrollment ──────────────────────────────────────────────


class TestBrowserActionPolicy:
    """Build + host coverage for the Cl@ve Permanente remote-state guard policy.

    Regression for the latent build crash: the policy listed the Cl@ve national
    IdP host, which the guard's AEAT-host predicate refused, so every build
    raised. It now builds under the explicit government-IdP opt-in.
    """

    def test_policy_builds_and_allows_permanente_credential_fill_actions(self, tmp_path: Path) -> None:
        # The build itself is the regression: the policy previously raised on
        # construction because it listed the Cl@ve IdP host. The two credential-
        # fill actions are on the allow-list and carry no write-verb token.
        settings = _settings_for(tmp_path)
        policy = clave_permanente_auth_browser_action_policy(settings)
        for action in (
            "clave-permanente-fill-username",
            "clave-permanente-fill-password",
        ):
            result = assert_remote_operation_allowed(
                policy,
                RemoteOperation(kind="browser_action", action=action),
            )
            assert result.decision == "allowed"

    def test_policy_allows_the_renamed_authenticate_action(self, tmp_path: Path) -> None:
        # The Cl@ve IdP login-form submit is labelled ``authenticate`` (not
        # ``submit``): it is an authentication step, not an AEAT tax filing, so
        # the write-token block does not apply. ``authenticate`` carries no
        # forbidden verb token, so it reaches — and matches — the allow-list.
        settings = _settings_for(tmp_path)
        policy = clave_permanente_auth_browser_action_policy(settings)
        result = assert_remote_operation_allowed(
            policy,
            RemoteOperation(kind="browser_action", action="clave-permanente-authenticate"),
        )
        assert result.decision == "allowed"

    def test_write_token_filter_still_blocks_a_write_verb_action(self, tmp_path: Path) -> None:
        # Safety net: the rename is ONLY the login label. A genuine write-verb
        # browser action under the SAME permanente policy is STILL refused by the
        # unchanged write-token filter — proof the block was not weakened.
        settings = _settings_for(tmp_path)
        policy = clave_permanente_auth_browser_action_policy(settings)
        with pytest.raises(RegistryValidationError, match="token 'presentar' is forbidden"):
            assert_remote_operation_allowed(
                policy,
                RemoteOperation(kind="browser_action", action="clave-permanente-presentar"),
            )

    def test_policy_admits_sibling_aeat_host_and_clave_idp_host(self, tmp_path: Path) -> None:
        settings = _settings_for(tmp_path)
        policy = clave_permanente_auth_browser_action_policy(settings)
        clave_host = urlsplit(settings.external_constants().aeat.domains.clave).netloc
        aeat_sibling = _aeat_url(_DOMAINS.www12, settings.aeat_sede_expedientes_path)
        idp_url = f"https://se-pasarela.{clave_host}/idp/gateway"
        for url in (aeat_sibling, idp_url):
            result = assert_remote_operation_allowed(
                policy,
                RemoteOperation(kind="http", method="GET", url=AnyUrl(url)),
            )
            assert result.decision == "allowed"

    def test_policy_refuses_non_aeat_non_idp_host(self, tmp_path: Path) -> None:
        settings = _settings_for(tmp_path)
        policy = clave_permanente_auth_browser_action_policy(settings)
        with pytest.raises(RegistryValidationError, match="not in allowed read-only hosts"):
            assert_remote_operation_allowed(
                policy,
                RemoteOperation(kind="http", method="GET", url=AnyUrl("https://attacker.example/read/path")),
            )

    def test_policy_rejects_unlisted_action(self, tmp_path: Path) -> None:
        settings = _settings_for(tmp_path)
        policy = clave_permanente_auth_browser_action_policy(settings)
        with pytest.raises(RegistryValidationError, match="explicit read-only allow-list"):
            assert_remote_operation_allowed(
                policy,
                RemoteOperation(kind="browser_action", action="clave-permanente-unreviewed"),
            )


def test_auth_provider_kind_has_clave_permanente_member() -> None:
    assert AuthProviderKind.CLAVE_PERMANENTE == "clave_permanente"


def test_select_provider_dispatches_clave_permanente(tmp_path: Path) -> None:
    from ..provider_selection import select_provider

    settings = _settings_for(
        tmp_path,
        CADRUMO_CLAVE_PERMANENTE_DNI_NIE="12345678Z",
        CADRUMO_CLAVE_PERMANENTE_PASSWORD="hunter2",
    )
    provider = select_provider(AuthProviderKind.CLAVE_PERMANENTE, settings=settings)
    assert isinstance(provider, ClavePermanenteAuthProvider)
    assert provider.kind == AuthProviderKind.CLAVE_PERMANENTE


# ── identity + password preconditions ───────────────────────────────────────


class TestPreconditions:
    def test_missing_identity_raises_configuration_error(self, tmp_path: Path) -> None:
        settings = _settings_for(tmp_path, CADRUMO_CLAVE_PERMANENTE_PASSWORD="hunter2")
        provider = ClavePermanenteAuthProvider(settings)

        async def run() -> None:
            with pytest.raises(AuthConfigurationError, match="CADRUMO_CLAVE_PERMANENTE_DNI_NIE"):
                await provider.authenticate()

        _run(run())

    def test_missing_password_raises_configuration_error(self, tmp_path: Path) -> None:
        settings = _settings_for(tmp_path, CADRUMO_CLAVE_PERMANENTE_DNI_NIE="12345678Z")
        provider = ClavePermanenteAuthProvider(settings)

        async def run() -> None:
            with pytest.raises(AuthConfigurationError, match="CADRUMO_CLAVE_PERMANENTE_PASSWORD"):
                await provider.authenticate()

        _run(run())

    def test_malformed_identity_raises_configuration_error(self, tmp_path: Path) -> None:
        settings = _settings_for(
            tmp_path,
            CADRUMO_CLAVE_PERMANENTE_DNI_NIE="NOT-A-VALID-ID",
            CADRUMO_CLAVE_PERMANENTE_PASSWORD="hunter2",
        )
        provider = ClavePermanenteAuthProvider(settings)

        async def run() -> None:
            with pytest.raises(AuthConfigurationError, match=r"NIF|NIE|identity"):
                await provider.authenticate()

        _run(run())


# ── describe() ───────────────────────────────────────────────────────────────


class TestDescribe:
    def test_describe_unconfigured(self, tmp_path: Path) -> None:
        settings = _settings_for(tmp_path)
        provider = ClavePermanenteAuthProvider(settings)
        description = provider.describe()
        assert description.configured is False
        assert description.available is False
        assert description.health_severity == "info"
        # Round-5 B2-style parity: never leak the raw env-var name.
        assert "AEAT_CLAVE_PERMANENTE" not in (description.health_summary or "")

    def test_describe_missing_password_only(self, tmp_path: Path) -> None:
        settings = _settings_for(tmp_path, CADRUMO_CLAVE_PERMANENTE_DNI_NIE="12345678Z")
        provider = ClavePermanenteAuthProvider(settings)
        description = provider.describe()
        assert description.configured is False
        assert description.available is False

    def test_describe_configured(self, tmp_path: Path) -> None:
        settings = _settings_for(
            tmp_path,
            CADRUMO_CLAVE_PERMANENTE_DNI_NIE="12345678Z",
            CADRUMO_CLAVE_PERMANENTE_PASSWORD="hunter2",
        )
        provider = ClavePermanenteAuthProvider(settings)
        description = provider.describe()
        assert description.configured is True
        assert description.available is True
        assert description.identity_nif == "12345678Z"
        assert description.kind == AuthProviderKind.CLAVE_PERMANENTE

    def test_describe_invalid_identity(self, tmp_path: Path) -> None:
        settings = _settings_for(
            tmp_path,
            CADRUMO_CLAVE_PERMANENTE_DNI_NIE="BAD",
            CADRUMO_CLAVE_PERMANENTE_PASSWORD="hunter2",
        )
        provider = ClavePermanenteAuthProvider(settings)
        description = provider.describe()
        assert description.configured is True
        assert description.available is False
        assert description.health_severity == "warning"


# ── verify() ─────────────────────────────────────────────────────────────────


class TestVerify:
    def test_verify_without_active_context_raises(self, tmp_path: Path) -> None:
        settings = _settings_for(
            tmp_path,
            CADRUMO_CLAVE_PERMANENTE_DNI_NIE="12345678Z",
            CADRUMO_CLAVE_PERMANENTE_PASSWORD="hunter2",
        )
        provider = ClavePermanenteAuthProvider(settings)

        async def run() -> None:
            from ......core.time.clock import now

            attempted_at = now()
            session_without_context = AeatSession(
                authenticated_at=attempted_at,
                idle_deadline=attempted_at,
                storage_state_path=None,
                identity_nif="12345678Z",
                provider_detail=ClavePermanenteSessionDetail(dni_nie="12345678Z"),
            )
            with pytest.raises(AeatLoginAssertionError, match="requires an active browser context"):
                await provider.verify(session_without_context)

        _run(run())
