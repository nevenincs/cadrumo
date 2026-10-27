"""Parsed CLI provisioning through a real profile worker and the native role.

The fixture controls native peer/login observation and connects the CLI's
installed-client factory to the test runtime endpoint. Admission, operation
execution, review, the profile journal and the components binary are real.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from uuid import UUID

import pytest

from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.application.components_operations import (
    COMPONENTS_SETUP_OPERATION_ID,
    COMPONENTS_STATUS_OPERATION_ID,
    COMPONENTS_VERIFY_OPERATION_ID,
)
from cadrumo.application.operations.persistence.journal import OperationPersistedSnapshot
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.core.config import override_settings
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition
from cadrumo.entrypoints.cli.tests.cli_runner import invoke_typer_app
from cadrumo.tests.components_role_package import (
    CountingProxy,
    components_role_fixture,
    counting_proxy_fixture,
    staged_components_role_fixture,
)
from cadrumo_client.commands import profile_admission
from cadrumo_client.contracts.contracts import ClientHello
from cadrumo_client.transport.framing import VerifiedConnection
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_runtime.adapters.tests.profile_worker_support import PROFILE_INPUT
from cadrumo_runtime.host.frontend.cli.app import aeat_cli_app
from cadrumo_runtime.host.tests.test_service_records import ServiceRecordRuntime, service_record_runtime

__all__ = ["components_role_fixture", "counting_proxy_fixture", "staged_components_role_fixture"]
pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.external_tool, pytest.mark.windows_only]


def _connect_cli(runtime: ServiceRecordRuntime, monkeypatch: pytest.MonkeyPatch) -> None:
    async def open_client(*, profile_id: UUID, frontend: OperationFrontendProjection) -> FrontendClient:
        assert profile_id == runtime.profile_id and frontend is OperationFrontendProjection.CLI
        connection = VerifiedConnection(
            runtime.endpoint.connect(timeout=3),
            expected=ClientHello(product_version="test", storage_identity=runtime.endpoint.storage_identity),
            deadline=time.monotonic() + 3,
        )
        return FrontendClient(connection, profile_id=profile_id, frontend=frontend)

    monkeypatch.setattr(profile_admission, "open_installed_client", open_client)


def _snapshots(root: Path) -> list[OperationPersistedSnapshot]:
    async def read() -> list[OperationPersistedSnapshot]:
        journal = OperationJournalRepository(storage_root=root)
        page = await journal.inventory_page(after=None, limit=128)
        assert not page.has_more
        return [await journal.load(entry.operation_id) for entry in page.entries]

    return asyncio.run(read())


@pytest.mark.usefixtures("components_role")
def test_parsed_cli_runs_registered_provisioning_against_real_role(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, counting_proxy: CountingProxy
) -> None:
    with service_record_runtime(tmp_path / "profile") as runtime, override_settings(cadrumo_output_language="en"):
        _connect_cli(runtime, monkeypatch)
        common = ["--format", "json", "--profile", str(runtime.profile_id), "--profile-secrets-stdin"]
        secret = json.dumps({"profile_passphrase": PROFILE_INPUT})

        def invoke(*args: str):
            return invoke_typer_app(aeat_cli_app(), [*common, "config", "provision", *args], input=secret)

        status = invoke("status")
        assert status.exit_code == 0, status.output
        quick = json.loads(status.stdout)["result"]
        assert quick["mode"] == "quick"
        assert [(item["item_id"], item["state"], item["recovery"]) for item in quick["items"]] == [
            ("browser", "absent", "set_up"),
            ("local_ai", "absent", "set_up_in_desktop"),
        ]
        assert counting_proxy.tunnels == {} and counting_proxy.unauthenticated == 0

        declined = invoke("setup")
        assert declined.exit_code == 2, declined.output
        result = json.loads(declined.stdout)["result"]
        assert result["outcome"] == "rejected" and result["approved"] is False
        assert result["plan_digest"] and result["plan_digest"] in declined.stderr
        assert counting_proxy.tunnels == {} and counting_proxy.unauthenticated == 0

        probe = invoke("probe")
        verify = invoke("verify", "--item", "browser")
        assert probe.exit_code == 0, probe.output
        assert verify.exit_code == 2, verify.output
        assert json.loads(probe.stdout)["result"]["mode"] == "full"
        verified = json.loads(verify.stdout)["result"]
        assert verified["mode"] == "full" and [row["item_id"] for row in verified["items"]] == ["browser"]

        snapshots = _snapshots(runtime.root)
        definitions = [snapshot.identity.definition_id for snapshot in snapshots]
        assert definitions.count(COMPONENTS_STATUS_OPERATION_ID) == 1
        assert definitions.count(COMPONENTS_VERIFY_OPERATION_ID) == 2
        assert definitions.count(COMPONENTS_SETUP_OPERATION_ID) == 1
        setup = next(
            snapshot for snapshot in snapshots if snapshot.identity.definition_id == COMPONENTS_SETUP_OPERATION_ID
        )
        assert setup.terminal_condition is OperationTerminalCondition.SUCCEEDED
        assert setup.effect is OperationEffect.NONE
        assert len(setup.consumed_interactions) == 1
        decision = setup.consumed_interactions[0]
        assert decision.response_action == "reject"
        assert decision.checkpoint.baseline_digest == result["plan_digest"]
