"""Every declared command-spec target must resolve against the live tree.

A :class:`~cadrumo.entrypoints.cli.command_spec.DeferredTarget` names a module
and a public qualname as strings, so nothing checks it until the owning command
group is lazily built. A target that names an inert package namespace, or a
symbol that a rename moved, therefore ships green and only fails when an
operator -- or a documentation sequence -- reaches that command, where it
surfaces as an unhandled ``RuntimeError`` rather than an instructive refusal.

This gate resolves every target the spec graph declares, through the same
:attr:`~cadrumo_client.commands.graph.CommandSpecGraph.resolver` the
owning graph uses, so a dangling target fails here instead of at the operator's
terminal.

Targets are discovered by walking the spec dataclasses recursively rather than
by reading a fixed list of fields: a new target-bearing field on any spec is
then covered the day it lands.
"""

from __future__ import annotations

import dataclasses
import sys
from collections.abc import Iterator
from typing import Final

import pytest

from cadrumo.tests.audited_process import run_audited_process
from cadrumo_client.commands.shared_contracts import DeferredTarget

from ..command_specs import COMMAND_GRAPH

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

#: Sanity floor for the walk itself. Deliberately NOT the exact target count:
#: an exact tally encodes a moment, trains everyone to bump the constant, and
#: then detects nothing. This only proves the walk still reaches the graph.
_MINIMUM_DISCOVERED_TARGETS: Final[int] = 100


def _iter_deferred_targets(value: object) -> Iterator[DeferredTarget]:
    """Yield every target reachable from ``value``, preserving repeated fields."""
    if isinstance(value, DeferredTarget):
        yield value
        return
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        for field in dataclasses.fields(value):
            yield from _iter_deferred_targets(getattr(value, field.name))
        return
    if isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            yield from _iter_deferred_targets(item)
        return
    if isinstance(value, dict):
        for item in value.values():
            yield from _iter_deferred_targets(item)


def _declared_targets() -> tuple[DeferredTarget, ...]:
    """Return every target the live command-spec graph declares."""
    return tuple(target for node in COMMAND_GRAPH.nodes() for target in _iter_deferred_targets(node.spec))


def test_the_walk_reaches_the_command_spec_graph() -> None:
    """The recursive walk must actually find targets, or the gate is vacuous."""
    discovered = _declared_targets()
    assert len(discovered) >= _MINIMUM_DISCOVERED_TARGETS, (
        f"discovered only {len(discovered)} deferred targets across "
        f"{len(tuple(COMMAND_GRAPH.nodes()))} command specs; the walk is not reaching the graph"
    )


def test_every_declared_command_target_resolves() -> None:
    """No command spec may name a module or symbol the tree does not define."""
    failures: list[str] = []
    for target in _declared_targets():
        try:
            COMMAND_GRAPH.resolver(target)
        except (RuntimeError, ImportError) as error:
            failures.append(f"{target.identity!r} -- {type(error).__name__}: {error}")

    assert not failures, "command specs declare targets that do not resolve:\n" + "\n".join(sorted(failures))


@pytest.mark.parametrize(
    ("module", "qualname"),
    [
        ("cadrumo.entrypoints.cli.command_specs", "definitely_not_a_real_symbol"),
        ("cadrumo.definitely.not.a.real.module", "Anything"),
    ],
)
def test_the_resolver_rejects_a_dangling_target(module: str, qualname: str) -> None:
    """Anti-tautology: prove the resolver this gate leans on actually refuses."""
    source = """
import sys
from cadrumo.entrypoints.cli.command_targets import resolve_deferred_target
from cadrumo_client.commands.shared_contracts import DeferredTarget
from cadrumo.core.errors.hierarchy import InternalInvariantError
try:
    resolve_deferred_target(DeferredTarget(sys.argv[1], sys.argv[2]))
except (InternalInvariantError, ImportError):
    pass
else:
    raise AssertionError('the actual resolver accepted a dangling target')
"""
    completed = run_audited_process(
        [sys.executable, "-c", source, module, qualname], check=False, capture_output=True, text=True
    )
    assert completed.returncode == 0, completed.stderr
