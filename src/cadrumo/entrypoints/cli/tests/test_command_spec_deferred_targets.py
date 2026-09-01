"""Every declared command-spec target must resolve against the live tree.

A :class:`~cadrumo.entrypoints.cli.command_spec.DeferredTarget` names a module
and a public qualname as strings, so nothing checks it until the owning command
group is lazily built. A target that names an inert package namespace, or a
symbol that a rename moved, therefore ships green and only fails when an
operator -- or a documentation sequence -- reaches that command, where it
surfaces as an unhandled ``RuntimeError`` rather than an instructive refusal.

This gate resolves every target the spec graph declares, through the same
:func:`~cadrumo.entrypoints.cli._command_target.resolve_deferred_target` the
runtime uses, so a dangling target fails here instead of at the operator's
terminal.

Targets are discovered by walking the spec dataclasses recursively rather than
by reading a fixed list of fields: a new target-bearing field on any spec is
then covered the day it lands.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator
from typing import Final

import pytest

from .._command_target import resolve_deferred_target
from ..command_spec import DeferredTarget
from ..command_specs import COMMAND_GRAPH

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

#: Sanity floor for the walk itself. Deliberately NOT the exact target count:
#: an exact tally encodes a moment, trains everyone to bump the constant, and
#: then detects nothing. This only proves the walk still reaches the graph.
_MINIMUM_DISCOVERED_TARGETS: Final[int] = 100


def _iter_deferred_targets(value: object, path: str) -> Iterator[tuple[str, DeferredTarget]]:
    """Yield every ``(path, target)`` reachable from ``value``."""
    if isinstance(value, DeferredTarget):
        yield path, value
        return
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        for field in dataclasses.fields(value):
            yield from _iter_deferred_targets(getattr(value, field.name), f"{path}.{field.name}")
        return
    if isinstance(value, (list, tuple, set, frozenset)):
        for index, item in enumerate(value):
            yield from _iter_deferred_targets(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _iter_deferred_targets(item, f"{path}[{key!r}]")


def _declared_targets() -> tuple[tuple[str, DeferredTarget], ...]:
    """Return every target the live command-spec graph declares."""
    return tuple(row for node in COMMAND_GRAPH.nodes() for row in _iter_deferred_targets(node.spec, node.spec.key))


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
    for path, target in _declared_targets():
        try:
            resolve_deferred_target(target)
        except (RuntimeError, ImportError) as error:
            failures.append(f"{path}: {target.identity!r} -- {type(error).__name__}: {error}")

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
    with pytest.raises((RuntimeError, ImportError)):
        resolve_deferred_target(DeferredTarget(module, qualname))
