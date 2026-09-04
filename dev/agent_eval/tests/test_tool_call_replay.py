"""Determinism-replay gate over the MCP tool-call dispatch.

Records golden tool calls resolved through the real MCP dispatch and asserts they
replay byte-identically, with an anti-tautology proof that a tampered record is
detected as divergent.
"""

from __future__ import annotations

import pytest

from .._replay import GoldenToolCall, divergent_replays, record_tool_call, replay_tool_call

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _resolver():
    from cadrumo_harness.mcp import (
        build_tool_descriptors,
        command_key_for_tool,
        tool_request_argv,
    )

    keys = [d.command_key for d in build_tool_descriptors()]

    def resolve(tool_name: str, args: tuple[str, ...]) -> tuple[str, ...]:
        key = command_key_for_tool(tool_name, command_keys=keys)
        assert key is not None, tool_name
        return tuple(tool_request_argv(key, list(args)))

    return resolve


def _a_tool_that_takes_no_arguments() -> str:
    """Return the first live MCP tool whose input schema requires nothing.

    The golden list named ``cadrumo_contract`` literally, and that tool has
    since been retired: both cases here then failed inside the resolver on a
    name that no longer exists, which is the one failure a determinism gate
    must never report - it says the dispatch diverged when nothing replayed at
    all.

    The case being preserved is a call with an EMPTY argument tuple, not that
    particular tool. Deriving it from the live descriptors keeps the case while
    letting the tool providing it change, and sorting makes the choice the same
    on every run - which a replay gate requires of its own inputs.
    """
    from cadrumo_harness.mcp import build_tool_descriptors

    candidates = sorted(
        descriptor.name for descriptor in build_tool_descriptors() if not descriptor.input_schema.get("required")
    )
    assert candidates, "no live MCP tool accepts an empty argument list"
    return candidates[0]


def _golden_calls() -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Return the recorded calls: one with arguments, one without, one with options."""
    return (
        ("cadrumo_modelo_work_calculate", ("wu_123",)),
        (_a_tool_that_takes_no_arguments(), ()),
        ("cadrumo_modelo_ivaw_balance", ("--year", "2024")),
    )


def test_recorded_tool_calls_replay_identically() -> None:
    resolve = _resolver()
    records = [record_tool_call(name, args, resolve=resolve) for name, args in _golden_calls()]
    assert all(replay_tool_call(record, resolve=resolve) for record in records)
    assert divergent_replays(records, resolve=resolve) == ()


def test_a_tampered_record_is_detected_as_divergent() -> None:
    resolve = _resolver()
    record = record_tool_call(_a_tool_that_takes_no_arguments(), (), resolve=resolve)
    tampered = GoldenToolCall(
        tool_name=record.tool_name,
        args=record.args,
        invocation=(*record.invocation, "--injected"),
    )
    assert not replay_tool_call(tampered, resolve=resolve)
    assert divergent_replays([tampered], resolve=resolve) == (tampered,)
