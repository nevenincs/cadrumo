"""The MCP relay, as a process of a hosted agent's tree runs it: read and edit the profile, and report.

Run with the profile named by ``CADRUMO_ACTIVE_PROFILE``. It builds the real
MCP server over the real runtime adapter, which signs in the only way the
relay knows, and drives it through the MCP SDK's memory transport. Like the
installed ``cadrumo-mcp``, it is the root of its own process, so it binds the
profile-persistence ports a resumed sign-in reads its receipt through before
the adapter runs. It prints one JSON line with the admission the server reports.
"""

from __future__ import annotations

import asyncio
import json
import os
from uuid import UUID

from cadrumo.adapters.persistence.storage.profile_persistence_composition import composed_profile_persistence_ports
from cadrumo_harness.mcp.runtime_adapter import RuntimeMcpAdapter
from cadrumo_harness.mcp.server import build_server
from cadrumo_harness.mcp.tests.agent_key_reads import edit_profile_and_read_back
from cadrumo_harness.mcp.tests.session import connected_server_and_client_session


async def _relay(profile_id: UUID) -> dict[str, object]:
    adapter = RuntimeMcpAdapter(profile_id=None, client=None, requests_attendance=True)
    try:
        async with connected_server_and_client_session(build_server(adapter)) as sdk:
            status = await sdk.call_tool("status", {})
            if status.is_error:
                return {"admitted": False, "status": status.structured_content}
            await edit_profile_and_read_back(sdk, profile_id)
            return {"admitted": True, "session": status.structured_content.get("session")}
    finally:
        await adapter.close()


def main() -> None:
    """Relay once for the active profile and print what it was admitted as."""
    with composed_profile_persistence_ports():
        result = asyncio.run(_relay(UUID(os.environ["CADRUMO_ACTIVE_PROFILE"])))
    print(json.dumps(result, default=str))


if __name__ == "__main__":
    main()
