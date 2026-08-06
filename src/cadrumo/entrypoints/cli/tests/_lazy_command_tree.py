"""Materialise the CLI's lazily-registered Typer subtrees for whole-tree gates.

The CLI registers its heavy subtrees through
:func:`~entrypoints.cli._command_suggestions.register_lazy_subcommand`, which
records each one in a process-global table keyed by group name and imports the
backing module only when the operator dispatches to it. A gate that walks the
FULL command tree at collection time must therefore drain that table first, or
it silently walks a tree missing whole command families and passes while blind
to them.

This materialiser lives in the shipped tree because its consumers do. The
conformance suites in this package own the whole-tree walk, and a module under
``src/cadrumo`` must not reach into the repository's development tooling for a
primitive it depends on: that tooling is not part of the distribution, so the
dependency direction only ever resolves in a source checkout.

See Also:
    :func:`~entrypoints.cli._command_suggestions.register_lazy_subcommand`
        The registration side whose table this drains.
"""

from __future__ import annotations

import typer

from .._command_suggestions import _LAZY_REGISTRY

__all__ = ["materialise_lazy_subcommands"]


def materialise_lazy_subcommands(app: typer.Typer) -> None:
    """Load every lazily-registered subcommand reachable from ``app``.

    Walks ``app`` and its registered Typer groups, draining the lazy registry
    for each group name reached. Idempotent, and terminates on a cyclic group
    graph via the identity-seen set.

    Args:
        app: Root Typer application whose subtree is materialised in place.
    """
    seen: set[int] = set()
    pending: list[typer.Typer] = [app]
    while pending:
        node = pending.pop()
        if id(node) in seen:
            continue
        seen.add(id(node))
        for lazy in _LAZY_REGISTRY.get(node.info.name or "", {}).values():
            lazy.load()
        for group in node.registered_groups:
            if group.typer_instance is not None:
                pending.append(group.typer_instance)
