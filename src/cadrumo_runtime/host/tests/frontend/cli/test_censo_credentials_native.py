"""Runtime-owned integration of AEAT's censal CLI, credentials and native custody."""

from __future__ import annotations

import json
import sys
from functools import cache
from pathlib import Path

import pytest
from typer.testing import CliRunner

from cadrumo.adapters.persistence.storage.certificate_secret_backend import build_certificate_secret_backend
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.adapters.persistence.storage.operator_scope import build_operator_scope_ports
from cadrumo.application.auth.credentials import active_auth_projection_span
from cadrumo.application.auth.sync_readiness import AuthSyncReadiness
from cadrumo.core.auth_provider import AuthProviderKind
from cadrumo.core.config import load_settings
from cadrumo.core.i18n.render import tr
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.entrypoints.cli.config import _censo_auth
from cadrumo_runtime.commands.tests.runtime_profile_cli_fixture import NativeCliProfileFixture, native_cli_profile_scope
from cadrumo_runtime.host.frontend.cli.app import aeat_cli_app
from cadrumo_runtime.host.tests.frontend.cli.native_profile_cli_support import (
    reauthenticate_native_profile,
)


@cache
def _app():
    return aeat_cli_app()


def _invoke(profile: NativeCliProfileFixture, *command: str, output_format: str | None = "json"):
    """Invoke the AEAT executable's real command graph, with native profile admission."""
    assert profile.label is not None
    close_active_bucket_session()
    arguments = ["--language", "en", "--profile", profile.label, "--profile-secrets-stdin"]
    if output_format is not None:
        arguments.extend(("--format", output_format))
    result = CliRunner().invoke(
        _app(), [*arguments, *command], input=json.dumps({"profile_passphrase": profile.passphrase})
    )
    assert profile.passphrase not in result.output
    return result


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
    original = _censo_auth.read_censo_auth
    seen: list[AuthSyncReadiness] = []

    def observe(client):
        readiness = original(client)
        seen.append(readiness)
        return readiness

    # Only terminal input is supplied. Admission, requests, protected transport,
    # persistence and readback all use their production implementations.
    monkeypatch.setattr(_censo_auth, "read_censo_auth", observe)
    monkeypatch.setattr(_censo_auth, "terminal_can_prompt_for_secrets", lambda: True)
    monkeypatch.setattr(_censo_auth.typer, "prompt", lambda *_args, **_kwargs: provider.value)
    monkeypatch.setattr(
        _censo_auth,
        "prompt_secret_no_echo",
        lambda prompt: "synthetic-native-password" if prompt == tr("cli.censo_auth.password") else "",
    )
    with native_cli_profile_scope(tmp_path) as profile:
        observations = []
        profile.failure_observer = observations.append
        profile.register(
            label="native-censo-password",
            facts={
                "identity.name": "Synthetic",
                "identity.surnames": "Censo Password",
                "auth.dni_nie": "12345678Z",
                "activities.description": "synthetic test profile",
            },
        )
        configured = _invoke(profile, "config", "profile", "censo", "pull", "--configure-auth", output_format=None)
        # Keep a missing certificate or a mismatched Cl@ve identity so synthetic
        # credentials cannot reach AEAT. The real preflight names that blocker.
        blocker = "certificate.file" if provider is AuthProviderKind.CERTIFICATE else "auth.identity_alignment"
        assert configured.exit_code != 0, (configured.output, observations)
        assert blocker in configured.output, (configured.output, type(configured.exception).__name__, seen)
        assert "synthetic-native-password" not in configured.output
        password_field = "auth.password" if provider is AuthProviderKind.CLAVE_PERMANENTE else "certificate.passphrase"
        assert any(item.field == password_field and item.satisfied for item in seen[-1].requirements)
        assert not seen[-1].ready
        reopened = _invoke(profile, "config", "profile", "censo", "pull")
        assert reopened.exit_code != 0, (reopened.output, observations)
        assert blocker in reopened.output
        assert "aeat config profile censo pull --configure-auth" in reopened.output
        assert seen[-1].provider == provider.value
        assert any(item.field == password_field and item.satisfied for item in seen[-1].requirements)
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
