"""Determinism-replay for operator tool calls.

Captures golden tool-call records (the tool name, its arguments, and the resolved
invocation) and replays them, asserting the resolution is byte-identical. A
non-deterministic mapping is an assurance failure in regulated work: the same
operator action must always project onto the same deterministic CLI invocation.
Pure: the resolver is injected, so this module stays free of the entrypoints
layer it replays.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from pydantic import BaseModel, ConfigDict, Field

_STRICT_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")

#: A resolver projects a (tool_name, args) call onto its deterministic invocation.
ToolCallResolver = Callable[[str, tuple[str, ...]], tuple[str, ...]]


class GoldenToolCall(BaseModel):
    """A captured tool call and its resolved invocation."""

    model_config = _STRICT_FROZEN

    tool_name: str = Field(min_length=1)
    args: tuple[str, ...]
    invocation: tuple[str, ...]


def record_tool_call(tool_name: str, args: tuple[str, ...], *, resolve: ToolCallResolver) -> GoldenToolCall:
    """Capture a golden tool call by resolving it once.

    Returns:
        :class:`GoldenToolCall` containing the original call and invocation.
    """
    return GoldenToolCall(tool_name=tool_name, args=args, invocation=resolve(tool_name, args))


def replay_tool_call(record: GoldenToolCall, *, resolve: ToolCallResolver) -> bool:
    """Return True when re-resolving the record yields its captured invocation."""
    return resolve(record.tool_name, record.args) == record.invocation


def divergent_replays(
    records: Iterable[GoldenToolCall],
    *,
    resolve: ToolCallResolver,
) -> tuple[GoldenToolCall, ...]:
    """Return the records whose replay diverges from their captured invocation.

    Returns:
        Tuple of divergent :class:`GoldenToolCall` records.
    """
    return tuple(record for record in records if not replay_tool_call(record, resolve=resolve))
