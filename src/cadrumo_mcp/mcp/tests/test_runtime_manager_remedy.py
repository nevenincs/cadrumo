"""MCP reports passive manager guidance without opening a client."""

from uuid import uuid4

import pytest

from cadrumo.core.config import override_settings
from cadrumo.tests.log_records import delivered_records, delivered_text
from cadrumo_client.contracts.contracts import RefusalCode

from ..runtime_adapter import RuntimeMcpAdapter
from ..runtime_admission import AdmissionDenial

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.mark.asyncio
async def test_unavailable_adapter_returns_remedy_without_automatic_request(caplog: pytest.LogCaptureFixture) -> None:
    adapter = RuntimeMcpAdapter(profile_id=uuid4(), client=None)
    adapter._admission_denial = AdmissionDenial(RefusalCode.UNAVAILABLE.value)
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
    records = [
        record.getMessage() for record in delivered_records(caplog) if "MCP tool refused:" in record.getMessage()
    ]
    assert records == [
        "MCP tool refused: tool=status reason=runtime_unavailable",
        "MCP tool refused: tool=observe reason=runtime_unavailable",
        "MCP tool refused: tool=search reason=runtime_unavailable",
    ]
    assert "remedy" not in await adapter.call("unknown_tool", {})
    assert "MCP tool refused: reason=unknown_tool" in delivered_text(caplog)
    await adapter.close()


@pytest.mark.asyncio
async def test_scope_refusal_is_logged_without_claiming_the_person_is_signed_out(
    caplog: pytest.LogCaptureFixture,
) -> None:
    adapter = RuntimeMcpAdapter(profile_id=uuid4(), client=None)
    adapter._admission_denial = AdmissionDenial("privilege_expansion")
    reply = await adapter.call("status", {})
    assert reply["denial"] == "privilege_expansion"
    assert "does not mean the person is signed out" in reply["remedy"]
    assert "MCP tool refused: tool=status reason=privilege_expansion" in delivered_text(caplog)
    await adapter.close()
