"""An asset refusal reaches an agent through the real MCP service with its reason key and facts.

The MCP server, its runtime adapter and the registered operation are the
production ones; the runtime is the host's portable human runtime, whose person signs
in with the profile password and approves the agent's attendance. The asset is
a battery-electric van entering service in 2023, whose forecast the product
refuses under the accelerated regime it does not compute.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from datetime import date
from pathlib import Path
from threading import Event, Thread
from typing import Any
from uuid import UUID

import pytest
from click.testing import Result

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.core.config import load_settings
from cadrumo.entrypoints.cli.tests.cli_fixture_worlds import CliWorldProvider, bind_cli_fixture_ports
from cadrumo.tests.cli_fixture_ports import CliInvocation
from cadrumo_client.transport.installed_client import open_installed_client
from cadrumo_mcp.mcp.runtime_adapter import RuntimeMcpAdapter
from cadrumo_mcp.mcp.server import build_server
from cadrumo_mcp.mcp.tests.session import connected_server_and_client_session
from cadrumo_runtime.host.tests.frontend.cli.cli_runner import bind_public_cli_runner, invoke_cached_cli
from cadrumo_runtime.host.tests.frontend.cli.runtime_profile_backend import runtime_cli_profile
from cadrumo_runtime.host.tests.frontend.cli.test_actividad_asset_accelerated_da18_cli import (
    electric_van,
    seed_direct_normal_profile,
    van_payment,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]

_ASSET_ID = "van-2023"
_IN_SERVICE = date(2023, 3, 1)
_DA18_CODE = "REFUSED_ACTIVIDAD_ASSET_ACCELERATED_DA18_DEPRECIATION_NOT_COMPUTED"
_DA18_REASON_KEY = "ledger.actividad_asset.errors.accelerated_da18_depreciation"


def _approve_attendance(holder: Any, stop: Event) -> None:
    deadline = time.monotonic() + 60
    while not stop.is_set() and time.monotonic() < deadline:
        candidates = holder.attendance_inventory().candidates
        if candidates:
            holder.decide_attendance(candidates[0].attendance_id, approve=True)
            return
        time.sleep(0.1)


async def _forecast_through_mcp(profile_id: UUID) -> dict[str, Any]:
    """Forecast the van as an attended agent and return what the MCP tool answered."""
    holder = await open_installed_client(profile_id=profile_id, frontend=OperationFrontendProjection.CLI)
    stop = Event()
    try:
        passphrase = load_settings().cadrumo_dev_test_database_password.get_secret_value()
        await asyncio.to_thread(holder.login_password, bytearray(passphrase.encode()), timeout=120)
        approver = Thread(target=_approve_attendance, args=(holder, stop), daemon=True)
        approver.start()
        adapter = RuntimeMcpAdapter(profile_id=profile_id, client=None, requests_attendance=True)
        try:
            async with connected_server_and_client_session(build_server(adapter)) as client:
                executed = await client.call_tool(
                    "execute",
                    {
                        "definition_id": "ledger.actividad-asset.forecast",
                        "payload": {
                            "profile_id": str(profile_id),
                            "asset_id": _ASSET_ID,
                            "covered_from": "2023-01-01",
                            "covered_until": "2024-01-01",
                            "requested_free_amount": {"decimal": "30000.00"},
                        },
                        "wait_seconds": 5,
                    },
                )
                assert executed.structured_content is not None
                return executed.structured_content
        finally:
            await adapter.close()
    finally:
        stop.set()
        await asyncio.to_thread(holder.close)


def test_a_forecast_refusal_reaches_the_agent_with_its_reason_key_and_facts(
    tmp_path: Path,
    run_cadrumo_cli: Callable[..., Result],
    cli_world_provider: CliWorldProvider,
    invoke_cli: CliInvocation,
) -> None:
    with (
        bind_public_cli_runner(run_cadrumo_cli),
        bind_cli_fixture_ports(cli_world_provider, invoke_cli),
        runtime_cli_profile(tmp_path=tmp_path, label="mcp asset refusal") as profile,
    ):
        seed_direct_normal_profile(profile.storage_root, profile.bucket_id)
        payment = van_payment(_ASSET_ID, _IN_SERVICE)
        created = invoke_cached_cli(
            [
                *("--format", "json", "app", "ledger", "actividad-asset", "create"),
                *("--name", _ASSET_ID),
                electric_van(_ASSET_ID, _IN_SERVICE, payment),
            ],
        )
        assert created.exit_code == 0, created.output
        executed = asyncio.run(_forecast_through_mcp(UUID(profile.bucket_id)))

    assert executed["outcome"] == "submitted", executed
    projection = executed["reply"]["observation"]["projection"]
    assert projection["terminal_condition"] == "refused"
    assert projection["effect"] == "none"
    result = executed["completion"]["document"]["projection"]
    assert result["outcome"] == "refused"
    assert result["forecast"] is None
    refusal = result["refusal"]
    assert refusal["code"] == _DA18_CODE == projection["refusal_ref"]
    assert refusal["reason_key"] == _DA18_REASON_KEY
    assert {fact["key"]: fact["value"] for fact in refusal["reason_facts"]} == {
        "asset_id": _ASSET_ID,
        "legal_reference": "ley-27-2014:da-18",
        "method": "electric_vehicle_free",
        "tax_year": "2023",
    }
