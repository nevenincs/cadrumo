"""MCP reports passive manager guidance without opening a client."""

from uuid import uuid4

import pytest

from cadrumo.application.runtime.contracts import RuntimeRefusalCode
from cadrumo.core.config import override_settings

from ..runtime_adapter import RuntimeMcpAdapter
from ..runtime_admission import AdmissionDenial

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.mark.asyncio
async def test_unavailable_adapter_returns_remedy_without_automatic_request() -> None:
    adapter = RuntimeMcpAdapter(profile_id=uuid4(), client=None)
    adapter._admission_denial = AdmissionDenial(RuntimeRefusalCode.UNAVAILABLE.value)
    with override_settings(cadrumo_output_language="en"):
        status = await adapter.call("status", {})
        reply = await adapter.call("observe", {"observation": {}})
        found = await adapter.call("search", {"family": "auth", "limit": 1})
    assert status["outcome"] == "status" and status["denial"] == "runtime_unavailable"
    assert "manager" in status["remedy"]
    assert reply["outcome"] == "refused" and reply["code"] == "runtime_unavailable"
    assert "manager" in reply["remedy"]
    # Finding an operation needs the session too, so it is refused the same way and names the manager.
    assert found["outcome"] == "refused" and found["code"] == "runtime_unavailable" and "manager" in found["remedy"]
    assert adapter.client is None
    assert "remedy" not in await adapter.call("unknown_tool", {})
    await adapter.close()
