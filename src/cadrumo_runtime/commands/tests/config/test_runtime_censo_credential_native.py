"""Censo setup saves login passwords through the native registered runtime."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.storage.certificate_secret_backend import build_certificate_secret_backend
from cadrumo.adapters.persistence.storage.operator_scope import build_operator_scope_ports
from cadrumo.application.auth.credentials import active_auth_projection_span
from cadrumo.core.auth_provider import AuthProviderKind
from cadrumo.core.config import load_settings
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.entrypoints.cli.config import _censo_auth
from cadrumo_runtime.commands import runtime_auth_configure
from cadrumo_runtime.commands.tests.config.test_runtime_auth_configure_native import _invoke
from cadrumo_runtime.commands.tests.runtime_profile_cli_fixture import native_cli_profile_scope
from cadrumo_runtime.host.tests.frontend.cli.native_profile_cli_support import reauthenticate_native_profile

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]


@pytest.mark.parametrize("provider", [AuthProviderKind.CERTIFICATE, AuthProviderKind.CLAVE_PERMANENTE])
def test_native_censo_password_setup_persists_for_next_invocation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
    provider: AuthProviderKind,
) -> None:
    """Use the real censo password helper, protected transport, worker and encrypted store."""
    original = runtime_auth_configure.run_registered_operation
    saved = []

    def configure_then_save(client, *args, **kwargs):
        result = original(client, *args, **kwargs)
        if not saved:
            _censo_auth._save_password(client, provider)
            saved.append(True)
        readiness = _censo_auth.read_censo_auth(client)
        password_field = "auth.password" if provider is AuthProviderKind.CLAVE_PERMANENTE else "certificate.passphrase"
        assert any(item.field == password_field and item.satisfied for item in readiness.requirements)
        return result

    monkeypatch.setattr(runtime_auth_configure, "run_registered_operation", configure_then_save)
    monkeypatch.setattr(_censo_auth, "prompt_secret_no_echo", lambda _: "synthetic-native-password")
    with native_cli_profile_scope(tmp_path) as profile:
        observations = []
        profile.failure_observer = observations.append
        profile.register(
            label="native-censo-password",
            facts={
                "identity.name": "Synthetic",
                "identity.surnames": "Censo Password",
                "identity.tax_id": "12345678Z",
                "auth.dni_nie": "12345678Z",
                "activities.description": "synthetic test profile",
            },
        )
        configured = _invoke(profile, "config", "auth", "configure", "--provider", provider.value)
        assert configured.exit_code == 0, (configured.output, saved, observations)
        assert "synthetic-native-password" not in configured.output
        assert saved == [True]
        reopened = _invoke(profile, "config", "auth", "configure", "--provider", provider.value)
        assert reopened.exit_code == 0, (reopened.output, observations)
        reauthenticate_native_profile(profile, authority_operation=authority_operation)
        with active_auth_projection_span(
            requested_provider=provider.value,
            certificate_secret_backend_factory=build_certificate_secret_backend,
            operator_scope_ports=build_operator_scope_ports(),
            # The fixture overrides its in-process secret store to a sibling
            # directory; native workers use the canonical root-relative store.
            settings=load_settings().model_copy(update={"cadrumo_secret_store_dir": profile.storage_root / "secrets"}),
        ) as snapshot:
            if provider is AuthProviderKind.CERTIFICATE:
                assert snapshot.certificate_credentials is not None
                secret = snapshot.certificate_credentials.password
            else:
                secret = snapshot.clave_permanente_password
            assert secret is not None
            assert secret.get_secret_value() == "synthetic-native-password"
