"""The console advertises an orientation core, not the flat verb universe.

Proves the surface policy: the default
``core`` surface advertises only the always-on floor / grounding / meta tools
plus the orientation slice (the ``overview`` family), the ``full``
opt-out restores the flat per-verb surface, and a verb outside the advertised
core stays reachable (``by_name`` spans every descriptor) so it is discovered,
not lost. The SDK-independent policy is asserted directly; the advertised
``tools/list`` is asserted through the real built ``Server`` under both modes.
When the ``cadrumo[agent]`` extra is absent the SDK-dependent build fails at the
optional-dependency boundary rather than skipping, matching the sibling tests.
"""

from __future__ import annotations

from typing import Any, cast

import anyio
import pytest

from .._harness_tools import HARNESS_LOAD_TOOL
from .._surface import (
    SURFACE_ENV_VAR,
    SurfaceMode,
    advertised_descriptors,
    is_orientation_command,
    resolve_surface_mode,
)
from .._tools import build_tool_descriptors
from ._session import connected_server_and_client_session as connect

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

# A concrete orientation command and a concrete long-tail command, used to prove
# the split is real against the live descriptor set rather than a tautology.
_ORIENTATION_KEY = "overview.status"
_LONG_TAIL_KEY = "ledger.add"


def test_resolve_surface_mode_defaults_to_core_when_unset_or_blank() -> None:
    assert resolve_surface_mode(None) is SurfaceMode.CORE
    assert resolve_surface_mode("") is SurfaceMode.CORE
    assert resolve_surface_mode("   ") is SurfaceMode.CORE


def test_resolve_surface_mode_reads_the_named_modes_case_insensitively() -> None:
    assert resolve_surface_mode("core") is SurfaceMode.CORE
    assert resolve_surface_mode("FULL") is SurfaceMode.FULL
    assert resolve_surface_mode("  Full  ") is SurfaceMode.FULL


def test_resolve_surface_mode_rejects_an_unknown_value_naming_the_accepted_set() -> None:
    with pytest.raises(ValueError, match="core, full") as excinfo:
        resolve_surface_mode("verbose")
    assert SURFACE_ENV_VAR in str(excinfo.value)


def test_is_orientation_command_covers_the_overview_family() -> None:
    assert is_orientation_command("overview.status")
    assert is_orientation_command("overview.agenda")
    assert not is_orientation_command("ledger.add")
    assert not is_orientation_command("modelo.work.calculate")


def test_advertised_descriptors_core_is_a_strict_orientation_subset_of_full() -> None:
    descriptors = build_tool_descriptors()
    full = advertised_descriptors(descriptors, mode=SurfaceMode.FULL)
    core = advertised_descriptors(descriptors, mode=SurfaceMode.CORE)

    assert full == descriptors
    assert len(core) < len(full)
    core_keys = {descriptor.command_key for descriptor in core}
    assert all(is_orientation_command(key) for key in core_keys)
    assert _ORIENTATION_KEY in core_keys
    assert _LONG_TAIL_KEY not in core_keys
    assert _LONG_TAIL_KEY in {descriptor.command_key for descriptor in full}


def test_built_server_advertises_core_by_default_and_full_on_opt_out() -> None:
    from .._server import build_server

    descriptors = build_tool_descriptors()
    always_on = {HARNESS_LOAD_TOOL, "search", "execute"}

    async def _advertised(mode: SurfaceMode) -> set[str]:
        server = cast("Any", build_server(descriptors, persona=None, surface_mode=mode))
        async with connect(server) as session:
            tools = (await session.list_tools()).tools
        return {tool.name for tool in tools}

    async def _drive() -> None:
        core = await _advertised(SurfaceMode.CORE)
        full = await _advertised(SurfaceMode.FULL)

        # The always-on floor + meta pair reach the client in BOTH modes.
        assert always_on <= core
        assert always_on <= full
        # CORE advertises the orientation verb but NOT the long-tail verb.
        assert "cadrumo_overview_status" in core
        assert "cadrumo_ledger_add" not in core
        # FULL advertises the long-tail verb; CORE is a strict subset.
        assert "cadrumo_ledger_add" in full
        assert core < full

    anyio.run(_drive)


def test_long_tail_verb_stays_callable_by_name_under_the_core_surface() -> None:
    # Gate invariance: a verb the CORE surface does not ADVERTISE is still known
    # to the call-tool dispatch (``by_name`` spans every descriptor), so it is
    # reachable by a direct call or the ``execute`` meta-tool - discovered, not
    # removed. An unknown name returns the ``unknown tool`` error; a known but
    # unadvertised name does not.
    from .._server import build_server

    descriptors = build_tool_descriptors()
    server = cast("Any", build_server(descriptors, persona=None, surface_mode=SurfaceMode.CORE))

    async def _drive() -> None:
        async with connect(server) as session:
            result = await session.call_tool("cadrumo_ledger_add", {})
        text = " ".join(block.text for block in result.content if block.type == "text")
        assert "unknown tool" not in text.lower()

    anyio.run(_drive)
