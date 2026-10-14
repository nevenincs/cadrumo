"""Canonical command-graph argument driving and runtime-independent observation helpers."""

from __future__ import annotations

import inspect
import sys
from collections.abc import Mapping
from enum import Enum
from pathlib import Path
from types import CodeType
from typing import Final
from uuid import UUID

from ...contracts.command_ports import CommandNodeKind
from ..graph import CommandSpecGraph
from ..parameters import ArgumentSpec, OptionSpec
from ..shared_contracts import DefaultKind, DeferredTarget
from ..spec import CommandSpec
from ..target import resolve_deferred_target

PROBE_PROFILE_LABEL: Final = "Governed fact declaration probe"

PROBE_PROFILE_TAX_ID: Final = "12345678Z"


def is_runnable(spec: CommandSpec) -> bool:
    """Report whether a spec has terminal behavior an operator can run."""
    return spec.kind == CommandNodeKind.LEAF or (
        spec.kind == CommandNodeKind.GROUP and spec.invocation.terminal_behavior == "executable"
    )


def command_path(graph: CommandSpecGraph, spec: CommandSpec) -> tuple[str, ...]:
    """Return the operator tokens that select ``spec`` below the root."""
    tokens: list[str] = []
    current = spec
    while current.parent_key is not None:
        tokens.append(current.token)
        current = graph.spec(current.parent_key)
    return tuple(reversed(tokens))


def _synthetic_value(spec: CommandSpec, parameter: ArgumentSpec | OptionSpec, workdir: Path) -> str:
    if parameter.value.choices:
        return parameter.value.choices[0]
    annotation = resolve_deferred_target(parameter.value.annotation)
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        member = next(iter(annotation))
        return str(member.value)
    if annotation is int:
        minimum = parameter.constraint.minimum
        return str(int(minimum) if minimum is not None else 1)
    if annotation is UUID:
        return "00000000-0000-4000-8000-000000000001"
    if parameter.name == "review_digest":
        return "0" * 64
    if isinstance(annotation, type) and issubclass(annotation, Path):
        location = workdir / f"{spec.key}-{parameter.name}.bin"
        if parameter.name != "output":
            location.write_bytes(b"synthetic probe input\n")
        return str(location)
    if parameter.name in {"name", "label"}:
        return PROBE_PROFILE_LABEL
    return f"probe-{parameter.name.replace('_', '-')}"


def synthetic_argv(
    graph: CommandSpecGraph,
    spec: CommandSpec,
    workdir: Path,
    *,
    also: tuple[str, ...] = (),
    values: Mapping[str, str] | None = None,
) -> list[str]:
    """Build the command path plus a synthetic value for every required parameter.

    ``also`` names optional parameters to supply as well, and ``values`` gives
    named parameters a domain-valid value in place of the synthetic one.
    """
    supplied = values or {}
    positional: list[str] = []
    named: list[str] = []
    for parameter in spec.parameters:
        wanted = parameter.name in also or parameter.name in supplied
        if parameter.default.kind is not DefaultKind.REQUIRED and not wanted:
            continue
        value = supplied.get(parameter.name) or _synthetic_value(spec, parameter, workdir)
        if isinstance(parameter, OptionSpec):
            named.extend((parameter.declarations[0], value))
        else:
            positional.append(value)
    return [*command_path(graph, spec), *positional, *named]


def free_monitoring_tool() -> int:
    """Return a ``sys.monitoring`` tool id no other tool holds."""
    for tool_id in (3, 4):
        if sys.monitoring.get_tool(tool_id) is None:
            return tool_id
    raise AssertionError("no free sys.monitoring tool id for a command probe")


def handler_code(target: DeferredTarget) -> CodeType:
    """Return the code object of a command's declared behavior target."""
    behavior = resolve_deferred_target(target)
    if callable(behavior):
        behavior = inspect.unwrap(behavior)
    code = getattr(behavior, "__code__", None)
    if not isinstance(code, CodeType):
        raise AssertionError(f"behavior target {target.identity!r} has no Python code to observe")
    return code
