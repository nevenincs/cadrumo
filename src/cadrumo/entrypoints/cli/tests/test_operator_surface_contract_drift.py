"""Live-tree drift gate for the backend-owned ``OperatorSurfaceContract``.

The companion of :func:`test_every_cli_leaf_has_a_registered_schema`. That gate
proves every CLI leaf has a registered JSON schema; this one proves the
:class:`~cadrumo.application.operator_surface.OperatorSurfaceContract` — the source
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
from typer.main import get_command as _typer_get_command

from ....application.operator_surface import COMMAND_RISK, get_operator_surface_contract
from ._lazy_command_tree import materialise_lazy_subcommands

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PINNED_ROOTS: frozenset[str] = frozenset({"config", "app"})


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

    materialise_lazy_subcommands(live_app)
    root = _typer_get_command(live_app)
    root.name = live_app.info.name or "cadrumo"

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

    # Anti-vacuity floor. A symmetric-difference assertion over two empty maps
    # passes while checking nothing, and the lazy-Typer tree is a documented
    # false-green vector: an isinstance-gated or unmaterialised walk yields a
    # single leaf (or none) and terminates silently. Pin the resolved surface
    # against its known shape so a collapsed walk reds here rather than passing
    # a mirror of two empty inventories. The floors sit comfortably below the
    # live counts (2 roots, 23 families, 151 sub-verbs) yet far above the
    # single-leaf blind-walk failure.
    live_family_total = sum(len(families) for families in live.values())
    live_sub_verb_total = sum(len(sub) for families in live.values() for sub in families.values())
    assert set(live) == _PINNED_ROOTS, f"live surface did not resolve both pinned roots: {sorted(live)}"
    assert live_family_total >= 20, (
        f"live tree resolved only {live_family_total} families; the lazy walk likely collapsed"
    )
    assert live_sub_verb_total >= 120, (
        f"live tree resolved only {live_sub_verb_total} sub-verbs; the lazy walk likely collapsed"
    )
    assert declared, "the operator-surface contract declared no families, so this gate would check nothing"

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


def test_no_risk_row_outlives_the_command_it_classifies() -> None:
    """Every declared risk row resolves to a command the surface still exposes.

    This is deliberately ONE-DIRECTIONAL, and the direction matters.

    An orphan risk row -- a declaration for a command that no longer exists --
    is pure drift: it survives a verb removal silently, and the next reader
    takes it for evidence that the door is still mounted. Nothing else in the
    tree catches it, because no consumer looks up a key that never arrives.

    The reverse is NOT asserted, because an absent row is a designed state
    rather than a gap. ``classify`` derives safe for a command with no row, so
    read-only verbs are intentionally undeclared, and today 26 of them are --
    the overview reports, the citation reads, ``config check``, ``contract``.
    Asserting an exact mirror would therefore fail against correct data and
    would have to be "fixed" by declaring rows that say nothing, which is how a
    risk table stops meaning anything. The classification tests own the other
    direction, where absence is checked as behaviour rather than inventory.
    """
    from ...mcp import build_tool_descriptors

    live_keys = {descriptor.command_key for descriptor in build_tool_descriptors()}
    assert live_keys, "descriptor set is empty, so this gate would pass while checking nothing"
    assert COMMAND_RISK, "risk table is empty, so this gate would pass while checking nothing"

    orphans = sorted(key for key in COMMAND_RISK if key not in live_keys)

    assert not orphans, (
        f"risk rows classify commands the surface no longer exposes: {orphans}. A removed verb must take "
        "its risk declaration with it, or the table asserts a door that is not there"
    )
