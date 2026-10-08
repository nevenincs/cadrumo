"""MCP reports passive manager guidance without opening a client."""

from uuid import uuid4

import pytest

from cadrumo.application.runtime.contracts import RuntimeRefusalCode
from cadrumo.core.config import override_settings

from ..runtime_adapter import RuntimeMcpAdapter

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.mark.asyncio
async def test_unavailable_adapter_returns_remedy_without_automatic_request() -> None:
    adapter = RuntimeMcpAdapter(profile_id=uuid4(), client=None)
    adapter._startup_denial = RuntimeRefusalCode.UNAVAILABLE.value
    with override_settings(cadrumo_output_language="en"):
        status = await adapter.call("status", {})
        reply = await adapter.call("search", {})
    assert status["outcome"] == "status" and status["denial"] == "runtime_unavailable"
    assert "manager" in status["remedy"]
    assert reply["outcome"] == "refused" and reply["code"] == "runtime_unavailable"
    assert "manager" in reply["remedy"]
    assert adapter.client is None
    assert "remedy" not in await adapter.call("unknown_tool", {})
    await adapter.close()
