"""CLI observation does not borrow authority; refused sign-out keeps selection."""

from __future__ import annotations

from typing import override
from uuid import uuid4

import pytest
import typer

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile import profile_pointer
from cadrumo.application.workflow import profile_bucket_scan
from cadrumo.core.bucket_pointer import BucketPointer
from cadrumo.core.config import override_settings
from cadrumo.core.json_contract import OutputSchema
from cadrumo_client.commands import custody
from cadrumo_client.commands.custody_payloads import ConfigSignInStatusResult
from cadrumo_client.commands.errors import CliRefusedBoundaryError
from cadrumo_client.contracts.sign_in import (
    HumanSignedOut,
    SignInPresence,
    SignInStatus,
    SignInStatusReply,
)
from cadrumo_client.transport import installed_client
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo_runtime.commands import sign_in_status
from cadrumo_runtime.commands.tests.config.runtime_cli import invoke_runtime_cli, unwrap_cli_result

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


class _ObservationClient(FrontendClient):
    def __init__(self) -> None:
        self._profile_id = uuid4()
        self.observed = 0
        self.closed = 0

    @override
    def sign_in_status(self, *, timeout: float = 5) -> SignInStatusReply:
        self.observed += 1
        return SignInStatusReply(
            request_id=uuid4(),
            runtime_boot_id=uuid4(),
            connection_id=uuid4(),
            profile_id=self.profile_id,
            status=SignInStatus(presence=SignInPresence.UNKNOWN),
        )

    @override
    def human_sign_out(self, *, timeout: float = 10) -> HumanSignedOut:
        raise FrontendRefusedError("authentication_required")

    @override
    def close(self) -> None:
        self.closed += 1


@pytest.mark.parametrize("selected", [False, True])
def test_status_keeps_unknown_distinct_and_never_borrows_proof(monkeypatch: pytest.MonkeyPatch, selected: bool) -> None:
    client = _ObservationClient()
    pointer = (
        BucketPointer.selected(bucket_id=str(client.profile_id), transition_revision=1)
        if selected
        else BucketPointer.absent(transition_revision=0)
    )
    monkeypatch.setattr(profile_pointer, "observe_active_profile_pointer", lambda: pointer)
    monkeypatch.setattr(sign_in_status, "activate_subcommand_output_language", lambda *_: None)
    emitted: list[OutputSchema] = []

    async def open_client(*, profile_id: object, frontend: OperationFrontendProjection) -> FrontendClient:
        assert selected and profile_id == client.profile_id and frontend is OperationFrontendProjection.CLI
        return client

    def emit(_ctx: typer.Context, *, command: str, result: OutputSchema, lines: tuple[str, ...]) -> None:
        assert command == "config.sign-in-status" and lines
        emitted.append(result)

    monkeypatch.setattr(installed_client, "open_installed_client", open_client)
    monkeypatch.setattr(sign_in_status, "emit_envelope", emit)
    sign_in_status.config_sign_in_status(typer.Context(typer.main.TyperCommand("test")))
    assert len(emitted) == 1 and isinstance(emitted[0], ConfigSignInStatusResult)
    assert emitted[0].status.presence is (SignInPresence.UNKNOWN if selected else SignInPresence.ABSENT)
    assert client.observed == client.closed == int(selected)


def test_runtime_parser_reports_the_selected_profile_without_borrowing_proof(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _ObservationClient()
    pointer = BucketPointer.selected(bucket_id=str(client.profile_id), transition_revision=1)
    monkeypatch.setattr(profile_pointer, "observe_active_profile_pointer", lambda: pointer)

    async def open_client(*, profile_id: object, frontend: OperationFrontendProjection) -> FrontendClient:
        assert profile_id == client.profile_id and frontend is OperationFrontendProjection.CLI
        return client

    monkeypatch.setattr(installed_client, "open_installed_client", open_client)
    with override_settings(cadrumo_cli_reveal_identifiers=True):
        result = invoke_runtime_cli(("--format", "json", "config", "sign-in-status"))
    assert result.exit_code == 0, result.output
    assert unwrap_cli_result(result) == {
        "profile_id": str(client.profile_id),
        "status": {"presence": "unknown", "idle_deadline": None, "absolute_deadline": None},
    }
    assert client.observed == client.closed == 1


def test_refused_global_sign_out_closes_connection_without_clearing_pointer(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _ObservationClient()
    pointer = BucketPointer.selected(bucket_id=str(client.profile_id), transition_revision=1)
    monkeypatch.setattr(profile_pointer, "observe_active_profile_pointer", lambda: pointer)
    monkeypatch.setattr(profile_bucket_scan, "read_profile_bucket", lambda _: None)
    monkeypatch.setattr(custody, "_activate_subcommand_output_language", lambda *_: None)
    monkeypatch.setattr(profile_pointer, "active_profile_pointer_transaction", lambda: pytest.fail("premature clear"))

    async def open_client(*, profile_id: object, frontend: OperationFrontendProjection) -> FrontendClient:
        assert profile_id == client.profile_id and frontend is OperationFrontendProjection.CLI
        return client

    monkeypatch.setattr(custody, "open_installed_client", open_client)
    with pytest.raises(CliRefusedBoundaryError):
        custody.config_logout(typer.Context(typer.main.TyperCommand("test")))
    assert client.closed == 1
