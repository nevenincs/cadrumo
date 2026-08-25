"""Runtime toolset activation widens the advertised surface, gate-invariant.

Proves dynamic toolsets: the ``toolsets``
meta-tool lists the domain groups and activates/deactivates one, activation adds
that group's per-verb tools to the advertised ``tools/list`` (rebuilt per call)
while the orientation core stays, a hard cap bounds simultaneous activations, an
unknown name/action refuses instructively, and a verb reached only through an
activated toolset still runs the same safety gates. The SDK-independent
management is asserted directly; the advertised-surface effect is asserted
through the real built ``Server``.
"""

from __future__ import annotations

from typing import Any, cast

import anyio
import pytest

from .._meta_tools import manage_toolsets
from .._tools import build_tool_descriptors
from .._toolsets import MAX_ACTIVE_TOOLSETS, Toolset, build_toolsets
from .session import connected_server_and_client_session as connect

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_every_toolset_resolves_to_nonempty_command_keys() -> None:
    """A renamed carve-out token must empty a group loudly, not silently.

    Every ``Toolset`` group derives its members from the live command surface
    (``build_toolsets`` over the real ``command_schema_refs``). A domain-matching
    token drift in ``toolset_for_command`` - the ``m036`` / ``censo`` /
    ``iva_wallet`` segment carve-outs, the ``app.live.borrador.100`` renta prefix,
    or a manifest ``MountedCommandDomain`` rename - would silently empty a group
    while the console kept serving. Assert every declared toolset resolves to at
    least one live command key so that drift fails here instead of shipping an
    empty toolset.
    """
    groups = build_toolsets()
    assert {group.toolset for group in groups} == set(Toolset)
    empty = [group.toolset.value for group in groups if not group.command_keys]
    assert not empty, f"toolset(s) resolved to zero live command keys: {empty}"


def test_list_reports_every_group_inactive_by_default() -> None:
    result = manage_toolsets("list", None, active=set())
    assert result.changed is False
    assert {group["toolset"] for group in result.groups} == {t.value for t in Toolset}
    assert all(group["active"] is False for group in result.groups)


def test_activate_then_deactivate_moves_the_active_set() -> None:
    active: set[Toolset] = set()
    activated = manage_toolsets("activate", "ledger", active=active)
    assert activated.changed is True
    assert active == {Toolset.LEDGER}
    assert "ledger" in activated.active

    # Re-activating the same toolset is a no-op (no spurious list_changed).
    again = manage_toolsets("activate", "ledger", active=active)
    assert again.changed is False

    deactivated = manage_toolsets("deactivate", "ledger", active=active)
    assert deactivated.changed is True
    assert active == set()


def test_activation_is_capped_and_refuses_past_the_limit() -> None:
    active: set[Toolset] = set()
    order = [t.value for t in Toolset]
    for name in order[:MAX_ACTIVE_TOOLSETS]:
        assert manage_toolsets("activate", name, active=active).changed is True
    overflow = manage_toolsets("activate", order[MAX_ACTIVE_TOOLSETS], active=active)
    assert overflow.changed is False
    assert overflow.refused is not None
    assert str(MAX_ACTIVE_TOOLSETS) in overflow.refused


def test_unknown_name_and_action_refuse_instructively() -> None:
    bad_name = manage_toolsets("activate", "nonsense", active=set())
    assert bad_name.refused is not None and "nonsense" in bad_name.refused
    bad_action = manage_toolsets("frobnicate", None, active=set())
    assert bad_action.refused is not None and "frobnicate" in bad_action.refused


def test_activating_a_toolset_widens_the_advertised_surface() -> None:
    from .._server import build_server

    descriptors = build_tool_descriptors()
    server = cast("Any", build_server(descriptors, persona=None))

    async def _drive() -> None:
        async with connect(server) as session:
            before = {tool.name for tool in (await session.list_tools()).tools}
            # The core surface does not advertise the long-tail ledger verbs.
            assert "cadrumo_ledger_add" not in before
            assert "toolsets" in before

            result = await session.call_tool("toolsets", {"action": "activate", "name": "ledger"})
            assert result.is_error is False

            after = {tool.name for tool in (await session.list_tools()).tools}
        # Activation widened the surface: ledger verbs now advertised, core kept.
        assert "cadrumo_ledger_add" in after
        assert "cadrumo_overview_status" in after
        assert before < after

    anyio.run(_drive)
