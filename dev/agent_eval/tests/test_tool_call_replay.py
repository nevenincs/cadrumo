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


_CALLS = (
    ("cadrumo_modelo_work_calculate", ("wu_123",)),
    ("cadrumo_contract", ()),
    ("cadrumo_modelo_ivaw_balance", ("--year", "2024")),
)


def test_recorded_tool_calls_replay_identically() -> None:
    resolve = _resolver()
    records = [record_tool_call(name, args, resolve=resolve) for name, args in _CALLS]
    assert all(replay_tool_call(record, resolve=resolve) for record in records)
    assert divergent_replays(records, resolve=resolve) == ()


def test_a_tampered_record_is_detected_as_divergent() -> None:
    resolve = _resolver()
    record = record_tool_call("cadrumo_contract", (), resolve=resolve)
    tampered = GoldenToolCall(
        tool_name=record.tool_name,
        args=record.args,
        invocation=(*record.invocation, "--injected"),
    )
    assert not replay_tool_call(tampered, resolve=resolve)
    assert divergent_replays([tampered], resolve=resolve) == (tampered,)
