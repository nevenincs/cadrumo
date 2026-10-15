"""Activity uses existing proof, records only authenticated input, and always closes."""

from __future__ import annotations

from typing import cast, override
from uuid import uuid4

import pytest

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.login_session import ProfileReceiptRefusedError
from cadrumo.core.bucket_pointer import BucketPointer
from cadrumo.core.profile_session import ProfileSessionRefusalReason
from cadrumo_client.contracts.profile_access import ProfileStatus
from cadrumo_client.transport import installed_client
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo_runtime.commands import activity
from cadrumo_runtime.commands.command_specs import RUNTIME_COMMAND_GRAPH

from .runtime_cli import invoke_runtime_cli, unwrap_cli_result

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


class _ActivityClient(FrontendClient):
    def __init__(self, failure: str | None) -> None:
        self._profile_id = uuid4()
        self.calls: list[str] = []
        self.failure = failure

    @override
    def resume_receipt(self, *, timeout: float = 5, activity_only: bool = False) -> ProfileStatus:
        assert activity_only
        self.calls.append("resume")
        if self.failure == "resume":
            raise ProfileReceiptRefusedError(ProfileSessionRefusalReason.ABSENT)
        return cast(ProfileStatus, object())

    @override
    def note_activity(self, *, timeout: float = 5) -> ProfileStatus:
        self.calls.append("activity")
        if self.failure == "activity":
            raise FrontendRefusedError("session_expired")
        return cast(ProfileStatus, object())

    @override
    def close(self) -> None:
        self.calls.append("close")


@pytest.mark.parametrize("failure", [None, "resume", "activity", "unselected"])
def test_activity_command_uses_existing_proof_and_closes(monkeypatch: pytest.MonkeyPatch, failure: str | None) -> None:
    client = _ActivityClient(failure)
    pointer = (
        BucketPointer.absent(transition_revision=0)
        if failure == "unselected"
        else BucketPointer.selected(bucket_id=str(client.profile_id), transition_revision=1)
    )
    monkeypatch.setattr(activity, "observe_active_profile_pointer", lambda: pointer)

    async def open_client(*, profile_id: object, frontend: OperationFrontendProjection) -> FrontendClient:
        assert profile_id == client.profile_id and frontend is OperationFrontendProjection.CLI
        return client

    monkeypatch.setattr(installed_client, "open_installed_client", open_client)
    result = invoke_runtime_cli(("--format", "json", "config", "activity"))
    if failure is None:
        assert result.exit_code == 0, result.output
        assert unwrap_cli_result(result) == {"activity_recorded": True}
        assert client.calls == ["resume", "activity", "close"]
    else:
        assert result.exit_code != 0, result.output
        assert "Traceback" not in result.output
        assert client.calls == (
            []
            if failure == "unselected"
            else ["resume", "close"]
            if failure == "resume"
            else ["resume", "activity", "close"]
        )


def test_activity_result_contract_is_owned_by_runtime_graph() -> None:
    spec = RUNTIME_COMMAND_GRAPH.by_schema_identity()["config.activity"]
    assert spec.result_schema.target is not None
    assert spec.result_schema.target.identity == "cadrumo_client.commands.custody_payloads:ConfigActivityResult"
