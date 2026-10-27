"""Repair optionally proves a current sign-in without acquiring login authority."""

from __future__ import annotations

import asyncio
from typing import cast
from uuid import UUID, uuid4

import pytest
import typer

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.core.async_cleanup import AsyncResourceCleanupError, close_async_resources
from cadrumo.core.profile_session import ProfileSessionRefusalReason
from cadrumo_client.commands.profile_binding import bound_profile_client
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.profile_selection import ActiveProfileReply
from cadrumo_client.contracts.sign_in import SignInPresence
from cadrumo_client.contracts.sign_in_outcomes import ProfileReceiptRefusedError
from cadrumo_client.transport.framing import VerifiedConnection
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.installation_client import InstallationClient

from .. import optional_profile_connection as optional
from .cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _context() -> typer.Context:
    app = typer.Typer()

    @app.command()
    def noop() -> None:
        return

    return typer.Context(typer.main.get_command(app))


class _Discovery:
    def __init__(self, profile_id: UUID | None) -> None:
        self.profile_id = profile_id
        self.closed = False
        self.close_error: Exception | None = None

    def active_profile(self) -> ActiveProfileReply:
        return ActiveProfileReply(
            request_id=uuid4(),
            runtime_boot_id=uuid4(),
            connection_id=uuid4(),
            selected_profile_id=self.profile_id,
            signed_in_profile_id=self.profile_id,
            presence=SignInPresence.ABSENT if self.profile_id is None else SignInPresence.PRESENT,
        )

    def close(self) -> None:
        if self.close_error is not None:
            raise self.close_error
        self.closed = True


def _discovery(monkeypatch: pytest.MonkeyPatch, profile_id: UUID | None) -> _Discovery:
    discovery = _Discovery(profile_id)

    async def open_discovery() -> InstallationClient:
        return cast(InstallationClient, discovery)

    monkeypatch.setattr(optional, "open_installed_installation_client", open_discovery)
    return discovery


@pytest.mark.parametrize("signed_in", [False, True])
def test_parsed_repair_binds_only_a_proven_current_profile(monkeypatch: pytest.MonkeyPatch, signed_in: bool) -> None:
    profile_id = uuid4()
    discovery = _discovery(monkeypatch, profile_id if signed_in else None)
    connection = _Discovery(profile_id)
    client = FrontendClient(
        cast(VerifiedConnection, connection), profile_id=profile_id, frontend=OperationFrontendProjection.CLI
    )
    resumed: list[UUID] = []

    async def open_profile(*, profile_id: UUID, frontend: OperationFrontendProjection) -> FrontendClient:
        assert signed_in
        assert discovery.closed
        assert profile_id == client.profile_id
        assert frontend is OperationFrontendProjection.CLI
        return client

    monkeypatch.setattr(optional, "open_installed_client", open_profile)
    monkeypatch.setattr(FrontendClient, "resume_receipt", lambda self: resumed.append(self.profile_id))

    def report(ctx: typer.Context) -> None:
        if signed_in:
            assert bound_profile_client(ctx) is client
            assert resumed == [profile_id]
        else:
            with pytest.raises(RefusalError):
                bound_profile_client(ctx)
        typer.echo("repair-bootstrap-reached")

    monkeypatch.setattr("cadrumo.entrypoints.cli.config.repair_commands.repair", report)
    result = invoke_cached_cli(["config", "repair"])
    assert result.exit_code == 0, result.output
    assert "repair-bootstrap-reached" in result.output
    assert discovery.closed
    assert connection.closed is signed_in


def test_unavailable_runtime_keeps_repair_sessionless(monkeypatch: pytest.MonkeyPatch) -> None:
    async def unavailable() -> InstallationClient:
        raise RefusalError(RefusalCode.UNAVAILABLE)

    monkeypatch.setattr(optional, "open_installed_installation_client", unavailable)
    ctx = _context()
    with ctx:
        optional.bind_optional_current_profile(ctx)
        with pytest.raises(RefusalError):
            bound_profile_client(ctx)


@pytest.mark.parametrize("close_fails", [False, True])
def test_native_proof_refusal_never_binds_and_retains_failed_close(
    monkeypatch: pytest.MonkeyPatch, close_fails: bool
) -> None:
    profile_id = uuid4()
    _discovery(monkeypatch, profile_id)
    connection = _Discovery(profile_id)
    connection.close_error = OSError("release failed") if close_fails else None
    client = FrontendClient(
        cast(VerifiedConnection, connection), profile_id=profile_id, frontend=OperationFrontendProjection.CLI
    )
    refusal = ProfileReceiptRefusedError(ProfileSessionRefusalReason.ABSENT)

    async def open_profile(**_kwargs: object) -> FrontendClient:
        return client

    def refuse(self: FrontendClient) -> None:
        raise refusal

    monkeypatch.setattr(optional, "open_installed_client", open_profile)
    monkeypatch.setattr(FrontendClient, "resume_receipt", refuse)
    ctx = _context()
    with ctx:
        if not close_fails:
            optional.bind_optional_current_profile(ctx)
            assert connection.closed
            with pytest.raises(RefusalError):
                bound_profile_client(ctx)
            return
        with pytest.raises(ProfileReceiptRefusedError) as caught:
            optional.bind_optional_current_profile(ctx)
        assert caught.value is refusal
        cleanup = refusal.__dict__["async_cleanup_error"]
        assert isinstance(cleanup, AsyncResourceCleanupError)
        assert cleanup.resources
        with pytest.raises(RefusalError):
            bound_profile_client(ctx)
        connection.close_error = None
        asyncio.run(close_async_resources(*cleanup.resources, task_name="test-repair-release", primary_error=None))
        assert connection.closed


def test_discovery_release_failure_is_not_unavailability(monkeypatch: pytest.MonkeyPatch) -> None:
    discovery = _discovery(monkeypatch, None)
    discovery.close_error = OSError("release failed")
    ctx = _context()
    with ctx:
        with pytest.raises(AsyncResourceCleanupError) as caught:
            optional.bind_optional_current_profile(ctx)
        assert caught.value.resources
        discovery.close_error = None
        asyncio.run(
            close_async_resources(*caught.value.resources, task_name="test-discovery-release", primary_error=None)
        )
        assert discovery.closed
