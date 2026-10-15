"""The censal CLI offers saved authentication and reports the worker's blockers."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest
import typer

from cadrumo_client.commands.errors import CliRefusedBoundaryError
from cadrumo_client.transport.frontend_client import FrontendClient

from .....application.auth.sync_readiness import AuthSyncReadiness, AuthSyncRequirement
from .....core.auth_provider import AuthProviderKind
from .....core.output_rendering import OutputFormat
from .. import _censo_auth

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _readiness(*, ready: bool = False) -> AuthSyncReadiness:
    return AuthSyncReadiness(
        provider="clave_movil",
        route="qr",
        ready=ready,
        requirements=(
            AuthSyncRequirement(field="identity.tax_id", satisfied=ready, reason="profile_tax_id_required"),
            AuthSyncRequirement(field="auth.dni_nie", satisfied=ready, reason="clave_identity_required"),
        ),
    )


def _context(monkeypatch: pytest.MonkeyPatch, *, output: OutputFormat, console: bool) -> typer.Context:
    monkeypatch.setattr(_censo_auth, "bound_profile_client", lambda _ctx: object())
    monkeypatch.setattr(_censo_auth, "terminal_can_prompt_for_secrets", lambda: console)
    monkeypatch.setattr(_censo_auth, "format_of", lambda _ctx: output)
    app = typer.Typer()

    @app.command()
    def pull() -> None:
        """Supply a concrete command context for the isolated presenter."""

    return typer.Context(typer.main.get_command(app))


@pytest.mark.parametrize("output,console", [(OutputFormat.JSON, True), (OutputFormat.TEXT, False)])
def test_unattended_pull_reports_all_missing_fields_without_prompting(
    monkeypatch: pytest.MonkeyPatch, output: OutputFormat, console: bool
) -> None:
    context = _context(monkeypatch, output=output, console=console)
    monkeypatch.setattr(_censo_auth, "read_censo_auth", lambda _client: _readiness())

    def no_prompt(*_args: object, **_kwargs: object) -> bool:
        raise AssertionError("Machine output must not prompt")

    monkeypatch.setattr(typer, "confirm", no_prompt)
    with pytest.raises(CliRefusedBoundaryError) as caught:
        _censo_auth.require_censo_auth(context)
    detail = caught.value.context or {}
    assert "identity.tax_id" in str(detail["requirements"])
    assert "auth.dni_nie" in str(detail["requirements"])
    assert detail["command"] == "aeat config profile censo pull --configure-auth"


def test_ready_pull_does_not_prompt_or_modify_authentication(monkeypatch: pytest.MonkeyPatch) -> None:
    context = _context(monkeypatch, output=OutputFormat.TEXT, console=True)
    monkeypatch.setattr(_censo_auth, "read_censo_auth", lambda _client: _readiness(ready=True))

    def no_prompt(*_args: object, **_kwargs: object) -> bool:
        raise AssertionError("Ready authentication should run directly")

    monkeypatch.setattr(typer, "confirm", no_prompt)
    _censo_auth.require_censo_auth(context)


def test_setup_rechecks_saved_readiness_before_allowing_remote_read(monkeypatch: pytest.MonkeyPatch) -> None:
    context = _context(monkeypatch, output=OutputFormat.TEXT, console=True)
    readings = iter((_readiness(), _readiness()))
    monkeypatch.setattr(_censo_auth, "read_censo_auth", lambda _client: next(readings))
    monkeypatch.setattr(typer, "confirm", lambda *_args, **_kwargs: True)
    saved: list[bool] = []
    monkeypatch.setattr(_censo_auth, "_configure", lambda *_args: saved.append(True))
    with pytest.raises(CliRefusedBoundaryError):
        _censo_auth.require_censo_auth(context)
    assert saved == [True]


def test_editing_is_explicitly_available_even_when_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    context = _context(monkeypatch, output=OutputFormat.TEXT, console=True)
    monkeypatch.setattr(_censo_auth, "read_censo_auth", lambda _client: _readiness(ready=True))
    saved: list[bool] = []
    monkeypatch.setattr(_censo_auth, "_configure", lambda *_args: saved.append(True))
    _censo_auth.require_censo_auth(context, configure=True)
    assert saved == [True]


def test_password_uses_protected_channel_and_is_erased(monkeypatch: pytest.MonkeyPatch) -> None:
    password = uuid4().hex
    monkeypatch.setattr(_censo_auth, "prompt_secret_no_echo", lambda _prompt: password)
    profile_id = uuid4()
    client = cast(FrontendClient, SimpleNamespace(profile_id=profile_id))
    observed: list[bytearray] = []

    def submit(_client: FrontendClient, payload: object, **options: object) -> SimpleNamespace:
        assert password not in str(payload)
        assert options["subject_ref"] == f"profile:{profile_id}"
        secret = options["secret"]
        assert isinstance(secret, bytearray)
        assert password.encode() in secret
        observed.append(secret)
        return SimpleNamespace(projection=SimpleNamespace(saved=True, provider="clave_permanente"))

    monkeypatch.setattr(_censo_auth, "run_registered_operation", submit)
    _censo_auth._save_password(client, AuthProviderKind.CLAVE_PERMANENTE)
    assert observed and not any(observed[0])
