"""The MCP setup tools drive the real components role of a built Cadrumo binary.

``just test-components-role IMAGE`` runs these cases with the built binary
(:mod:`cadrumo.tests.components_role_package`). Each case has its own
throwaway storage root, and a local proxy stands in for the network, so
nothing reaches a publisher. The plan the tool returns and the digest the
setup carries are the role's own: the setup the approval binds is refused by
the network before anything moves, and is never asked to review again.
"""

from __future__ import annotations

from typing import cast
from uuid import uuid4

import pytest

from cadrumo.tests.components_role_package import (
    components_role_fixture,
    refusing_proxy_fixture,
    staged_components_role_fixture,
)
from cadrumo_client.transport.frontend_client import FrontendClient

from ..runtime_adapter import RuntimeMcpAdapter
from .test_setup_tools import _Lease

__all__ = ["components_role_fixture", "refusing_proxy_fixture", "staged_components_role_fixture"]

pytestmark = [pytest.mark.integration, pytest.mark.external_tool, pytest.mark.hex_core]


def _adapter() -> RuntimeMcpAdapter:
    lease = _Lease(uuid4())
    return RuntimeMcpAdapter(profile_id=lease.profile_id, client=cast(FrontendClient, lease))


@pytest.mark.anyio
@pytest.mark.usefixtures("components_role")
async def test_the_status_and_plan_of_an_empty_root_come_from_the_role() -> None:
    adapter = _adapter()
    try:
        status = await adapter.call("setup_status", {})
        plan = await adapter.call("setup_plan", {"items": ["browser"]})
        again = await adapter.call("setup_plan", {"items": ["browser"]})
    finally:
        await adapter.close()

    assert status["outcome"] == "ok" and status["setup_complete"] is False
    assert [(row["item_id"], row["state"]) for row in status["rows"]] == [("browser", "absent"), ("local_ai", "absent")]
    assert plan["outcome"] == "ok"
    assert [entry["item_id"] for entry in plan["plan"]["entries"]] == ["browser"]
    assert again["plan_digest"] == plan["plan_digest"]


@pytest.mark.anyio
@pytest.mark.usefixtures("components_role", "refusing_proxy")
async def test_a_setup_under_the_planned_digest_is_refused_by_a_blocking_network_before_anything_moves() -> None:
    adapter = _adapter()
    try:
        plan = await adapter.call("setup_plan", {"items": ["browser"]})
        setup = await adapter.call("setup", {"plan_digest": plan["plan_digest"], "items": ["browser"]})
        after = await adapter.call("setup_status", {"items": ["browser"]})
    finally:
        await adapter.close()

    assert setup["outcome"] == "refused"
    assert (setup["item_id"], setup["failure_category"]) == ("browser", "blocked_by_network")
    assert setup["plan_digest"] == plan["plan_digest"]
    assert "progress" not in setup
    assert [row["state"] for row in after["rows"]] == ["absent"]
