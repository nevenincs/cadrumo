"""Drive a live command through the real CLI with synthetic arguments and observe it.

The command-graph probes share one way of reaching a command: its operator path
comes from the graph's parent chain, each required parameter gets a synthetic
value derived from its declared type, and a seeded natural-person profile gives
profile-bound commands something to open. ``sys.monitoring`` then watches the
command's own behavior target, so a probe can prove its command actually ran.
"""

from __future__ import annotations

import inspect
import sys
from enum import Enum
from pathlib import Path
from types import CodeType
from typing import Final

from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.application.operator_surface.command_ports import CommandNodeKind

from ....adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ....domain.user_profile.tests.profile_creation_authority import profile_creation_context_for_test
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from .._command_runtime import resolve_deferred_target
from ..command_spec import ArgumentSpec, CommandSpec, CommandSpecGraph, DefaultKind, DeferredTarget, OptionSpec

PROBE_PROFILE_ID: Final = "0ac1e000-0000-4000-8000-000000515077"
PROBE_PROFILE_LABEL: Final = "Governed fact declaration probe"


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
) -> list[str]:
    """Build the command path plus a synthetic value for every required parameter.

    ``also`` names optional parameters to supply as well.
    """
    positional: list[str] = []
    named: list[str] = []
    for parameter in spec.parameters:
        if parameter.default.kind is not DefaultKind.REQUIRED and parameter.name not in also:
            continue
        value = _synthetic_value(spec, parameter, workdir)
        if isinstance(parameter, OptionSpec):
            named.extend((parameter.declarations[0], value))
        else:
            positional.append(value)
    return [*command_path(graph, spec), *positional, *named]


def seed_probe_profile(runtime_profile: TestRuntimeProfile) -> None:
    """Seed a natural-person profile; the seed itself may lease the authority."""
    with bundled_indexed_authority().operation() as operation, validating_governed_facts(operation):
        record = create_user_profile_record(
            profile_id=PROBE_PROFILE_ID,
            setup_state=ProfileSetupState.COMPLETE,
            facts=(
                UserProfileFact(path="identity.name", value="Ana"),
                UserProfileFact(path="identity.surnames", value="Perez"),
                UserProfileFact(path="identity.tax_id", value="12345678Z"),
                UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                UserProfileFact(path="provenance.source", value="manual_cli"),
            ),
            context=profile_creation_context_for_test(),
        )
        seed_test_profile_record(record, root=runtime_profile.storage_root, label=PROBE_PROFILE_LABEL)


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


__all__ = [
    "PROBE_PROFILE_ID",
    "PROBE_PROFILE_LABEL",
    "command_path",
    "free_monitoring_tool",
    "handler_code",
    "is_runnable",
    "seed_probe_profile",
    "synthetic_argv",
]
