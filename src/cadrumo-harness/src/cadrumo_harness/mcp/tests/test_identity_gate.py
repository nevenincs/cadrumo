"""The block-first-mutation identity gate.

Proves the pure decision logic directly (SDK-independent) and the wired gate
through the real built ``Server`` (SDK-gated, never skipped): an unconfirmed
first mutating call is refused; an identity read clears it; a profile switch
or strong logout re-arms it; and the refusal is byte-identical on the direct
call path and the ``execute`` meta path. No mocks - the state object and
decision function are exercised as real logic and the server drives real
handlers.
"""

from __future__ import annotations

import importlib.util
from typing import Any, cast

import anyio
import pytest

from cadrumo.application.operator_surface import command_classification

from .._dispatch import tool_name_for_command
from .._harness_tools import HARNESS_LOAD_TOOL, WHOAMI_TOOL
from .._identity_gate import (
    ACTIVE_IDENTITY_CHANGING_COMMANDS,
    IDENTITY_READ_COMMANDS,
    IDENTITY_READ_CONSOLE_TOOLS,
    SessionIdentityState,
    identity_elicitation_echo,
    identity_gate_refusal,
)
from .._tools import build_tool_descriptors
from ._session import connected_server_and_client_session as connect

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_SDK_PRESENT = importlib.util.find_spec("mcp") is not None

# A concrete mutating verb (declared not-read-only in the risk table) and its
# MCP tool name, plus a concrete read-only identity verb. A handoff verb is used
# for the server-level cases so a CLEARED gate refuses at the confirmation route
# (no elicitation channel in a unit build) instead of spawning a real CLI
# subprocess - the identity refusal and that confirmation refusal are distinct
# texts, so "gate cleared" is asserted by the identity refusal being absent.
_MUTATING_KEY = "ledger.export"
_MUTATING_TOOL = "cadrumo_ledger_export"
_IDENTITY_READ_KEY = "overview.status"
_LOGOUT_KEY = "config.logout"
_LOGOUT_TOOL = tool_name_for_command(_LOGOUT_KEY)


# --- pure decision logic (SDK-independent) ------------------------------------


def test_first_mutation_is_refused_when_unconfirmed() -> None:
    state = SessionIdentityState()
    assert state.identity_confirmed is False
    refusal = identity_gate_refusal(_MUTATING_KEY, state=state)
    assert refusal is not None
    assert refusal.strip()


def test_an_identity_read_clears_the_gate() -> None:
    state = SessionIdentityState()
    # An identity-read verb records the read and is itself allowed...
    assert identity_gate_refusal(_IDENTITY_READ_KEY, state=state) is None
    assert state.identity_confirmed is True
    # ...so the next mutating call proceeds.
    assert identity_gate_refusal(_MUTATING_KEY, state=state) is None


def test_whoami_style_direct_read_clears_the_gate() -> None:
    # whoami carries no command key; the server records it via this method.
    state = SessionIdentityState()
    state.record_identity_read()
    assert identity_gate_refusal(_MUTATING_KEY, state=state) is None


def test_every_active_identity_change_re_arms_the_gate() -> None:
    state = SessionIdentityState()
    state.record_identity_read()
    assert identity_gate_refusal(_MUTATING_KEY, state=state) is None  # confirmed, allowed
    for command_key in sorted(ACTIVE_IDENTITY_CHANGING_COMMANDS):
        state.record_identity_read()  # confirm again before each identity change
        assert identity_gate_refusal(command_key, state=state) is None
        assert state.identity_confirmed is False
        # The next mutating call is refused again until a fresh read.
        assert identity_gate_refusal(_MUTATING_KEY, state=state) is not None


def test_harness_load_and_whoami_are_the_console_identity_reads() -> None:
    assert HARNESS_LOAD_TOOL in IDENTITY_READ_CONSOLE_TOOLS
    assert WHOAMI_TOOL in IDENTITY_READ_CONSOLE_TOOLS


def test_a_profile_switch_after_a_console_read_re_arms_the_gate() -> None:
    # harness.load / whoami clear the gate via record_identity_read (the server's
    # console-identity-read hook). A profile switch AFTER that console read still
    # re-arms, so identity is re-confirmed before any mutation post-switch - the
    # Erik/Erika guarantee survives the harness.load path.
    state = SessionIdentityState()
    state.record_identity_read()  # e.g. a harness.load floor read on session start
    assert identity_gate_refusal(_MUTATING_KEY, state=state) is None  # cleared
    assert identity_gate_refusal("config.login", state=state) is None  # switch allowed
    assert state.identity_confirmed is False  # ...and re-arms
    assert identity_gate_refusal(_MUTATING_KEY, state=state) is not None  # refused again


def test_read_only_calls_never_trip_the_gate_and_do_not_confirm() -> None:
    state = SessionIdentityState()
    # A non-identity read-only verb (declared read_only in the manifest) is
    # allowed but does NOT clear the gate.
    assert identity_gate_refusal("overview.agenda", state=state) is None
    assert state.identity_confirmed is False
    # So a following mutation is still refused.
    assert identity_gate_refusal(_MUTATING_KEY, state=state) is not None


def test_every_identity_read_command_clears_the_gate() -> None:
    for read_key in sorted(IDENTITY_READ_COMMANDS):
        state = SessionIdentityState()
        assert identity_gate_refusal(read_key, state=state) is None
        assert state.identity_confirmed is True


#: The sandbox-entry keys the identity gate no longer knows about. Entering a
#: sandbox now happens through the canonical ``config.login`` switch, which
#: carries a ``sandbox:<name>`` label, so these have no registration and no
#: place in the gate's identity-changing set.
_RETIRED_SANDBOX_USE_KEYS: tuple[str, ...] = ("config.sandbox.use", "sandbox.use")


def test_the_canonical_switch_carries_the_identity_change_not_a_sandbox_verb() -> None:
    """The gate re-arms on the canonical switch, and knows no sandbox-use verb.

    The positive control is stated first and is load-bearing: every claim
    below is an absence, and a set that had been emptied, or a descriptor
    build that returned nothing, would satisfy all of them while proving
    nothing.
    """
    exposed = {descriptor.command_key for descriptor in build_tool_descriptors()}

    assert "config.login" in ACTIVE_IDENTITY_CHANGING_COMMANDS
    assert "config.login" in exposed
    assert identity_gate_refusal("config.login", state=SessionIdentityState()) is None

    for retired in _RETIRED_SANDBOX_USE_KEYS:
        assert retired not in ACTIVE_IDENTITY_CHANGING_COMMANDS
        assert retired not in exposed


def test_a_reappearing_sandbox_use_verb_would_fail_closed_rather_than_pass() -> None:
    """Unavailability is not the only guarantee worth holding, so the fallback is pinned.

    A key absent from the risk table classifies all-false, which means NOT
    read-only. The gate therefore treats a sandbox-use verb as an ordinary
    mutating call and refuses it on an unconfirmed session, rather than
    waving it through as it once did by name. This is the property that
    survives someone re-registering the verb without re-reading this module.
    """
    for retired in _RETIRED_SANDBOX_USE_KEYS:
        assert command_classification(retired).read_only is False
        assert identity_gate_refusal(retired, state=SessionIdentityState()) is not None

    # ...and it is a refusal on the UNCONFIRMED session specifically, not a
    # blanket block: a confirmed session lets the same call through, so the
    # assertion above is measuring the gate and not a dead key path.
    confirmed = SessionIdentityState()
    confirmed.record_identity_read()
    for retired in _RETIRED_SANDBOX_USE_KEYS:
        assert identity_gate_refusal(retired, state=confirmed) is None


def test_elicitation_echo_names_the_label_never_empty() -> None:
    assert "Erika" in identity_elicitation_echo(active_profile_label="Erika")
    # A missing label renders a neutral placeholder, not an empty name.
    assert identity_elicitation_echo(active_profile_label=None).strip()
    assert identity_elicitation_echo(active_profile_label="").strip()


# --- wired gate through the real server (SDK-gated, never skipped) -------------


def _direct_refusal_text(server: Any) -> str:
    async def _drive() -> str:
        async with connect(server) as session:
            result = await session.call_tool(_MUTATING_TOOL, {})
        assert result.is_error is True
        return " ".join(block.text for block in result.content if block.type == "text")

    return anyio.run(_drive)


def _execute_refusal_text(server: Any) -> str:
    async def _drive() -> str:
        async with connect(server) as session:
            result = await session.call_tool("execute", {"command_key": _MUTATING_KEY, "arguments": {}})
        assert result.is_error is True
        # The execute path carries the refusal inside the error envelope.
        assert result.structured_content is not None
        return str(result.structured_content["refusal"])

    return anyio.run(_drive)


def test_unconfirmed_first_mutation_refuses_on_both_paths_byte_identical() -> None:
    from .._server import build_server

    descriptors = build_tool_descriptors()
    if not _SDK_PRESENT:
        with pytest.raises(ModuleNotFoundError, match="mcp"):
            build_server(descriptors)
        return

    # The expected refusal, computed from the same decision function.
    expected = identity_gate_refusal(_MUTATING_KEY, state=SessionIdentityState())
    assert expected is not None

    # A fresh server per path so neither call has a prior identity read.
    direct = _direct_refusal_text(cast("Any", build_server(descriptors, persona=None)))
    execute = _execute_refusal_text(cast("Any", build_server(descriptors, persona=None)))

    assert direct == expected
    assert execute == expected
    # Gate invariance: byte-identical across the two call paths.
    assert direct == execute


def test_a_whoami_read_clears_the_gate_on_the_direct_path() -> None:
    from .._server import build_server

    descriptors = build_tool_descriptors()
    if not _SDK_PRESENT:
        with pytest.raises(ModuleNotFoundError, match="mcp"):
            build_server(descriptors)
        return

    expected_refusal = identity_gate_refusal(_MUTATING_KEY, state=SessionIdentityState())
    assert expected_refusal is not None

    server = cast("Any", build_server(descriptors, persona=None))

    async def _drive() -> None:
        async with connect(server) as session:
            # A whoami read first, on the same session...
            whoami_result = await session.call_tool(WHOAMI_TOOL, {})
            assert whoami_result.is_error is False
            # ...so the subsequent mutating call is no longer identity-refused. It may
            # still fail downstream (e.g. no active profile), but NOT with the gate.
            mutate_result = await session.call_tool(_MUTATING_TOOL, {})
        text = " ".join(block.text for block in mutate_result.content if block.type == "text")
        assert expected_refusal not in text

    anyio.run(_drive)


def test_a_harness_load_read_clears_the_gate_on_the_direct_path() -> None:
    # The harness.load identity read carries the block, so loading
    # the floor clears the gate - the subsequent first mutation is not identity-
    # refused (it refuses instead at the confirmation route, a distinct text).
    from .._server import build_server

    descriptors = build_tool_descriptors()
    if not _SDK_PRESENT:
        with pytest.raises(ModuleNotFoundError, match="mcp"):
            build_server(descriptors)
        return

    expected_refusal = identity_gate_refusal(_MUTATING_KEY, state=SessionIdentityState())
    assert expected_refusal is not None

    server = cast("Any", build_server(descriptors, persona=None))

    async def _drive() -> None:
        async with connect(server) as session:
            load_result = await session.call_tool(HARNESS_LOAD_TOOL, {})
            assert load_result.is_error is False
            mutate_result = await session.call_tool(_MUTATING_TOOL, {})
        text = " ".join(block.text for block in mutate_result.content if block.type == "text")
        assert expected_refusal not in text

    anyio.run(_drive)


def test_identity_state_is_shared_across_the_two_call_paths() -> None:
    # State is shared: an identity read on the DIRECT path (whoami, no
    # subprocess) clears the gate for a subsequent ``execute`` mutating call on
    # the same session, so the execute call is no longer identity-refused (it
    # refuses instead at the confirmation route, a distinct text).
    from .._server import build_server

    descriptors = build_tool_descriptors()
    if not _SDK_PRESENT:
        with pytest.raises(ModuleNotFoundError, match="mcp"):
            build_server(descriptors)
        return

    expected_refusal = identity_gate_refusal(_MUTATING_KEY, state=SessionIdentityState())
    assert expected_refusal is not None

    server = cast("Any", build_server(descriptors, persona=None))

    async def _drive() -> None:
        async with connect(server) as session:
            whoami_result = await session.call_tool(WHOAMI_TOOL, {})
            assert whoami_result.is_error is False
            mutate_result = await session.call_tool("execute", {"command_key": _MUTATING_KEY, "arguments": {}})
        assert mutate_result.structured_content is not None
        assert expected_refusal not in str(mutate_result.structured_content.get("refusal", ""))

    anyio.run(_drive)


@pytest.mark.parametrize(
    ("logout_tool", "logout_arguments"),
    (
        (_LOGOUT_TOOL, {}),
        ("execute", {"command_key": _LOGOUT_KEY, "arguments": {}}),
    ),
)
def test_strong_logout_re_arms_identity_on_direct_and_execute_paths(
    logout_tool: str,
    logout_arguments: dict[str, object],
) -> None:
    """Both server paths re-arm before the strong-logout confirmation route."""
    from .._server import build_server

    descriptors = build_tool_descriptors()
    if not _SDK_PRESENT:
        with pytest.raises(ModuleNotFoundError, match="mcp"):
            build_server(descriptors)
        return

    expected_refusal = identity_gate_refusal(_MUTATING_KEY, state=SessionIdentityState())
    assert expected_refusal is not None

    server = cast("Any", build_server(descriptors, persona=None))

    async def _drive() -> None:
        async with connect(server) as session:
            whoami_result = await session.call_tool(WHOAMI_TOOL, {})
            assert whoami_result.is_error is False

            logout_result = await session.call_tool(logout_tool, logout_arguments)
            logout_text = " ".join(block.text for block in logout_result.content if block.type == "text")
            assert expected_refusal not in logout_text
            assert expected_refusal not in str(logout_result.structured_content or {})

            mutate_result = await session.call_tool(_MUTATING_TOOL, {})
        text = " ".join(block.text for block in mutate_result.content if block.type == "text")
        assert text == expected_refusal

    anyio.run(_drive)
