"""Live-tree drift gate for the backend-owned ``OperatorSurfaceContract``.

The companion of :func:`test_every_cli_leaf_has_a_registered_schema`. That gate
proves every CLI leaf has a registered JSON schema; this one proves the
:class:`~aeat.application.operator_surface.OperatorSurfaceContract` — the source
the ``aeat app contract`` capability manifest (and, later, the MCP ``tools/list``)
is built from — declares *exactly* the mounted command families and their
sub-verbs.

Without this gate the contract is self-referential: the sibling
``test_required_children_match_mounted_command_families`` checks the contract
against itself, and ``test_app_contract`` checks the manifest against the same
contract. Neither resolves the real Typer tree, so a whole family
(``config google``, ``config check``, ``config reset``) or a sub-verb (every
``app live`` child but ``filed``) could be — and was — absent from the manifest
while the CLI mounted it, handing an agent an authoritative-looking tool map with
holes.

The gate forces every lazily-registered subtree to materialise, walks the two
pinned roots two levels deep, and computes the symmetric difference between the
live ``root -> family -> sub-verb`` surface and the contract's declaration. The
difference must be empty. There is no allowlist: a new family or sub-verb that
lands without a contract update reds this gate (and is therefore co-committed
with the contract by construction).
"""

from __future__ import annotations

from typing import TypeGuard, cast

import click
import pytest
import typer
from typer.main import get_command as _typer_get_command

from ....application.operator_surface import get_operator_surface_contract

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PINNED_ROOTS: frozenset[str] = frozenset({"config", "app"})


def _force_load_lazy_subcommands(app: typer.Typer) -> None:
    """Materialise every lazily-registered subcommand on ``app`` and its descendants.

    Mirrors the leaf-schema gate's loader: the CLI registers heavy subtrees via
    :func:`register_lazy_subcommand` in a process-global table keyed by group
    name, imported only on dispatch. The drift gate needs the full tree at
    collection time, so we force-load every lazy entry under every materialised
    group.
    """
    from .._command_suggestions import _LAZY_REGISTRY

    seen: set[int] = set()
    pending: list[typer.Typer] = [app]
    while pending:
        node = pending.pop()
        if id(node) in seen:
            continue
        seen.add(id(node))
        group_name = node.info.name or ""
        for lazy in _LAZY_REGISTRY.get(group_name, {}).values():
            lazy.load()
        for group in node.registered_groups:
            if group.typer_instance is not None:
                pending.append(group.typer_instance)


def _is_command_group(command: click.Command) -> TypeGuard[click.Group]:
    """Return True when ``command`` is a Click group / multi-command.

    Typer vendors its own Click, so commands returned by
    :func:`typer.main.get_command` are not instances of the imported
    ``click.Group``; duck-typing on the group interface is vendor-robust.
    """
    return callable(getattr(command, "list_commands", None)) and callable(getattr(command, "get_command", None))


def _direct_children(command: click.Command) -> dict[str, click.Command]:
    """Return the directly-mounted child commands of ``command`` (empty for a leaf).

    Materialises the synthetic context so a lazy ``get_command`` resolves every
    registered subcommand, including those behind a lazy loader.
    """
    children: dict[str, click.Command] = {}
    if not _is_command_group(command):
        return children
    with click.Context(command, info_name=command.name or None) as ctx:
        for child_name in command.list_commands(ctx):
            child = command.get_command(ctx, child_name)
            if child is not None:
                children[str(child_name)] = child
    return children


def _resolve_live_surface() -> dict[str, dict[str, frozenset[str]]]:
    """Resolve ``{root: {family-child: frozenset(sub-verb)}}`` from the live tree.

    For a family whose child is a group with sub-commands, the sub-verb set is its
    direct child names. For a family whose child is a leaf command (or an
    ``invoke_without_command`` group with no registered leaf, e.g. ``app contract``),
    the sub-verb set is the degenerate self-reference ``{child}`` — matching the
    contract's convention of summarising such a verb as ``commands=(child,)``.
    """
    from .. import app as live_app

    _force_load_lazy_subcommands(live_app)
    root = _typer_get_command(live_app)
    root.name = live_app.info.name or "aeat"

    surface: dict[str, dict[str, frozenset[str]]] = {}
    for root_name, root_cmd in _direct_children(cast(click.Command, root)).items():
        if root_name not in _PINNED_ROOTS:
            continue
        families: dict[str, frozenset[str]] = {}
        for child_name, child_cmd in _direct_children(root_cmd).items():
            sub_verbs = frozenset(_direct_children(child_cmd))
            families[child_name] = sub_verbs or frozenset({child_name})
        surface[root_name] = families
    return surface


def _declared_surface() -> dict[str, dict[str, frozenset[str]]]:
    """Resolve ``{root: {family-child: frozenset(command)}}`` from the contract."""
    declared: dict[str, dict[str, frozenset[str]]] = {}
    for family in get_operator_surface_contract().command_families:
        declared.setdefault(family.root.value, {})[family.child] = frozenset(
            str(command) for command in family.commands
        )
    return declared


def test_operator_surface_contract_covers_the_live_tree() -> None:
    """The contract declares exactly the mounted families and their sub-verbs.

    Symmetric difference, both levels, no allowlist:

    * **Family drift** — a ``root -> child`` group/leaf mounted by the CLI but
      absent from ``command_families`` (the agent's manifest would omit it), or a
      contract family with no live mount (a dead manifest entry).
    * **Sub-verb drift** — within a shared family, a sub-command mounted by the
      CLI but missing from the family's ``commands`` tuple (or the reverse).

    The diagnostic names every drifted family and sub-verb so a regression run
    states the exact contract edit without further investigation.
    """
    live = _resolve_live_surface()
    declared = _declared_surface()

    lines: list[str] = []
    for root in sorted(set(live) | set(declared)):
        live_families = live.get(root, {})
        declared_families = declared.get(root, {})

        families_missing = sorted(set(live_families) - set(declared_families))
        families_orphan = sorted(set(declared_families) - set(live_families))
        if families_missing:
            lines.append(f"[{root}] families mounted by the CLI but ABSENT from the contract: {families_missing}")
        if families_orphan:
            lines.append(f"[{root}] contract families with NO live CLI mount: {families_orphan}")

        for child in sorted(set(live_families) & set(declared_families)):
            sub_missing = sorted(live_families[child] - declared_families[child])
            sub_orphan = sorted(declared_families[child] - live_families[child])
            if sub_missing:
                lines.append(
                    f"[{root} {child}] sub-verbs mounted by the CLI but ABSENT from the contract: {sub_missing}",
                )
            if sub_orphan:
                lines.append(f"[{root} {child}] contract sub-verbs with NO live CLI mount: {sub_orphan}")

    assert not lines, "OperatorSurfaceContract drifted from the live CLI tree:\n" + "\n".join(lines)
